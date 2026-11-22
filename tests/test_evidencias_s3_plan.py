"""Pruebas unitarias del plan de evidencias en S3, IPC-35 versionado, eventos G2, ventana limpia, 2027 y Yahoo."""
from __future__ import annotations

import hashlib
import json
import unittest
from datetime import date
from pathlib import Path

from prisma.data.evidencias_s3 import (
    BUCKET_PRODUCTIVO,
    ConflictoEvidenciaS3,
    escribir_inmutable,
    escribir_json_inmutable,
    estado_permiso_yahoo,
    verificar_permiso_yahoo,
)
from prisma.domain import bmv_core as core
from prisma.domain.catalogo_ipc import (
    ESTADO_MAPEO_CONFIRMADO,
    ESTADO_MAPEO_PROPUESTO,
    ESTADO_OFICIAL,
    cargar_catalogo_versionado,
    catalogo_naftrac_20261117,
    convertir_provisional_a_versionado,
)
from scripts.conciliar_eventos_corporativos import conciliar_eventos, construir_colas_g2
from scripts.incorporar_boletines_seguros_s3 import incorporar_en_s3, preparar_corte
from scripts.inicializar_evidencias_s3 import inicializar_en_s3
from scripts.validar_calendario_2027_s3 import validar_propuesta_2027
from scripts.verificar_habilitacion_yahoo import evaluar_habilitacion_yahoo
from scripts.verificar_ventana_limpia_s3 import calcular_racha_limpia, diagnosticar_html_boletin
from tests.test_recolector_seguro import S3
from tests.test_yahoo_secundario import payload as yahoo_payload

ROOT = Path(__file__).resolve().parents[1]

HTML_BOLETIN_20261020 = (
    "<html><body><p>Resumen de mercado 20 Oct 2026</p>"
    "<table>"
    "<tr><th>Emisora</th><th>Serie</th><th>Último</th><th>Anterior</th><th>PPP</th></tr>"
    "<tr><td>WALMEX</td><td>*</td><td>62.10</td><td>61.50</td><td>62.00</td></tr>"
    "<tr><td>AMX</td><td>B</td><td>15.20</td><td>15.00</td><td>15.10</td></tr>"
    "</table></body></html>"
).encode("utf-8")


class EvidenciasS3Test(unittest.TestCase):
    def test_escritura_inmutable_idempotente_y_rechaza_conflicto_o_prefijo(self):
        s3 = S3()
        r1 = escribir_inmutable(s3, BUCKET_PRODUCTIVO, "evidencias/prueba.txt", b"hola", "text/plain")
        self.assertEqual(r1["estado"], "CREADO")
        r2 = escribir_inmutable(s3, BUCKET_PRODUCTIVO, "evidencias/prueba.txt", b"hola", "text/plain")
        self.assertEqual(r2["estado"], "IDENTICO")
        with self.assertRaises(ConflictoEvidenciaS3):
            escribir_inmutable(s3, BUCKET_PRODUCTIVO, "evidencias/prueba.txt", b"otro", "text/plain")
        with self.assertRaises(ValueError):
            escribir_inmutable(s3, BUCKET_PRODUCTIVO, "gold/prohibido.json", b"{}", "application/json")

    def test_inicializar_evidencias_crea_prefijos_gobernanza_en_s3(self):
        s3 = S3()
        res = inicializar_en_s3(s3, BUCKET_PRODUCTIVO, fecha_iso="2026-11-21T23:00:00+00:00")
        self.assertEqual(res["gobernanza"]["estado"], "CREADO")
        self.assertEqual(res["yahoo_permiso"]["estado"], "CREADO")
        self.assertEqual(res["calendario_2027"]["estado"], "CREADO")
        self.assertEqual(res["catalogo_ipc_provisional"]["estado"], "CREADO")
        gob = json.loads(s3.objetos["evidencias/gobernanza/declaracion_fuentes.json"])
        self.assertFalse(gob["bmv"]["correspondencia_almacenada_en_chat_o_s3"])
        self.assertFalse(gob["observaciones_yahoo"]["habilitacion_productiva"])
        self.assertFalse(gob["calendario_bmv_2027"]["habilita_operacion"])


