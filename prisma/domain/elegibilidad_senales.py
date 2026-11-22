"""Regla conservadora para inferencia; no calcula ni publica predicciones."""
import math
from datetime import date
from urllib.parse import urlsplit


def evaluar_ventanas(filas, sesiones, emisoras):
    """Evalúa ventanas de 21 sesiones dadas por un calendario ya verificado.

    La regla comprueba metadatos declarados, no la autenticidad del boletín,
    modelos, eventos corporativos ni los derechos de uso.
    """
    if len(sesiones) != 21 or len(set(sesiones)) != 21 or sorted(sesiones) != list(sesiones):
        raise ValueError("Se requieren 21 sesiones distintas y ordenadas.")
    for fecha in sesiones:
        if date.fromisoformat(fecha).isoformat() != fecha:
            raise ValueError("Sesión inválida.")
    if not emisoras or len(set(emisoras)) != len(emisoras):
        raise ValueError("Emisoras inválidas o duplicadas.")
    indice = {}
    for fila in filas:
        clave = (fila.get("fecha"), fila.get("emisora"))
        if clave[0] not in sesiones or clave[1] not in emisoras:
            continue
        indice.setdefault(clave, []).append(fila)
    salida = {}
    for emisora in emisoras:
        errores = []
        series = set()
        for fecha in sesiones:
            candidatos = indice.get((fecha, emisora), [])
            if len(candidatos) != 1:
                errores.append({"fecha": fecha, "motivo": "AUSENTE" if not candidatos else "AMBIGUA"})
                continue
            fila = candidatos[0]
            try:
                precio = float(fila.get("ppp_bmv_mxn"))
            except (TypeError, ValueError):
                precio = 0
            if fila.get("estado_captura") != "PPP_PUBLICADO_VERIFICADO":
                motivo = "FUENTE_NO_OFICIAL"
            elif not math.isfinite(precio) or precio <= 0:
                motivo = "PRECIO_INVALIDO"
            else:
                sha = fila.get("sha256_boletin")
                url = fila.get("url_fuente")
                serie = fila.get("serie")
                try:
                    fuente = urlsplit(url or "")
                    ruta_esperada = f"/docs-pub/rss/boletin{fecha.replace('-', '')}.html"
                    origen_ok = (fuente.scheme == "https" and fuente.hostname == "www.bmv.com.mx"
                                 and fuente.path == ruta_esperada and not fuente.query and not fuente.fragment
                                 and not fuente.username and not fuente.password and fuente.port in (None, 443))
                except ValueError:
                    origen_ok = False
                if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                    motivo = "SIN_HUELLA_VALIDA"
                elif not origen_ok:
                    motivo = "ORIGEN_NO_BMV"
                elif not isinstance(serie, str) or not serie.strip():
                    motivo = "SERIE_AUSENTE"
                else:
                    series.add(serie.strip())
                    continue
            errores.append({"fecha": fecha, "motivo": motivo})
        if len(series) > 1:
            errores.append({"fecha": None, "motivo": "CAMBIO_DE_SERIE_NO_VALIDADO"})
        salida[emisora] = {"ventana_apta": not errores, "errores": errores}
    aptas = sum(v["ventana_apta"] for v in salida.values())
    for resultado in salida.values():
        resultado["apta_modelo_relativo"] = resultado["ventana_apta"] and aptas >= 2
    return salida
