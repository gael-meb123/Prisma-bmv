"""Genera evidencia local de panel y catálogo, sin certificar fuentes ni emitir señales."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import pandas as pd
from scripts.auditar_panel_estadistico import cargar, auditar as vinculos
from scripts.auditar_formulas_panel import auditar as formulas
from prisma.domain.catalogo_ipc import catalogo_naftrac_20261117


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", type=Path, required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    historico, sha = cargar(root / "serie_ppp_historica_15_emisoras_bmv.csv")
    panel, sha_panel = cargar(root / "dataset_panel_15_emisoras_features_ajustado_fase1.csv")
    vinculo = vinculos(historico, panel)
    aritmetica = formulas(pd.read_csv(io.BytesIO((root / "dataset_panel_15_emisoras_features_ajustado_fase1.csv").read_bytes())))
    catalogo = catalogo_naftrac_20261117()
    archivos = ["eventos_corporativos_15_emisoras.csv", "registro_modelos_g2_oficial.json",
                "registro_modelos_g2_v2.json", "registro_modelos_g2_exportado.json"]
    reporte = {
        "sha256_historico": sha, "sha256_panel": sha_panel,
        "vinculos": vinculo, "aritmetica": aritmetica,
        "huellas": {f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in archivos},
        "catalogo": {"version": catalogo.version, "fecha_corte": catalogo.fecha_corte.isoformat(),
                     "componentes": len(catalogo.componentes), "estado": "PROVISIONAL_NO_OFICIAL",
                     "alias_pendientes": ["RA -> R / A", "LIVEPOLC.1 -> LIVEPOL / C-1"]},
        "validaciones_externas": [
            "Documentos oficiales de eventos corporativos, fechas ex y factores de ajuste.",
            "Composición IPC con vigencia y evidencia de equivalencia de alias.",
            "Evidencia BMV de cada sesión de entrenamiento/evaluación; auditoría temporal sin fuga.",
            "Calendario oficial BMV 2027 y alcance de autorización BMV."
        ],
        "emision": "NO_HABILITADA"
    }
    with args.salida.open("x", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"vinculos": vinculo["contadores"], "aritmetica": aritmetica["resultados"],
                      "reporte": str(args.salida)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
