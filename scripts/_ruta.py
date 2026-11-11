"""Hace importables `prisma` y la Lambda desde la carpeta scripts/."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for p in (RAIZ, RAIZ / "infra" / "lambda" / "recolector_diario_bmv"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
