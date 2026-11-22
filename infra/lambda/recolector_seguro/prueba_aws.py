"""Prueba aislada; todos los Put se redirigen a un prefijo S3 de laboratorio."""
import concurrent.futures
import importlib
import json
import os
import re
import urllib.error

recolector = importlib.import_module("infra.lambda.recolector_seguro.handler")
api = importlib.import_module("infra.api_gateway_aislada.handler")
DESTINO = "prisma-bmv-aislado-prueba-2026-bucket-pumqsjizexvp"
ORIGEN = "prisma-bmv-datalake-tunombre-2026"
HTML = ("""<p>19 Nov 2026</p><table><tr><th>Emisora</th><th>Serie</th>
<th>Último</th><th>Anterior</th><th>PPP</th></tr>
<tr><td>AMX</td><td>B</td><td>11</td><td>9</td><td>10</td></tr>
<tr><td>WALMEX</td><td>*</td><td>20</td><td>19</td><td>20</td></tr>
</table>""").encode()


class RedirigirS3:
    def __init__(self, cliente, prefijo):
        self.cliente, self.prefijo = cliente, prefijo
        self.fallar_silver = False

    def _destino(self, kwargs):
        if kwargs["Bucket"] != ORIGEN:
            raise ValueError("Bucket no autorizado.")
        key = kwargs["Key"]
        if key not in ("snapshot.csv", "snapshot-conflicto.csv") and not key.startswith((
            "bronze/", "silver/precios_ppp/", "silver/recolector_seguro/precios_ppp/",
            "silver/capturas_seguras/", "silver/capturas_en_curso/", "cuarentena/recolector-seguro/",
            "silver/ipc35_provisional/", "evidencias/operacion/",
        )):
            raise ValueError("Clave fuera de la prueba.")
        return {**kwargs, "Bucket": DESTINO, "Key": self.prefijo + key}

    def put_object(self, **kwargs):
        if self.fallar_silver and kwargs["Key"].startswith("silver/recolector_seguro/precios_ppp/"):
            self.fallar_silver = False
            raise RuntimeError("Fallo simulado antes de Silver")
        return self.cliente.put_object(**self._destino(kwargs))

    def get_object(self, **kwargs):
        return self.cliente.get_object(**self._destino(kwargs))

    def list_objects_v2(self, **kwargs):
        args = self._destino({**kwargs, "Key": kwargs["Prefix"]})
        args["Prefix"] = args.pop("Key")
        if "StartAfter" in args:
            args["StartAfter"] = self.prefijo + args["StartAfter"]
        response = self.cliente.list_objects_v2(**args)
        for item in response.get("Contents", []):
            if not item["Key"].startswith(self.prefijo):
                raise ValueError("Resultado S3 fuera del prefijo aislado.")
            item["Key"] = item["Key"][len(self.prefijo):]
        return response


