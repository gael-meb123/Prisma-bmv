import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
os.environ.setdefault("PRISMA_PBKDF2_ITER", "1000")  # rápido en pruebas; producción usa 600 000
for p in (RAIZ, RAIZ / "infra" / "lambda" / "recolector_diario_bmv"):
    sys.path.insert(0, str(p))

import json  # noqa: E402

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

DATOS = RAIZ / "datos"


@pytest.fixture(scope="session")
def serie():
    return pd.read_csv(DATOS / "serie_unificada_reciente.csv")


@pytest.fixture(scope="session")
def g2_registrado():
    return pd.read_csv(DATOS / "registro_senales_prospectivas_panel_g2.csv")


@pytest.fixture(scope="session")
def modelos():
    return json.loads((DATOS / "modelos" / "registro_modelos_g2_oficial.json").read_text())


@pytest.fixture(scope="session")
def html_prueba():
    return (RAIZ / "tests" / "fixtures" / "boletin_prueba.html").read_bytes()