class CatalogoVersionadoTest(unittest.TestCase):
    def test_provisional_versionado_solo_cubre_su_corte(self):
        cat_dict = convertir_provisional_a_versionado(catalogo_naftrac_20261117())
        cat = cargar_catalogo_versionado(cat_dict)
        self.assertEqual(len(cat.en_fecha(date(2026, 11, 17))), 35)
        self.assertEqual(cat.alias_confirmados("yahoo", date(2026, 11, 17)), {})
        with self.assertRaises(ValueError):
            cat.en_fecha(date(2026, 11, 18))

    def test_oficial_exige_sha_s3_evidencia_y_bloquea_alias_sin_confirmar_y_solapamientos(self):
        sha = "a" * 64
        base = {
            "version": "ipc-oficial-2026-11-v1",
            "fecha_publicacion": "2026-11-01",
            "fecha_consulta": "2026-11-21",
            "estado_composicion": ESTADO_OFICIAL,
            "fuente": {"nombre": "S&P/BMV", "url": "https://example.org/ipc"},
            "evidencia_s3_key": "evidencias/catalogo_ipc/oficial_202611.pdf",
            "sha256_evidencia": sha,
            "componentes": [
                {
                    "instrumento_id": "BMV:R:A",
                    "emisora": "R",
                    "serie": "A",
                    "origen": "IPC_OFICIAL",
                    "vigente_desde": "2026-11-01",
                    "vigente_hasta": None,
                    "estado_mapeo": ESTADO_MAPEO_CONFIRMADO,
                    "alias": [
                        {"fuente": "blackrock", "simbolo": "RA", "estado": ESTADO_MAPEO_CONFIRMADO, "evidencia": "Constancia BMV"},
                        {"fuente": "yahoo", "simbolo": "RA.MX", "estado": ESTADO_MAPEO_CONFIRMADO, "evidencia": "Constancia Yahoo"},
                    ],
                },
            ],
        }
        cat = cargar_catalogo_versionado(base)
        self.assertEqual(cat.resolver_alias("blackrock", "ra", date(2026, 11, 21)).emisora, "R")
        self.assertEqual(cat.alias_confirmados("yahoo", date(2026, 11, 21)), {"R": "RA.MX"})

        # Alias sensible RA sin confirmar debe fallar en catálogo oficial.
        sin_ev = json.loads(json.dumps(base))
        sin_ev["componentes"][0]["alias"][0]["estado"] = ESTADO_MAPEO_PROPUESTO
        with self.assertRaises(ValueError):
            cargar_catalogo_versionado(sin_ev)

        # Solapamiento de intervalos para el mismo par debe fallar.
        solapado = json.loads(json.dumps(base))
        solapado["componentes"].append({**base["componentes"][0], "instrumento_id": "BMV:R:A:v2", "vigente_desde": "2026-11-15"})
        with self.assertRaises(ValueError):
            cargar_catalogo_versionado(solapado)


class IncorporacionBoletinesTest(unittest.TestCase):
    def test_preserva_hueco_instantanea_y_rechaza_discrepancia_ppp(self):
        sha = hashlib.sha256(HTML_BOLETIN_20261020).hexdigest()
        snap = [
            {"fecha": "2026-10-20", "emisora": "WALMEX", "serie": "*", "estado_captura": "PPP_PUBLICADO_VERIFICADO",
             "ppp_bmv_mxn": "62.0", "sha256_boletin": sha},
            {"fecha": "2026-10-20", "emisora": "AMX", "serie": "B", "estado_captura": "PPP_PUBLICADO_VERIFICADO",
             "ppp_bmv_mxn": "15.1", "sha256_boletin": sha},
            {"fecha": "2026-10-20", "emisora": "BIMBO", "serie": "A", "estado_captura": "NO_PUBLICADO_EN_BOLETIN_RSS_DEL_DIA",
             "ppp_bmv_mxn": "", "sha256_boletin": sha},
        ]
        corte = preparar_corte(HTML_BOLETIN_20261020, "2026-10-20", snap)
        self.assertEqual(corte["conciliacion"]["huecos_normalizados_legado"], 1)
        s3 = S3()
        rep = incorporar_en_s3(s3, BUCKET_PRODUCTIVO, [corte], aplicar=True)
        self.assertTrue(rep["cortes"][0]["verificado_lector_compartido"])
        self.assertIn("silver/capturas_seguras/2026/10/captura_20261020.json", s3.objetos)
        # Discrepancia de precio debe abortar sin escribir.
        snap_mal = [dict(snap[0], ppp_bmv_mxn="99.99"), snap[1]]
        with self.assertRaises(ValueError):
            preparar_corte(HTML_BOLETIN_20261020, "2026-10-20", snap_mal)


