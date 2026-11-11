"""Normalización, analítica de dashboards, consola SQL y guardrails de Prismi."""

import pandas as pd
import pytest

from prisma.data import analytics as an
from prisma.data.athena import ErrorSQL, MotorSQLLocal, validar_sql_lectura
from prisma.data.repository import RepositorioLocal
from prisma.domain import bmv_core as core
from prisma.services import prismi
from tests.conftest import DATOS


@pytest.fixture(scope="module")
def repo():
    r = RepositorioLocal(DATOS)
    return {"precios": r.precios(), "g2": r.senales_g2(), "g1": r.senales_g1(), "modelos": r.modelos_g2()}


def test_normalizacion_lista_oficial_y_etiqueta_unica(repo):
    p = repo["precios"]
    assert p.groupby("fecha").size().eq(15).all()
    assert set(p["estado_captura"]) == {core.ESTADO_PUBLICADO, core.ESTADO_HUECO}
    assert not {"GCARSO", "KOF", "ORBIA"} & set(p["emisora"])
    assert p[p["estado_captura"] == core.ESTADO_HUECO]["ppp_bmv_mxn"].isna().all()


def test_retraso_de_explorer(repo):
    assert an.fechas_disponibles(repo["precios"], 1)[0] == "2026-10-29"
    assert an.fechas_disponibles(repo["precios"], 0)[0] == "2026-10-30"


def test_kpis_sesion(repo):
    k = an.kpis_sesion(repo["precios"][repo["precios"]["fecha"] == "2026-10-30"])
    assert k["total"] == 15 and k["verificadas"] + k["huecos"] == 15


def test_marcador_reproduce_resumen_oficial(repo):
    seg = an.seguimiento(repo["g1"].iloc[0:0], repo["g2"], repo["precios"], "2026-10-30")
    m = an.marcador_modelos(seg).set_index("modelo")
    assert m.loc["G2-V1 Calibrado", "aciertos_parciales"] == 2
    assert m.loc["G2-V2 Zona neutral", "aciertos_parciales"] == 3
    assert m.loc["G2-V3 Alta discriminación", "aciertos_parciales"] == 4
    assert (m["en_seguimiento"] == 8).all()


def test_consenso_registrado_es_coherente(repo):
    assert an.inconsistencias_consenso(repo["g2"]).empty
    assert an.canonizar_consenso("DIVERGENCIA_G2 (V1=SUBIDA, V2=NO_SUBIDA, V3=SUBIDA)") == an.DIVERGENCIA
    assert an.canonizar_consenso("CONSENSO_PANEL_G2_NO_SUBIDA") == an.NO_SUBIDA


def test_factor_clave_en_puntos_porcentuales(repo):
    fila = repo["g2"][(repo["g2"]["emisora"] == "GMEXICO") & (repo["g2"]["fecha_senal"] == "2026-10-30")].iloc[0]
    e = an.explicar_factor(repo["modelos"], fila)
    assert e.ret_rel_pct == pytest.approx(-9.4697, abs=1e-3)
    assert e.z_rel < -1.5 and "reversión a la media" in e.lectura


def test_g1_anulada_excluida(repo):
    t = an.tabla_probabilidades(repo["g1"], repo["g2"], "WALMEX", "2026-10-28", True, False)
    assert (~t["valida"]).sum() == 1
    assert an.consenso_por_generacion(t)["G1"] == an.DIVERGENCIA


def test_trayectoria_sin_interpolar(repo):
    t = an.trayectoria(repo["precios"], "WALMEX", "2026-10-28", "2026-11-05", 48.40)
    assert list(t["paso"]) == ["t0", "t+1", "t+2", "t+3", "t+4", "t+5"]
    assert t.iloc[2]["retorno_pct"] == pytest.approx(4.1116, abs=1e-3)
    assert (t.iloc[3:]["estado"] == "FUTURO").all() and t.iloc[3:]["retorno_pct"].isna().all()


# --- Consola SQL ---------------------------------------------------------------
@pytest.mark.parametrize("sql", [
    "DROP TABLE bmv_silver_ppp", "SELECT 1; DELETE FROM bmv_silver_ppp", "SELECT * FROM information_schema.tables",
    "SELECT * FROM read_csv('/etc/passwd')", "INSERT INTO bmv_silver_ppp VALUES (1)", "",
])
def test_guardia_sql_rechaza(sql):
    with pytest.raises(ErrorSQL):
        validar_sql_lectura(sql, 100)


def test_guardia_sql_acepta_cte_y_limita():
    s = validar_sql_lectura("-- comentario\nWITH x AS (SELECT * FROM bmv_silver_ppp) SELECT * FROM x;", 50)
    assert s.endswith("LIMIT 50")


def test_motor_local_bloquea_archivos(repo):
    m = MotorSQLLocal({"bmv_silver_ppp": repo["precios"]})
    assert len(m.ejecutar("SELECT * FROM bmv_silver_ppp").datos) == len(repo["precios"])
    with pytest.raises(ErrorSQL):
        m.ejecutar("SELECT * FROM read_csv('/etc/passwd')")


# --- Prismi ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def ctx(repo):
    seg = an.seguimiento(repo["g1"], repo["g2"], repo["precios"], "2026-10-30")
    return prismi.construir_contexto(repo["precios"], repo["g1"], repo["g2"], seg, ("WALMEX", "GMEXICO", "GFNORTE", "AMX"))


@pytest.mark.parametrize("q", ["Dame una receta de pozole", "¿Quién ganará las elecciones?", "¿Compro Bitcoin?"])
def test_prismi_rechaza_temas_externos(q, ctx):
    r = prismi.responder(q, [], ctx, "professional", "", "m", False)
    assert r.origen == "GUARDRAIL" and r.texto == prismi.MENSAJE_FRONTERA


def test_prismi_no_da_asesoria(ctx):
    r = prismi.responder("¿Debo comprar GMEXICO hoy?", [], ctx, "professional", "", "m", False)
    assert r.origen == "GUARDRAIL" and r.texto.startswith(prismi.MENSAJE_NO_ASESORIA)


def test_prismi_responde_con_cifras_reales(ctx):
    r = prismi.responder("¿Cuál es la señal de GMEXICO?", [], ctx, "professional", "", "m", False)
    assert "-9.47 pp" in r.texto and "CONSENSO_ALTO_SUBIDA" in r.texto and "224.31" in r.texto


def test_prismi_explorer_no_ve_emisoras_bloqueadas(repo):
    ctx = prismi.construir_contexto(repo["precios"], repo["g1"], repo["g2"], pd.DataFrame(), ("WALMEX",))
    assert "GMEXICO" not in ctx.texto


def test_prompt_de_sistema_incluye_reglas(ctx):
    p = prismi.prompt_sistema(ctx, "explorer")
    assert prismi.MENSAJE_FRONTERA in p and "Nunca des órdenes" in p and "Explorer" in p
