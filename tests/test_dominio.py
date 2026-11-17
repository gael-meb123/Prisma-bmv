"""Núcleo cuantitativo: calendario, parser, cero imputación, paridad con el registro oficial."""

import numpy as np
import pandas as pd
import pytest

from prisma.domain import bmv_core as core


# --- Calendario ---------------------------------------------------------------
def test_t5_salta_feriado_2_de_noviembre():
    assert core.sumar_sesiones("2026-10-28", 5) == "2026-11-05"
    assert core.sumar_sesiones("2026-10-30", 5) == "2026-11-09"


def test_ventana_21_termina_en_corte_y_omite_feriados():
    v = core.ultimas_sesiones("2026-10-28", 21)
    assert len(v) == 21 and v[-1] == "2026-10-28" and v[0] == "2026-09-30"
    assert "2026-09-16" not in core.ultimas_sesiones("2026-10-01", 21)


def test_anio_sin_calendario_queda_marcado_como_provisional():
    assert core.calendario_verificado(2026)
    assert not core.calendario_verificado(2031)
    assert core.calendario_objetivo("2031-03-03", "2031-03-10").startswith("PROVISIONAL")


# --- Parser del boletín ------------------------------------------------------
def test_parser_extrae_ppp_y_desescapa_entidades(html_prueba):
    q = core.parse_bulletin_quotes(html_prueba)
    assert q[("WALMEX", "*")]["ppp"] == 50.39  # primera aparición, no la de la segunda tabla
    assert q[("PE&OLES", "*")]["ppp"] == 785.76
    assert q[("GMEXICO", "B")]["variacion_ppp_vs_anterior_pct"] == round((224.31 / 233.70 - 1) * 100, 2)


def test_parser_descarta_columna_desplazada_y_tabla_de_paquetes(html_prueba):
    q = core.parse_bulletin_quotes(html_prueba)
    assert ("CEMEX", "CPO") not in q  # el "PPP" era la variación porcentual
    assert all(v["ppp"] != 9.99 for v in q.values())


def test_silver_siempre_15_filas_sin_imputar(html_prueba):
    filas = core.registros_silver("2026-10-30", core.parse_bulletin_quotes(html_prueba), "u", "h")
    df = pd.DataFrame(filas)
    assert len(df) == 15
    huecos = df[df["estado_captura"] == core.ESTADO_HUECO]
    assert len(huecos) == 10 and huecos["ppp_bmv_mxn"].isna().all()
    assert list(pd.DataFrame(filas)[list(core.COLUMNAS_SILVER)].columns) == list(core.COLUMNAS_SILVER)


# --- Cero imputación ---------------------------------------------------------
def test_features_exigen_21_precios_validos():
    with pytest.raises(ValueError):
        core.calcular_features_ppp([10.0] * 20)
    with pytest.raises(ValueError):
        core.calcular_features_ppp([10.0] * 20 + [np.nan])


def test_un_hueco_en_la_ventana_bloquea_la_emisora(serie):
    s = serie.copy()
    mask = (s["emisora"] == "AMX") & (s["fecha"] == "2026-10-15")
    s.loc[mask, "estado_captura"] = core.ESTADO_HUECO
    s.loc[mask, "ppp_bmv_mxn"] = np.nan
    est, eleg = core.extraer_ventanas_panel(s, "2026-10-28")
    fila = est.set_index("emisora").loc["AMX"]
    assert not fila["ventana_21_completa_apta_inferencia"]
    assert fila["fechas_huecos_ventana_21"] == "2026-10-15"
    assert "AMX" not in set(eleg["emisora"])


# --- Paridad con el monitor oficial -------------------------------------------
@pytest.mark.parametrize("fecha", ["2026-10-28", "2026-10-29", "2026-10-30"])
def test_features_e_inferencia_reproducen_el_registro(fecha, serie, g2_registrado, modelos):
    _, eleg = core.extraer_ventanas_panel(serie, fecha)
    filas = core.inferir_panel_g2(eleg, modelos, fecha, "h", "u", "t")
    assert len(filas) == 12
    reg = g2_registrado.set_index("id_senal_g2")
    for f in filas:
        r = reg.loc[f["id_senal_g2"]]
        for v in ("ret_10", "ret_10_rel_panel", "volatilidad_20", "ppp_base_t"):
            assert f[v] == pytest.approx(r[v], abs=1e-9)
        tol = 1e-6 if "V3" in f["modelo_g2"] else 2e-3
        assert f["probabilidad_subida"] == pytest.approx(r["probabilidad_subida"], abs=tol)


