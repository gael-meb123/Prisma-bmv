"""Pruebas de extremo a extremo de la interfaz con streamlit.testing (sin navegador)."""

import re

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import RAIZ

APP = str(RAIZ / "app.py")


@pytest.fixture(autouse=True)
def estado_aislado(tmp_path, monkeypatch):
    monkeypatch.setenv("PRISMA_STATE_DIR", str(tmp_path))
    from prisma.settings import get_settings
    get_settings.cache_clear()
    from prisma.ui.contexto import servicios
    servicios.clear()
    yield


def _app(email=None):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["tour_visto"] = True
    if email:
        at.session_state["usuario_email"] = email
    return at.run()


def _sin_errores(at):
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def test_portada_y_registro_inicia_en_explorer():
    at = _app()
    _sin_errores(at)
    at.text_input[2].input("Ana Morales")
    at.text_input[3].input("ana@fondoalfa.mx")
    at.text_input[4].input("ClaveSegura2026")
    at.checkbox[0].check()
    at.button(key="FormSubmitter:f_registro-Crear cuenta").click().run()
    _sin_errores(at)
    assert at.session_state["usuario_email"] == "ana@fondoalfa.mx"
    assert any("Explorer" in m.value for m in at.markdown)


@pytest.mark.parametrize("email,emisoras", [
    ("explorer@demo.prismabmv.com", ["WALMEX"]),
    ("pro@demo.prismabmv.com", ["AMX", "GFNORTE", "GMEXICO", "WALMEX"]),
    ("enterprise@demo.prismabmv.com", ["AMX", "GFNORTE", "GMEXICO", "WALMEX"]),
])
def test_terminal_por_plan(email, emisoras):
    at = _app(email)
    _sin_errores(at)
    assert at.selectbox(key="au_em").options == emisoras
    explorer = email.startswith("explorer")
    assert at.selectbox(key="mk_fecha").value == ("2026-10-29" if explorer else "2026-10-30")
    hay_sql = any(b.key == "lk_run" for b in at.button)
    assert hay_sql == email.startswith("enterprise")


def test_explorer_ve_bloqueo_al_elegir_gmexico():
    at = _app("explorer@demo.prismabmv.com")
    at.selectbox(key="sg_em").set_value("GMEXICO").run()
    _sin_errores(at)
    assert any(b.label.startswith("Activar Professional") for b in at.button)


def test_checkout_sandbox_activa_professional():
    at = _app("explorer@demo.prismabmv.com")
    at.session_state["checkout_plan"] = "professional"
    at.session_state["vista"] = "checkout"
    at.run()
    _sin_errores(at)
    campos = {t.label: t for t in at.text_input}
    campos["Número de tarjeta"].input("4242 4242 4242 4242")
    campos["Vencimiento (MM/AA)"].input("12/30")
    campos["CVC"].input("123")
    at.button(key="FormSubmitter:f_pago-Pagar $49 USD y activar Professional").click().run()
    _sin_errores(at)
    assert at.session_state["vista"] == "terminal"
    assert at.selectbox(key="au_em").options == ["AMX", "GFNORTE", "GMEXICO", "WALMEX"]


def test_consola_sql_enterprise():
    at = _app("enterprise@demo.prismabmv.com")
    at.button(key="lk_run").click().run()
    _sin_errores(at)
    assert any(df.value.shape == (20, 5) for df in at.dataframe)


def test_prismi_responde_desde_widget():
    at = _app("pro@demo.prismabmv.com")
    at.button(key="pr_q1").click().run()
    _sin_errores(at)
    msgs = at.session_state["prismi_msgs"]
    assert msgs[-1]["role"] == "assistant" and "GMEXICO" in msgs[-1]["content"]


def test_sin_identidad_academica_en_codigo_entregado():
    prohibidas = re.compile(r"universidad|semestre|tecnm|celaya|proyecto escolar|proyecto final|big data", re.I)
    # Solo el código de la terminal; los scripts de investigación de la raíz quedan fuera de alcance.
    entregado = [RAIZ / "app.py", RAIZ / "README.md"]
    for carpeta in ("prisma", "infra", "scripts", "docs"):
        for patron in ("*.py", "*.md", "*.sql", "*.sh"):
            entregado += list((RAIZ / carpeta).rglob(patron))
    for ruta in entregado:
        assert not prohibidas.search(ruta.read_text(encoding="utf-8")), ruta


def test_mascota_svg_valido_y_con_ids_unicos():
    from prisma.ui.mascota import mascota

    a, b = mascota("happy", "wave"), mascota("idle", "point-right")
    for svg in (a, b):
        assert svg.count("<g") == svg.count("</g>") and "\n" not in svg  # Markdown no debe partirlo
    assert 'id="prismi-bill-' in a and set(re.findall(r'id="([^"]+)"', a)).isdisjoint(re.findall(r'id="([^"]+)"', b))
    assert "prismi-pose-idle" in mascota("happy", "pose-inexistente")
