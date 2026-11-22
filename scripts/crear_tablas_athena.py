"""
Prisma BMV - Crea la base y las tablas externas de Athena (infra/athena/0*.sql).

Uso:
  python scripts/crear_tablas_athena.py --bucket MI_BUCKET [--region us-east-1] [--workgroup primary]
  python scripts/crear_tablas_athena.py --bucket MI_BUCKET --solo-imprimir
"""

from __future__ import annotations

import argparse

import _ruta  # noqa: F401

DIR_SQL = _ruta.RAIZ / "infra" / "athena"


def sentencias(bucket: str) -> list[tuple[str, str]]:
    out = []
    for ruta in sorted(DIR_SQL.glob("0*.sql")):
        texto = ruta.read_text(encoding="utf-8").replace("${BUCKET}", bucket)
        sql = "\n".join(l for l in texto.splitlines() if not l.strip().startswith("--")).strip().rstrip(";")
        out.append((ruta.name, sql))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--workgroup", default="primary")
    ap.add_argument("--solo-imprimir", action="store_true")
    a = ap.parse_args()

    if a.solo_imprimir:
        for nombre, sql in sentencias(a.bucket):
            print(f"-- {nombre}\n{sql};\n")
        return
    raise SystemExit(
        "Creación bloqueada: los DDL 0*.sql corresponden a la Lambda alternativa "
        "y no son compatibles con el Gold desplegado. Use --solo-imprimir para "
        "inspección y consulte docs/ARQUITECTURA_AWS.md."
    )


if __name__ == "__main__":
    main()