def lambda_handler(event, context):
    import boto3
    if isinstance(event, dict) and set(event) == {"fecha_fuente"}:
        # Diagnóstico de red y contrato, sin S3, inferencia ni fuentes alternativas.
        if event["fecha_fuente"] not in ("2026-11-19", "2026-11-20"):
            raise ValueError("Fecha de diagnóstico no admitida.")
        from datetime import date
        fecha = date.fromisoformat(event["fecha_fuente"])
        url = recolector.core.url_boletin(fecha.strftime("%Y%m%d"))
        try:
            raw = recolector.descargar(url)
            filas = recolector._filas(raw, fecha, url)
            resultado = {"fecha": fecha.isoformat(), "estado": "BOLETIN_VALIDADO",
                         "filas": len(filas), "sin_escrituras": True}
        except Exception as exc:
            resultado = {"fecha": fecha.isoformat(), "estado": "FUENTE_NO_VALIDADA",
                         "tipo": type(exc).__name__, "detalle": str(exc)[:200],
                         "sin_escrituras": True}
        print("DIAGNOSTICO_FUENTE " + json.dumps(resultado, ensure_ascii=True))
        return resultado
    if not isinstance(event, dict) or set(event) != {"run_id"} or not re.fullmatch(r"[0-9a-f]{32}", event["run_id"]):
        raise ValueError("Identificador de prueba inválido.")
    s3 = boto3.client("s3")
    base = f"pruebas/recolector-seguro/{event['run_id']}/"
    evento = {"fecha": "2026-11-19"}

    def procesar(proxy, raw=HTML, ev=evento):
        return recolector.ejecutar(ev, proxy, lambda _: raw, ORIGEN)

    concurrente = RedirigirS3(s3, base + "concurrencia/")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        resultados = list(pool.map(lambda _: procesar(concurrente), range(5)))
    assert sum(r["bronze"] == "CREADO" for r in resultados) == 1
    assert sum(r["silver"] == "CREADO" for r in resultados) == 1
    assert sum(r["manifiesto"] == "CREADO" for r in resultados) == 1
    assert all(r["emision"] == "NO_HABILITADA" for r in resultados)
    try:
        procesar(concurrente, HTML + b"<!-- diferente -->")
    except recolector.ConflictoInmutable:
        pass
    else:
        raise AssertionError("No se bloqueó Bronze divergente.")
    assert procesar(concurrente)["silver"] == "IDENTICO"

    historial = RedirigirS3(s3, base + "historial/")
    procesar(historial, HTML.replace(b"19 Nov", b"18 Nov"), {"fecha": "2026-11-18"})
    historico = procesar(historial)
    assert historico["guardia"]["resumen_evidencia"]["CAPTURA_SEGURA_CONFIRMADA"] == 1
    assert historico["guardia"]["resumen_evidencia"]["COINCIDE_PPP_Y_HASH"] == 4

    # La API usa solo el snapshot sintético y el manifiesto de este prefijo.
    s3.put_object(Bucket=DESTINO, Key=base + "concurrencia/snapshot.csv", IfNoneMatch="*",
                  Body=b"fecha,emisora,serie,estado_captura,ppp_bmv_mxn\n2026-11-17,WALMEX,*,PPP_PUBLICADO_VERIFICADO,42\n")
    entorno = {"MERCADO_BUCKET": ORIGEN, "MERCADO_KEY": "snapshot.csv",
               "CAPTURAS_SEGURAS_HABILITADAS": "true"}
    anterior = {k: os.environ.get(k) for k in entorno}
    try:
        os.environ.update(entorno)
        fechas = api.ejecutar({"routeKey": "GET /api/mercado/fechas"}, None, concurrente)
        assert fechas["statusCode"] == 200
        assert json.loads(fechas["body"]) == ["2026-11-19", "2026-11-17"]
        resumen = api.ejecutar({"routeKey": "GET /api/mercado/resumen"}, None, concurrente)
        assert resumen["statusCode"] == 200 and json.loads(resumen["body"])["fecha"] == "2026-11-19"
        pagina = api.ejecutar({"routeKey": "GET /api/mercado/fechas",
                              "queryStringParameters": {"mes": "2026-11", "limite": "1"}}, None, historial)
        assert pagina["statusCode"] == 200
        assert json.loads(pagina["body"])["siguiente"] == "2026-11-18"
        segunda = api.ejecutar({"routeKey": "GET /api/mercado/fechas",
                               "queryStringParameters": {"mes": "2026-11", "limite": "1",
                                                         "despues": "2026-11-18"}}, None, historial)
        assert segunda["statusCode"] == 200 and json.loads(segunda["body"])["fechas"] == ["2026-11-19"]
    finally:
        for k, valor in anterior.items():
            if valor is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = valor

    parcial = RedirigirS3(s3, base + "parcial/")
    parcial.fallar_silver = True
    try:
        procesar(parcial)
    except RuntimeError:
        pass
    else:
        raise AssertionError("No se detectó error parcial.")
    reparado = procesar(parcial)
    assert reparado["bronze"] == "IDENTICO" and reparado["silver"] == "CREADO"

    solapada = RedirigirS3(s3, base + "fecha-solapada/")
    s3.put_object(Bucket=DESTINO, Key=base + "fecha-solapada/snapshot.csv", IfNoneMatch="*",
                  Body=b"fecha,emisora,serie,estado_captura,ppp_bmv_mxn\n2026-11-19,WALMEX,*,PPP_PUBLICADO_VERIFICADO,20\n")
    def guardia_fallida(*args):
        raise RuntimeError("Fallo simulado de guardia")
    try:
        recolector.ejecutar(evento, solapada, lambda _: HTML, ORIGEN, guardia=guardia_fallida)
    except RuntimeError:
        pass
    else:
        raise AssertionError("No se detectó error de guardia.")
    anterior = {k: os.environ.get(k) for k in entorno}
    try:
        os.environ.update(entorno)
        consulta = {"routeKey": "GET /api/mercado/resumen"}
        assert api.ejecutar(consulta, None, solapada)["statusCode"] == 503
        procesar(solapada)
        assert api.ejecutar(consulta, None, solapada)["statusCode"] == 200
        s3.put_object(Bucket=DESTINO, Key=base + "fecha-solapada/snapshot-conflicto.csv", IfNoneMatch="*",
                      Body=b"fecha,emisora,serie,estado_captura,ppp_bmv_mxn\n2026-11-19,WALMEX,*,PPP_PUBLICADO_VERIFICADO,42\n")
        os.environ["MERCADO_KEY"] = "snapshot-conflicto.csv"
        assert api.ejecutar(consulta, None, solapada)["statusCode"] == 503
        assert api.ejecutar({"routeKey": "GET /api/mercado/fechas"}, None, solapada)["statusCode"] == 503
    finally:
        for k, valor in anterior.items():
            if valor is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = valor

    def sin_boletin(url):
        raise urllib.error.HTTPError(url, 404, "No publicado", {}, None)
    try:
        recolector.ejecutar(evento, RedirigirS3(s3, base + "sin-boletin/"), sin_boletin, ORIGEN)
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
    else:
        raise AssertionError("Se aceptó un boletín ausente.")

    # Lectura exclusivamente del HTML histórico conservado; todos los Put se
    # canalizan por RedirigirS3 al bucket aislado.
    obj = s3.get_object(Bucket=ORIGEN, Key="bronze/2026/11/boletin_20261117.html")
    real = obj["Body"].read(recolector.MAX_BYTES + 1)
    resultado = procesar(RedirigirS3(s3, base + "bronze-real/"), real, {"fecha": "2026-11-17"})
    assert resultado["emision"] == "NO_HABILITADA"
    for caso in ("concurrencia", "parcial", "fecha-solapada", "bronze-real"):
        legado = s3.list_objects_v2(Bucket=DESTINO, Prefix=base + caso + "/silver/precios_ppp/", MaxKeys=1)
        assert not legado.get("Contents"), "La prueba escribió en el prefijo Silver legado."
    resumen = {"concurrencia": "OK", "duplicados": "OK", "divergencia": "OK", "api_fechas_resumen": "OK",
               "fecha_solapada_parcial_y_conflicto": "OK",
               "silver_legado_no_modificado": "OK",
               "historial_confirmado_y_paginacion": "OK",
               "recuperacion_parcial": "OK", "boletin_404": "OK",
               "bronze_real_20261117": "OK", "emision": resultado["emision"],
               "evidencia_bronze_real": resultado["guardia"]["resumen_evidencia"],
               "destino_aislado": DESTINO, "prefijo": base}
    print("PRUEBA_AISLADA_COMPLETADA " + json.dumps(resumen, sort_keys=True))
    return resumen
