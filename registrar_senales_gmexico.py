"""Conserva el registro legado de GMEXICO sin reemitir pronosticos historicos."""

from pathlib import Path
import pandas as pd
from metodologia_ppp import agregar_trazabilidad

WORKSPACE = Path(__file__).resolve().parent
OUTPUT_CSV = WORKSPACE / "registro_senales_prospectivas_gmexico.csv"


def main():
    if not OUTPUT_CSV.exists():
        raise RuntimeError(
            "No existe el registro original. Un recalculo historico no permite reconstruir "
            "una emision prospectiva ni su timestamp; restaura la evidencia archivada."
        )
    df = agregar_trazabilidad(pd.read_csv(OUTPUT_CSV))
    if df.id_senal.duplicated().any():
        raise ValueError("Hay IDs duplicados en el registro original")
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"Trazabilidad actualizada para {len(df)} senales originales de GMEXICO.")


if __name__ == "__main__":
    main()
