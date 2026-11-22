"""Descargador y archivador auditable de Avisos de Derechos oficiales de BMV (Ola 1: 5 emisoras G2).

Descarga los PDFs oficiales publicados en ``www.bmv.com.mx/docs-pub/derechos/`` desde las páginas
corporativas oficiales de cada emisora G2 (AMX, FEMSA, GFNORTE, GMEXICO, WALMEX), los guarda de
forma inmutable (``IfNoneMatch='*'``) en S3 bajo ``evidencias/eventos_corporativos/v1/documentos/<EMISORA>/``,
extrae los campos oficiales del encabezado BMV mediante ``pypdf``, construye la cola conciliada
sin fabricar montos ni fechas y ejecuta la conciliación formal de ``conciliar_eventos_corporativos.py``.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prisma.data.evidencias_s3 import (
    BUCKET_PRODUCTIVO,
    escribir_inmutable,
    escribir_json_inmutable,
    leer_json,
    sha256_bytes,
    timestamp_slug,
)
from prisma.domain import bmv_core as core
from scripts.conciliar_eventos_corporativos import PREFIJO_EVENTOS, conciliar_eventos

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# IDs oficiales verificados en https://www.bmv.com.mx/api/searchservice/v1 (2026-11-21)
EMISORAS_G2_BMV = {
    "AMX": {"id_empresa": "6024", "serie": "B"},
    "FEMSA": {"id_empresa": "5305", "serie": "UBD"},
    "GFNORTE": {"id_empresa": "5433", "serie": "O"},
    "GMEXICO": {"id_empresa": "6008", "serie": "B"},
    "WALMEX": {"id_empresa": "5214", "serie": "*"},
}

# En México BMV migró de liquidación T+2 a T+1 el 2024-05-27.
FECHA_INICIO_T1_BMV = date(2024, 5, 27)


def _http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(5_000_001)


def _fecha_dmy_a_iso(texto: str | None) -> str | None:
    if not texto:
        return None
    m = re.search(r"(\d{2})[/-](\d{2})[/-](\d{4})", texto)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def _retroceder_sesiones_bmv(fecha_iso: str, sesiones: int) -> str:
    actual = date.fromisoformat(fecha_iso)
    restantes = sesiones
    while restantes > 0:
        actual -= timedelta(days=1)
        if core.calendario_verificado(actual.year):
            if core.es_sesion_bmv(actual):
                restantes -= 1
        elif actual.weekday() < 5:
            restantes -= 1
    return actual.isoformat()


def listar_avisos_derechos_html(html: str, anios: set[int] | None = None) -> list[dict]:
    """Extrae enlaces oficiales ``/docs-pub/derechos/*.pdf`` de la sección AVISOS DE DERECHOS."""
    idx = html.upper().find("AVISOS DE DERECHOS")
    if idx == -1:
        return []
    end = html.find("</table>", idx)
    bloque = html[idx:end + 8] if end != -1 else html[idx:idx + 40_000]
    resultados = []
    vistos = set()
    for tr in re.findall(r"<tr[^>]*>.*?</tr>", bloque, re.S | re.I):
        m_href = re.search(r'href=["\'](/docs-pub/derechos/[^"\']+\.pdf)["\']', tr, re.I)
        if not m_href:
            continue
        ruta = m_href.group(1)
        if ruta in vistos:
            continue
        vistos.add(ruta)
        tds = [
            re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", td)).strip()
            for td in re.findall(r"<td[^>]*>.*?</td>", tr, re.S | re.I)
        ]
        fecha_pub_raw = tds[0] if tds else ""
        fecha_pub_iso = _fecha_dmy_a_iso(fecha_pub_raw)
        if anios and fecha_pub_iso and int(fecha_pub_iso[:4]) not in anios:
            continue
        resultados.append({
            "fecha_publicacion_raw": fecha_pub_raw,
            "fecha_publicacion": fecha_pub_iso,
            "asunto": tds[1] if len(tds) > 1 else "",
            "ruta_bmv": ruta,
            "url_bmv": "https://www.bmv.com.mx" + ruta,
            "archivo": Path(ruta).name,
        })
    return resultados


def extraer_texto_pdf(raw_pdf: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw_pdf))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def parsear_aviso_derechos_texto(texto: str, serie_objetivo: str) -> dict:
    """Interpreta el encabezado oficial estandarizado del PDF 'Aviso de derechos' de BMV."""
    lineas = [re.sub(r"\s+", " ", l).strip() for l in texto.splitlines() if l.strip()]
    unido = "\n".join(lineas)

    def _valor_tras(etiqueta: str) -> str | None:
        m = re.search(rf"^{re.escape(etiqueta)}\s*(?:\n|\s+)(.+)$", unido, re.M | re.I)
        return m.group(1).strip() if m else None

    m_clave = re.search(r"CLAVE DE COTIZACI[ÓO]N\s+([A-Z0-9&._-]+)", unido, re.I)
    clave = m_clave.group(1).strip().upper() if m_clave else None

    tipo_derecho = _valor_tras("TIPO DE DERECHO")
    fecha_pago_raw = _valor_tras("FECHA DE PAGO")
    fecha_pago = _fecha_dmy_a_iso(fecha_pago_raw)

    # Extraer bloque completo de PROPORCIÓN hasta el siguiente encabezado BMV
    m_prop = re.search(
        r"PROPORCI[ÓO]N\s*\n(.*?)(?:\n(?:CUENTA Y EJERCICIO|REGLA DE PRORRATEO|LUGAR DE PAGO|DERECHOS)\b)",
        unido,
        re.S | re.I,
    )
    proporcion = re.sub(r"\s+", " ", m_prop.group(1)).strip() if m_prop else ""

    # Buscar fecha ex-derecho o ex-cupón explícita en el cuerpo si existe
    fecha_ex_explicita = None
    m_ex = re.search(
        r"(?:ex[\s-]?(?:derecho|cup[oó]n|dividendo))[^0-9]{0,50}(\d{2}[/-]\d{2}[/-]\d{4})",
        unido,
        re.I,
    )
    if m_ex:
        fecha_ex_explicita = _fecha_dmy_a_iso(m_ex.group(1))

    # Monto en efectivo para la serie objetivo (ej. SERIE(S) 'UBD' ... A MXN $ 2.014925)
    monto_mxn = None
    moneda = None
    serie_esc = re.escape(serie_objetivo)
    m_monto = re.search(
        rf"SERIE\(S\)\s*['\"]?{serie_esc}['\"]?[^;]*?\bA\s+(MXN|USD)\s*\$\s*([0-9]+(?:\.[0-9]+)?|\.[0-9]+)",
        proporcion,
        re.I,
    )
    if m_monto:
        moneda = m_monto.group(1).upper()
        valor = float(m_monto.group(2))
        if moneda == "MXN":
            monto_mxn = valor

    # Proporción de dividendo en acciones / split: "N ACCION(ES) ... X M ACCION(ES)"
    ratio_split = None
    m_acc = re.search(
        rf"([0-9]+(?:\.[0-9]+)?)\s+ACCION\(ES\)\s+DE\s+LA\s+SERIE\(S\)\s+NUEVA\(S\)\s*['\"]?{serie_esc}['\"]?.*?\bX\s+([0-9]+(?:\.[0-9]+)?)\s+ACCION\(ES\)",
        proporcion,
        re.I,
    )
    if m_acc and tipo_derecho and "ACCIONES" in tipo_derecho.upper():
        nuevas = float(m_acc.group(1))
        anteriores = float(m_acc.group(2))
        if nuevas > 0 and anteriores > 0:
            # Dividendo en acciones (N nuevas por cada M anteriores): factor de precio = M / (M + N)
            ratio_split = round(anteriores / (anteriores + nuevas), 8)

    return {
        "clave_cotizacion": clave,
        "tipo_derecho": tipo_derecho,
        "fecha_pago": fecha_pago,
        "fecha_ex_explicita": fecha_ex_explicita,
        "proporcion": proporcion,
        "moneda": moneda,
        "monto_mxn": monto_mxn,
        "ratio_split": ratio_split,
    }


def descargar_y_archivar_avisos_bmv(
    s3,
    bucket: str,
    *,
    emisoras: list[str] | None = None,
    anios: set[int] | None = None,
    fetcher=_http_get,
) -> list[dict]:
    """Descarga PDFs oficiales de BMV para emisoras G2 y los archiva inmutablemente en S3."""
    anios = anios or {2024, 2025, 2026}
    seleccion = emisoras or list(EMISORAS_G2_BMV.keys())
    catalogo = []

    for em in seleccion:
        cfg = EMISORAS_G2_BMV[em]
        url_corp = f"https://www.bmv.com.mx/es/emisoras/informcioncorporativa/{em}-{cfg['id_empresa']}-CGEN_CAPIT"
        html = fetcher(url_corp).decode("utf-8", errors="ignore")
        avisos = listar_avisos_derechos_html(html, anios=anios)
        for av in avisos:
            raw_pdf = fetcher(av["url_bmv"])
            if not raw_pdf.startswith(b"%PDF"):
                continue
            s3_key = f"{PREFIJO_EVENTOS}documentos/{em}/{av['archivo']}"
            res_s3 = escribir_inmutable(s3, bucket, s3_key, raw_pdf, "application/pdf")
            try:
                texto = extraer_texto_pdf(raw_pdf)
                parsed = parsear_aviso_derechos_texto(texto, cfg["serie"])
            except Exception as exc:
                parsed = {"error_parseo": str(exc)}
            catalogo.append({
                "emisora": em,
                "serie_objetivo": cfg["serie"],
                "id_empresa_bmv": cfg["id_empresa"],
                **av,
                "evidencia_s3_key": s3_key,
                "sha256_evidencia": res_s3["sha256"],
                "estado_s3": res_s3["estado"],
                "bytes": res_s3["bytes"],
                "parseo": parsed,
            })
    return catalogo


def _fecha_ex_derivada(aviso_parseado: dict, fecha_ex_yahoo: str) -> tuple[str | None, str]:
    if aviso_parseado.get("fecha_ex_explicita"):
        return aviso_parseado["fecha_ex_explicita"], "EXPLICITA_EN_PDF_BMV"
    fecha_pago = aviso_parseado.get("fecha_pago")
    if not fecha_pago:
        return None, "SIN_FECHA_PAGO"
    # Regla operativa BMV: liquidación T+1 desde 2024-05-27, T+2 anterior.
    # Si la fecha ex-derecho está 1..3 sesiones antes del pago y coincide con el ciclo vigente, se deriva.
    sesiones_ciclo = 1 if date.fromisoformat(fecha_pago) >= FECHA_INICIO_T1_BMV else 2
    candidata = _retroceder_sesiones_bmv(fecha_pago, sesiones_ciclo)
    # También verificar si el aviso paga 1 sesión después del ex-date (registro = pago - 1)
    if candidata == fecha_ex_yahoo:
        return candidata, f"DERIVADA_CICLO_BMV_T-{sesiones_ciclo}"
    # En algunos pagos BMV hay fecha de registro previa (T-2 incluso tras 2024-05-27); reportar candidata del ciclo sin forzar coincidencia.
    return candidata, f"DERIVADA_CICLO_BMV_T-{sesiones_ciclo}_REVISAR"


def cruzar_ola1_con_catalogo_bmv(cola_ola1: dict, catalogo_avisos: list[dict]) -> dict:
    """Cruza los 33 eventos Ola 1 contra PDFs oficiales descargados sin fabricar datos."""
    por_em: dict[str, list[dict]] = {}
    for av in catalogo_avisos:
        por_em.setdefault(av["emisora"], []).append(av)

    eventos_act = []
    emparejados = 0
    for ev in cola_ola1.get("eventos", []):
        nuevo = dict(ev)
        em = ev["emisora"]
        tipo = ev["tipo"]
        f_yahoo = date.fromisoformat(ev["fecha_ex_yahoo"])
        candidatos = []
        for av in por_em.get(em, []):
            p = av.get("parseo") or {}
            fp_str = p.get("fecha_pago")
            td = (p.get("tipo_derecho") or "").upper()
            if not fp_str:
                continue
            fp = date.fromisoformat(fp_str)
            delta_dias = (fp - f_yahoo).days
            if not (-1 <= delta_dias <= 12):
                continue
            if tipo == "DIVIDENDO":
                if ("DIVIDENDO EN EFECTIVO" in td or "REEMBOLSO" in td) and p.get("monto_mxn") is not None:
                    candidatos.append((abs(delta_dias), av))
            elif tipo == "SPLIT":
                if ("ACCIONES" in td or "SPLIT" in td) and p.get("ratio_split") is not None:
                    candidatos.append((abs(delta_dias), av))

        if not candidatos:
            eventos_act.append(nuevo)
            continue

        # Agrupar por fecha_pago más cercana (algunas emisoras como FEMSA/WALMEX emiten ordinario + extraordinario el mismo día)
        candidatos.sort(key=lambda x: x[0])
        mejor_fecha_pago = candidatos[0][1]["parseo"]["fecha_pago"]
        del_mismo_pago = [av for _, av in candidatos if av["parseo"]["fecha_pago"] == mejor_fecha_pago]

        # Elegir coincidencia más exacta (individual o suma si hay 2 avisos simultáneos distintos)
        elegido = del_mismo_pago[0]
        if tipo == "DIVIDENDO":
            monto_y = float(ev["monto_mxn_yahoo"])
            # Revisar si un aviso individual está más cerca que la suma de avisos del mismo día
            mejor_ind = min(del_mismo_pago, key=lambda a: abs(a["parseo"]["monto_mxn"] - monto_y))
            suma_mismo_pago = round(sum(a["parseo"]["monto_mxn"] for a in del_mismo_pago), 6)
            # Evitar sumar avisos duplicados/alcances con el mismo monto exacto
            montos_unicos = list({round(a["parseo"]["monto_mxn"], 6): a for a in del_mismo_pago}.values())
            suma_unicos = round(sum(a["parseo"]["monto_mxn"] for a in montos_unicos), 6)
            if len(montos_unicos) > 1 and abs(suma_unicos - monto_y) < abs(mejor_ind["parseo"]["monto_mxn"] - monto_y):
                monto_oficial = suma_unicos
                elegido = montos_unicos[0]
                nota_fuente = (
                    f"BMV Avisos de Derechos ({len(montos_unicos)} exhibiciones mismo pago {mejor_fecha_pago}: "
                    + ", ".join(a["archivo"] for a in montos_unicos) + ")"
                )
            else:
                monto_oficial = round(mejor_ind["parseo"]["monto_mxn"], 6)
                elegido = mejor_ind
                nota_fuente = f"BMV Aviso de Derechos {elegido['archivo']} (pago {mejor_fecha_pago})"
            f_ex_of, metodo_ex = _fecha_ex_derivada(elegido["parseo"], ev["fecha_ex_yahoo"])
            nuevo.update({
                "estado_verificacion": "EVIDENCIA_BMV_CARGADA",
                "evidencia_s3_key": elegido["evidencia_s3_key"],
                "sha256_evidencia": elegido["sha256_evidencia"],
                "fecha_ex_oficial": f_ex_of,
                "metodo_fecha_ex_oficial": metodo_ex,
                "fecha_pago_oficial": mejor_fecha_pago,
                "monto_oficial_mxn": monto_oficial,
                "fuente_oficial_descripcion": nota_fuente,
            })
            emparejados += 1
        elif tipo == "SPLIT":
            f_ex_of, metodo_ex = _fecha_ex_derivada(elegido["parseo"], ev["fecha_ex_yahoo"])
            nuevo.update({
                "estado_verificacion": "EVIDENCIA_BMV_CARGADA",
                "evidencia_s3_key": elegido["evidencia_s3_key"],
                "sha256_evidencia": elegido["sha256_evidencia"],
                "fecha_ex_oficial": f_ex_of,
                "metodo_fecha_ex_oficial": metodo_ex,
                "fecha_pago_oficial": mejor_fecha_pago,
                "ratio_split_oficial": elegido["parseo"]["ratio_split"],
                "fuente_oficial_descripcion": f"BMV Aviso de Derechos {elegido['archivo']} (pago {mejor_fecha_pago})",
            })
            emparejados += 1
        eventos_act.append(nuevo)

    return {
        **cola_ola1,
        "actualizado_en_utc": datetime.now(timezone.utc).isoformat(),
        "total_avisos_bmv_archivados": len(catalogo_avisos),
        "eventos_con_evidencia_bmv": emparejados,
        "panel_ajustado_habilitado": False,
        "eventos": eventos_act,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bucket", default=BUCKET_PRODUCTIVO)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--cola-key", default=PREFIJO_EVENTOS + "muestra_prioritaria_g2_2024_2026.json")
    p.add_argument("--guardar-s3", action="store_true")
    args = p.parse_args()

    import boto3
    s3 = boto3.client("s3", region_name=args.region)
    cola_base = leer_json(s3, args.bucket, args.cola_key)
    catalogo = descargar_y_archivar_avisos_bmv(s3, args.bucket)
    cola_cruzada = cruzar_ola1_con_catalogo_bmv(cola_base, catalogo)
    conciliacion = conciliar_eventos(s3, args.bucket, cola_cruzada)

    salida = {
        "avisos_bmv_archivados": len(catalogo),
        "eventos_ola1_totales": conciliacion["total_eventos"],
        "eventos_con_evidencia_bmv": cola_cruzada["eventos_con_evidencia_bmv"],
        "verificados_oficiales": conciliacion["verificados_oficiales"],
        "divergentes": conciliacion["divergentes"],
        "pendientes": conciliacion["pendientes"],
        "invalidos": conciliacion["invalidos"],
        "muestra_aprobada": conciliacion["muestra_aprobada"],
        "panel_ajustado_habilitado": conciliacion["panel_ajustado_habilitado"],
    }
    if args.guardar_s3:
        ts = timestamp_slug()
        salida["catalogo_s3"] = escribir_json_inmutable(
            s3, args.bucket, f"{PREFIJO_EVENTOS}catalogo_avisos_bmv_2024_2026_{ts}.json",
            {"version": 1, "generado_en_utc": datetime.now(timezone.utc).isoformat(), "total": len(catalogo), "avisos": catalogo},
        )
        salida["cola_conciliada_s3"] = escribir_json_inmutable(
            s3, args.bucket, f"{PREFIJO_EVENTOS}muestra_prioritaria_g2_2024_2026_bmv_{ts}.json",
            cola_cruzada,
        )
        salida["auditoria_conciliacion_s3"] = escribir_json_inmutable(
            s3, args.bucket, f"evidencias/auditorias/conciliacion_eventos_{ts}.json",
            conciliacion,
        )
    salida["detalle_resumen"] = [
        {
            "evento_id": d["evento_id"],
            "resultado": d["resultado"],
            "delta_factor": d.get("delta_factor"),
            "fecha_ex_coincide": d.get("fecha_ex_coincide"),
        }
        for d in conciliacion["detalle"]
    ]
    print(json.dumps(salida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
