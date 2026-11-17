"""Enterprise - Consola SQL (Athena), exportación masiva y auditoría forense SHA-256."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from prisma.data import analytics as an
from prisma.data.athena import ErrorSQL, MotorSQLLocal, validar_sql_lectura
from prisma.data.integrity import verificar_bronze, verificar_contra_fuente
from prisma.data.repository import RepositorioAthena, RepositorioLocal, RepositorioS3
from prisma.plans import tiene_acceso
from prisma.ui import components as ui
from prisma.ui.contexto import Servicios, VistaPlan

COSTO_ATHENA_USD_TB = 5.0
MINIMO_FACTURABLE_BYTES = 10 * 1024 * 1024

CONSULTAS_EJEMPLO = {
    "Últimas 20 cotizaciones verificadas de WALMEX": (
        "SELECT fecha, emisora, ppp_bmv_mxn, variacion_ppp_vs_anterior_pct, sha256_boletin\n"
        "FROM bmv_silver_ppp\nWHERE emisora = 'WALMEX' AND estado_captura = 'PPP_PUBLICADO_VERIFICADO'\n"
        "ORDER BY fecha DESC\nLIMIT 20"
    ),
    "Huecos documentados por emisora": (
        "SELECT emisora, COUNT(*) AS huecos\nFROM bmv_silver_ppp\n"
        "WHERE estado_captura = 'NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA'\nGROUP BY emisora\nORDER BY huecos DESC"
    ),
    "Consenso G2 de la última fecha": (
        "SELECT emisora, modelo_g2, probabilidad_subida, prediccion_etiqueta, estado_consenso_g2\n"
        "FROM bmv_gold_senales_g2\nWHERE fecha_senal = (SELECT MAX(fecha_senal) FROM bmv_gold_senales_g2)\n"
        "ORDER BY emisora, modelo_g2"
    ),
    "Señales G2 con rezago relativo mayor a 5 pp": (
        "SELECT fecha_senal, emisora, ROUND(ret_10_rel_panel * 100, 2) AS rel_pp,\n"
        "       ROUND(AVG(probabilidad_subida), 4) AS prob_media\n"
        "FROM bmv_gold_senales_g2\nWHERE ret_10_rel_panel < -0.05\nGROUP BY fecha_senal, emisora, ret_10_rel_panel\n"
        "ORDER BY fecha_senal DESC"
    ),
}


def _tablas_locales(datos: dict) -> dict[str, pd.DataFrame]:
    silver = datos["precios"].copy()
    silver["anio"] = silver["fecha"].str[:4].astype(int)
    silver["mes"] = silver["fecha"].str[5:7].astype(int)
    g2 = datos["g2"].copy()
    return {"bmv_silver_ppp": silver, "bmv_gold_senales_g2": g2,
            "bmv_gold_senales_g1": datos["g1"].copy(), "v_senales_g2_tipadas": g2}


def _costo(bytes_escaneados: int | None) -> str:
    if bytes_escaneados is None:
        return "—"
    facturable = max(bytes_escaneados, MINIMO_FACTURABLE_BYTES)
    return f"${facturable / 1024 ** 4 * COSTO_ATHENA_USD_TB:.6f} USD"


def _consola_sql(sv: Servicios, datos: dict) -> None:
    usa_athena = isinstance(sv.repo, RepositorioAthena)
    motor = sv.repo.cliente_athena if usa_athena else MotorSQLLocal(_tablas_locales(datos))
    if not usa_athena:
        st.caption("Motor activo: DuckDB local con las mismas tablas que Athena. Configure "
                   "PRISMA_DATA_SOURCE=athena para consultar el lakehouse en AWS.")
    else:
        st.caption(f"Motor activo: Amazon Athena, base {sv.settings.athena_database}, "
                   f"workgroup {sv.settings.athena_workgroup}.")

    ejemplo = st.selectbox("Consulta de ejemplo", list(CONSULTAS_EJEMPLO), key="lk_ej")
    sql = st.text_area("SQL (solo lectura)", CONSULTAS_EJEMPLO[ejemplo], height=170, key=f"lk_sql_{ejemplo}")
    if st.button("Ejecutar consulta", type="primary", key="lk_run"):
        try:
            seguro = validar_sql_lectura(sql, sv.settings.athena_max_filas)
            with st.spinner("Ejecutando…"):
                res = motor.ejecutar(seguro)
        except ErrorSQL as e:
            st.error(str(e))
            return
        m = st.columns(4)
        m[0].metric("Filas", f"{len(res.datos):,}")
        m[1].metric("Tiempo", f"{res.milisegundos or 0:,} ms")
        m[2].metric("Datos escaneados", "—" if res.bytes_escaneados is None else f"{res.bytes_escaneados / 1024:,.1f} KB")
        m[3].metric("Costo estimado", _costo(res.bytes_escaneados))
        st.dataframe(res.datos, hide_index=True)
        st.download_button("Descargar resultado (CSV)", res.datos.to_csv(index=False).encode(),
                           "consulta_prisma_bmv.csv", "text/csv", key="lk_dl_q")


def _exportacion(datos: dict) -> None:
    conjuntos = {
        "silver_precios_ppp": datos["precios"],
        "gold_senales_g2": datos["g2"],
        "gold_senales_g1": datos["g1"],
    }
    formato = st.segmented_control("Formato", ["CSV", "Parquet", "JSON"], default="Parquet", key="lk_fmt")
    sel = st.multiselect("Conjuntos", list(conjuntos), default=list(conjuntos), key="lk_sets")
    if not sel or not formato:
        return
    buf = io.BytesIO()
    manifiesto = {"generado_utc": datetime.now(timezone.utc).isoformat(), "formato": formato, "archivos": []}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre in sel:
            df = conjuntos[nombre]
            if formato == "CSV":
                contenido, ext = df.to_csv(index=False).encode(), "csv"
            elif formato == "JSON":
                contenido, ext = df.to_json(orient="records", force_ascii=False, indent=1).encode(), "json"
            else:
                b = io.BytesIO()
                df.to_parquet(b, index=False)
                contenido, ext = b.getvalue(), "parquet"
            archivo = f"{nombre}.{ext}"
            z.writestr(archivo, contenido)
            manifiesto["archivos"].append({"archivo": archivo, "filas": len(df),
                                           "sha256": hashlib.sha256(contenido).hexdigest()})
        z.writestr("MANIFIESTO.json", json.dumps(manifiesto, ensure_ascii=False, indent=2))
    st.dataframe(pd.DataFrame(manifiesto["archivos"]), hide_index=True)
    st.download_button(f"Descargar paquete ({formato})", buf.getvalue(), "prisma_bmv_export.zip",
                       "application/zip", type="primary", key="lk_dl_zip")
    st.caption("El manifiesto incluye el SHA-256 de cada archivo para verificar el paquete después de transferirlo.")


def _forense(sv: Servicios, datos: dict, vp: VistaPlan) -> None:
    fecha = st.selectbox("Sesión", vp.fechas, key="lk_fs")
    sesion = datos["precios"][datos["precios"]["fecha"] == fecha]
    firmas = an.firmas_sesion(sesion)
    for h in firmas["hashes"]:
        ui.html(f'<div class="pb-panel" style="margin-bottom:.4rem"><div class="pb-kpi-l">Firma en Silver</div>'
                f'<div class="pb-hash">{h}</div></div>')
    if not firmas["hashes"]:
        st.info("La sesión no tiene firma registrada.")
        return
    sha = firmas["hashes"][0]
    ymd = fecha.replace("-", "")

    a, b = st.columns(2)
    if a.button("Verificar contra Bronze", key="lk_vb"):
        if isinstance(sv.repo, RepositorioS3):
            html_b, side = sv.repo.bronze(ymd)
        elif isinstance(sv.repo, RepositorioLocal):
            html_b, side = sv.repo.bronze_local(ymd)
        else:
            html_b, side = None, None
        r = verificar_bronze(sha, html_b, side)
        (st.success if r.estado == "COINCIDE" else st.warning)(f"{r.estado}: {r.detalle}")
    if b.button("Verificar contra bmv.com.mx", key="lk_vf"):
        with st.spinner("Descargando el boletín oficial…"):
            r = verificar_contra_fuente(firmas["url"] or "", sha)
        {"COINCIDE": st.success, "NO_COINCIDE": st.warning}.get(r.estado, st.error)(f"{r.estado}: {r.detalle}")
        if r.sha_calculado:
            ui.html(f'<div class="pb-hash">recalculado: {r.sha_calculado}</div>')


def render(sv: Servicios, datos: dict, vp: VistaPlan) -> None:
    if not tiene_acceso(vp.plan, "lakehouse_athena"):
        ui.bloqueo("lakehouse_athena",
                   "Consultas SQL directas sobre las capas Silver y Gold en Amazon Athena, exportación masiva en "
                   "CSV, Parquet o JSON con manifiesto de firmas y verificación forense de cada boletín.", "lk")
        return
    t1, t2, t3 = st.tabs(["Consola SQL", "Exportación masiva", "Auditoría forense SHA-256"])
    with t1:
        _consola_sql(sv, datos)
    with t2:
        _exportacion(datos)
    with t3:
        _forense(sv, datos, vp)