def test_contribuciones_suman_el_log_odds(modelos):
    x = {"ret_10": 0.02, "ret_10_rel_panel": -0.09, "volatilidad_20": 0.018}
    m = modelos["G2_V1_POOLED_REL3_CALIBRADO"]
    z = sum(core.contribuciones_log_odds(m, "GMEXICO", x).values())
    assert 1 / (1 + np.exp(-z)) == pytest.approx(core.probabilidad_g2(m, "GMEXICO", x))


def test_sin_escalador_oficial_no_hay_inferencia(modelos):
    eleg = pd.DataFrame([{"emisora": "ASUR", "ppp_t": 1.0, "ret_10": 0, "ret_10_rel_panel": 0,
                          "volatilidad_20": 0.01, "media_ret_10_panel_corte": 0,
                          "inicio_ventana_21": "a", "fin_ventana_21": "b"}])
    assert core.inferir_panel_g2(eleg, modelos, "2026-10-30", "h", "u", "t") == []


# --- Seguimiento t+1 ... t+5 -------------------------------------------------
def test_seguimiento_reproduce_registro(serie, g2_registrado):
    u = core.actualizar_seguimiento(g2_registrado, serie, "2026-10-30")
    pd.testing.assert_series_equal(u["retorno_parcial_pct"].astype(float), g2_registrado["retorno_parcial_pct"].astype(float),
                                   check_names=False)
    assert (u["estado_resolucion"] == g2_registrado["estado_resolucion"]).all()
    assert list(u["acierto_parcial_en_curso"].map(core._a_bool)) == list(g2_registrado["acierto_parcial_en_curso"].map(core._a_bool))


def _senal(clase, prob=0.6):
    return pd.DataFrame([{"id_senal_g2": "x", "fecha_senal": "2026-10-28", "fecha_objetivo_h5": "2026-11-05",
                          "emisora": "WALMEX", "ppp_base_t": 48.40, "probabilidad_subida": prob,
                          "prediccion_clase": clase, "estado_resolucion": "PENDIENTE_T+5"}])


def _serie_con(fecha, ppp):
    estado = core.ESTADO_PUBLICADO if ppp is not None else core.ESTADO_HUECO
    return pd.DataFrame([{"fecha": fecha, "emisora": "WALMEX", "estado_captura": estado, "ppp_bmv_mxn": ppp}])


def test_resuelve_en_t5_con_brier(serie):
    s = pd.concat([serie, _serie_con("2026-11-05", 49.00)], ignore_index=True)
    r = core.actualizar_seguimiento(_senal(1, 0.6), s, "2026-11-05").iloc[0]
    assert r["estado_resolucion"] == "RESUELTA_T+5"
    assert r["target_y_observado"] == 1 and r["acierto_direccional_t5"] == 1
    assert r["brier_observado_t5"] == pytest.approx((0.6 - 1) ** 2)


def test_hueco_en_t5_no_se_sustituye(serie):
    s = pd.concat([serie, _serie_con("2026-11-04", 51.0), _serie_con("2026-11-05", None)], ignore_index=True)
    r = core.actualizar_seguimiento(_senal(1), s, "2026-11-05").iloc[0]
    assert r["estado_resolucion"] == "NO_EVALUABLE_HUECO_EN_T+5"
    assert pd.isna(r.get("ppp_t5_observado"))
    assert r["ppp_parcial_reciente"] == 51.0  # el parcial sí usa el último PPP observado


def test_seguimiento_es_idempotente(serie, g2_registrado):
    a = core.actualizar_seguimiento(g2_registrado, serie, "2026-10-30")
    b = core.actualizar_seguimiento(a, serie, "2026-10-30")
    pd.testing.assert_frame_equal(a, b)