class EventosCorporativosTest(unittest.TestCase):
    def test_colas_y_conciliacion_recalcula_factor_sobre_ppp_bmv(self):
        colas = construir_colas_g2(
            ROOT / "eventos_corporativos_15_emisoras.csv",
            ROOT / "serie_ppp_historica_15_emisoras_bmv.csv",
        )
        self.assertEqual(colas["ola1"]["total"], 33)
        self.assertEqual(colas["ola2"]["total"], 85)
        self.assertFalse(colas["ola1"]["panel_ajustado_habilitado"])

        s3 = S3()
        doc = b"AVISO OFICIAL DIVIDENDO WALMEX"
        doc_key = "evidencias/eventos_corporativos/v1/documentos/WALMEX/aviso_1.pdf"
        doc_sha = hashlib.sha256(doc).hexdigest()
        s3.objetos[doc_key] = doc
        cola_sintetica = {
            "ola": "OLA_TEST",
            "eventos": [{
                "evento_id": "WALMEX_2025-05-02_DIVIDENDO",
                "emisora": "WALMEX",
                "fecha_ex_yahoo": "2025-05-02",
                "tipo": "DIVIDENDO",
                "factor_yahoo": 0.98,
                "ppp_bmv_previo": 50.0,
                "estado_verificacion": "VERIFICADO_OFICIAL",
                "evidencia_s3_key": doc_key,
                "sha256_evidencia": doc_sha,
                "fecha_ex_oficial": "2025-05-02",
                "monto_oficial_mxn": 1.0,
            }],
        }
        rep = conciliar_eventos(s3, BUCKET_PRODUCTIVO, cola_sintetica)
        self.assertTrue(rep["muestra_aprobada"])
        self.assertFalse(rep["panel_ajustado_habilitado"])
        self.assertEqual(rep["detalle"][0]["factor_recalculado_bmv"], 0.98)

        # Monto oficial distinto provoca divergencia y bloquea aprobación.
        cola_sintetica["eventos"][0]["monto_oficial_mxn"] = 2.5
        rep_div = conciliar_eventos(s3, BUCKET_PRODUCTIVO, cola_sintetica)
        self.assertFalse(rep_div["muestra_aprobada"])
        self.assertEqual(rep_div["divergentes"], 1)


