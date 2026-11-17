"""API de la terminal web (/api/terminal/*): plan, cero imputación, paridad y guardrails de Prismi."""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("dotenv")
from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
from core.supabase_auth import Usuario, usuario_actual  # noqa: E402


@pytest.fixture
def cliente():
    def con_plan(plan: str) -> TestClient:
        api.app.dependency_overrides[usuario_actual] = lambda: Usuario("t", "t@x", "Test", "user", plan)
        return TestClient(api.app)

    yield con_plan
    api.app.dependency_overrides.clear()


def test_endpoints_publicos_sin_sesion():
    c = TestClient(api.app)
    assert c.get("/api/terminal/sectores").status_code == 200
    g = c.get("/api/terminal/gobernanza").json()
    assert len(g["nodos"]) == 10 and all(0 <= e["destino"] < 10 for e in g["enlaces"])
    assert c.get("/api/terminal/serie?emisora=WALMEX").status_code == 401


def test_explorer_solo_ve_walmex(cliente):
    c = cliente("explorer")
    assert c.get("/api/terminal/serie?emisora=WALMEX").status_code == 200
    for ruta in ("serie", "senal", "seguimiento"):
        assert c.get(f"/api/terminal/{ruta}?emisora=GMEXICO").status_code == 403
    assert c.get("/api/terminal/marcador").json()["emisoras"] == ["WALMEX"]


def test_serie_no_rellena_huecos(cliente):
    puntos = cliente("professional").get("/api/terminal/serie?emisora=WALMEX").json()["puntos"]
    for p in puntos:
        if p["estado"] != "PPP_PUBLICADO_VERIFICADO":
            assert p["ppp"] is None


def test_senal_y_descomposicion(cliente):
    d = cliente("professional").get("/api/terminal/senal?emisora=GMEXICO").json()
    assert d["fecha"] and {m["generacion"] for m in d["modelos"]} == {"G2"}
    assert all(0 < m["probabilidad"] < 1 for m in d["modelos"])
    f = d["factor"]
    if f and f["contribuciones"]:
        registrada = next(m["probabilidad"] for m in d["modelos"] if m["modelo"] == f["modelo"])
        # Paridad con el registro oficial (V1/V2 difieren hasta ~0.0013, documentado).
        assert abs(f["probabilidad_reconstruida"] - registrada) < 0.002


def test_seguimiento_trayectoria_t0_a_t5(cliente):
    d = cliente("professional").get("/api/terminal/seguimiento?emisora=WALMEX").json()
    assert [t["paso"] for t in d["trayectoria"]] == ["t0", "t+1", "t+2", "t+3", "t+4", "t+5"]
    assert d["trayectoria"][0]["retorno_pct"] == 0
    for t in d["trayectoria"]:
        if t["estado"] != "OBSERVADO":
            assert t["ppp"] is None and t["retorno_pct"] is None


def test_prismi_guardrails_y_contexto(cliente):
    c = cliente("explorer")
    r = c.post("/api/terminal/prismi", json={"pregunta": "¿Debo comprar WALMEX?"}).json()
    assert r["origen"] == "GUARDRAIL" and "No doy recomendaciones" in r["respuesta"]
    r = c.post("/api/terminal/prismi", json={"pregunta": "receta de pastel"}).json()
    assert r["origen"] == "GUARDRAIL"
    r = c.post("/api/terminal/prismi", json={"pregunta": "¿Qué es el PPP?", "contexto_grafica": "Serie PPP WALMEX"}).json()
    assert "Precio Promedio Ponderado" in r["respuesta"]