class VentanaCalendarioYahooTest(unittest.TestCase):
    def test_diagnostico_mantenimiento_y_racha_ventana_limpia(self):
        mantenimiento = b"<html><head><title>Sitio Grupo BMV no disponible</title></head></html>"
        d_mant = diagnosticar_html_boletin(mantenimiento, "2026-11-20")
        self.assertTrue(d_mant["mantenimiento_detectado"])
        self.assertFalse(d_mant["boletin_valido"])

        d_ok = diagnosticar_html_boletin(HTML_BOLETIN_20261020, "2026-10-20")
        self.assertTrue(d_ok["boletin_valido"])

        racha = calcular_racha_limpia(["2026-10-20", "2026-11-20", "2026-11-23", "2026-11-24"], desde_iso="2026-11-20")
        self.assertEqual(racha["sesiones_consecutivas_confirmadas"], 3)
        self.assertEqual(racha["faltan_para_ventana_limpia"], 18)
        self.assertFalse(racha["ventana_limpia_completa"])

    def test_validador_calendario_2027_bloquea_sin_fuente_y_simula_frontera_con_evidencia(self):
        s3 = S3()
        rep_pend = validar_propuesta_2027(s3, BUCKET_PRODUCTIVO, {"anio": 2027, "estado": "PENDIENTE_FUENTE_OFICIAL"})
        self.assertFalse(rep_pend["valido_para_promocion"])

        pdf = b"%PDF-1.4 calendario bmv 2027"
        key = "evidencias/calendario_bmv/2027/calendario_oficial_2027.pdf"
        s3.objetos[key] = pdf
        prop = {
            "anio": 2027,
            "estado": "FUENTE_OFICIAL_CARGADA",
            "evidencia_s3_key": key,
            "sha256_evidencia": hashlib.sha256(pdf).hexdigest(),
            "feriados": ["2027-01-01", "2027-02-01", "2027-03-15"],
        }
        rep_ok = validar_propuesta_2027(s3, BUCKET_PRODUCTIVO, prop)
        self.assertTrue(rep_ok["valido_para_promocion"])
        self.assertFalse(rep_ok["habilita_operacion"])
        self.assertEqual(rep_ok["simulacion_frontera_2026_2027"]["sesiones_2026"] + rep_ok["simulacion_frontera_2026_2027"]["sesiones_2027"], 21)

    def test_compuerta_yahoo_bloquea_en_tramite_y_habilita_solo_con_permiso_y_archivo(self):
        s3 = S3()
        escribir_json_inmutable(s3, BUCKET_PRODUCTIVO, "evidencias/observaciones_yahoo/estado_permiso.json", estado_permiso_yahoo("2026-11-21T23:00:00+00:00"))
        ok, errs = verificar_permiso_yahoo(json.loads(s3.objetos["evidencias/observaciones_yahoo/estado_permiso.json"]))
        self.assertFalse(ok)
        self.assertTrue(errs)

        rep_bloq = evaluar_habilitacion_yahoo(s3, BUCKET_PRODUCTIVO)
        self.assertFalse(rep_bloq["listo_para_activar_produccion"])

        # Simular permiso aprobado y archivo archivado válido.
        s3.objetos["evidencias/observaciones_yahoo/estado_permiso.json"] = json.dumps({
            **estado_permiso_yahoo("2026-11-21T23:00:00+00:00"),
            "estado": "APROBADO",
            "habilitacion_permitida": True,
            "alcance_autorizado": "Licencia académica y web pública",
            "referencia_autorizacion": "DOC-YAH-2026",
        }).encode("utf-8")
        s3.objetos["observaciones/yahoo/WALMEX.MX/2026-11-19.json"] = yahoo_payload()
        rep_ok = evaluar_habilitacion_yahoo(s3, BUCKET_PRODUCTIVO)
        self.assertTrue(rep_ok["listo_para_activar_produccion"])

    def test_almacen_ipc35_y_estadistica_provisional_y_avance_automatico(self):
        import importlib
        from unittest.mock import patch
        from prisma.data.ipc35_almacen import (
            SIMBOLOS_YAHOO_IPC35,
            generar_resumen_avance_s3,
            guardar_corte_ipc35,
            leer_captura_ipc35,
            leer_manifiesto_ipc35,
        )
        from tests.test_api_gateway_aislada import Tabla

        self.assertEqual(len(SIMBOLOS_YAHOO_IPC35), 35)
        s3 = S3()
        html = (
            "<html><body><p>Resumen 17 Nov 2026</p><table>"
            "<tr><th>Emisora</th><th>Serie</th><th>Último</th><th>Anterior</th><th>PPP</th></tr>"
            "<tr><td>VOLAR</td><td>A</td><td>15.30</td><td>15.00</td><td>15.14</td></tr>"
            "</table></body></html>"
        ).encode("utf-8")
        res = guardar_corte_ipc35(s3, BUCKET_PRODUCTIVO, html, "2026-11-17", "https://www.bmv.com.mx/docs-pub/rss/boletin20261117.html")
        self.assertEqual(res["silver_ipc35"], "CREADO")
        self.assertEqual(res["observados_ppp"], 1)
        man = leer_manifiesto_ipc35(s3, BUCKET_PRODUCTIVO, "2026-11-17")
        _, filas = leer_captura_ipc35(s3, BUCKET_PRODUCTIVO, man)
        self.assertEqual(len(filas), 35)

        api = importlib.import_module("infra.api_gateway_aislada.handler")
        tabla = Tabla({"rol": "user", "plan": "explorer", "email": "e@example.org", "nombre": "E"})
        ev = {
            "routeKey": "GET /api/terminal/estadistica",
            "queryStringParameters": {"emisora": "VOLAR", "desde": "2026-11-01", "hasta": "2026-11-20", "universo": "ipc35_provisional"},
            "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "u", "token_use": "access"}}}},
        }
        with patch.dict("os.environ", {"MERCADO_BUCKET": BUCKET_PRODUCTIVO, "MERCADO_KEY": "k"}):
            resp = api.ejecutar(ev, tabla, s3)
            self.assertEqual(resp["statusCode"], 200)
            body = json.loads(resp["body"])
            self.assertEqual(body["metodologia"]["estado_composicion"], "PROVISIONAL_NO_OFICIAL")
            self.assertFalse(body["metodologia"]["inferencia_habilitada"])
            self.assertEqual(body["estadisticas_historico_verificado"][0]["n_valido"], 1)
            self.assertEqual(body["estadisticas_historico_verificado"][0]["media"], 15.14)

        av = generar_resumen_avance_s3(s3, BUCKET_PRODUCTIVO, "2026-11-20", "a" * 64, "b" * 64, {"SILVER_AUSENTE": 0})
        self.assertIn("evidencias/operacion/cortes/avance_20261120.json", s3.objetos)
        self.assertIn("evidencias/operacion/avance_ventana_limpia.json", s3.objetos)
        self.assertEqual(av["emision"], "NO_HABILITADA")


if __name__ == "__main__":
    unittest.main()
