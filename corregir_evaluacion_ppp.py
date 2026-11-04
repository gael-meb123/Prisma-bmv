"""Migracion auditable v2: respalda salidas, recalcula y conserva las emisiones originales."""

import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

import modulo_panel_multiemisora as panel
import investigacion_profunda_gmexico as gm
from etapa10_ejecutor_diario import aplicar_correcciones_registro, resolve_matured_signals_and_update_scoreboard
from metodologia_ppp import ROOT, VERSION_METODOLOGIA, agregar_trazabilidad, timestamp_utc

AUDIT = ROOT / "auditoria_evaluacion_v2"
ARCHIVOS = [
    "dataset_panel_15_emisoras_features.csv", "metricas_panel_15_emisoras.json",
    "reporte_investigacion_profunda_gmexico.json", "registro_senales_prospectivas_walmex.csv",
    "registro_senales_prospectivas_gmexico.csv", "marcador_modelos_prospectivo.csv",
]
PREDICCIONES = [
    "id_senal", "fecha_senal", "fecha_objetivo_h5", "ppp_base_mxn", "prob_subida_h5",
    "prediccion_clase", "timestamp_emision_utc",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = AUDIT / "manifiesto.json"
    if manifest.exists():
        print(f"Correccion v2 ya aplicada. Evidencia: {manifest}")
        return
    if not ROOT.is_dir():
        raise ValueError("Directorio de proyecto no disponible")
    backup = AUDIT / "antes"
    backup.mkdir(parents=True, exist_ok=True)
    for name in ARCHIVOS:
        target = backup / name
        if not target.exists():
            shutil.copy2(ROOT / name, target)
    price_path = ROOT / "serie_ppp_historica_15_emisoras_bmv.csv"
    price_hash = sha(price_path)
    before = pd.read_csv(backup / ARCHIVOS[0])
    signals = {tk: pd.read_csv(backup / f"registro_senales_prospectivas_{tk}.csv") for tk in ["walmex", "gmexico"]}

    panel.main()
    gm.main()
    old_w = aplicar_correcciones_registro(pd.read_csv(ROOT / "registro_senales_prospectivas_walmex.csv"))
    old_w.to_csv(ROOT / "registro_senales_prospectivas_walmex.csv", index=False, encoding="utf-8-sig")
    series = pd.read_csv(ROOT / "serie_ppp_walmex_prospectiva.csv")
    resolve_matured_signals_and_update_scoreboard(series, ROOT / "registro_senales_prospectivas_walmex.csv", ROOT / "marcador_modelos_prospectivo.csv")
    raw = pd.read_csv(price_path)
    gseries = raw[raw.emisora.eq("GMEXICO")].copy()
    gseries["precio_apto_calculo"] = gseries.estado_captura.eq("PPP_PUBLICADO_VERIFICADO")
    gpath = ROOT / "registro_senales_prospectivas_gmexico.csv"
    agregar_trazabilidad(pd.read_csv(gpath)).to_csv(gpath, index=False, encoding="utf-8-sig")
    resolve_matured_signals_and_update_scoreboard(gseries, gpath, ROOT / "marcador_modelos_prospectivo_gmexico.csv")

    for tk, original in signals.items():
        current = pd.read_csv(ROOT / f"registro_senales_prospectivas_{tk}.csv")
        pd.testing.assert_frame_equal(original[PREDICCIONES], current[PREDICCIONES], check_dtype=False)
    if sha(price_path) != price_hash:
        raise AssertionError("La migracion altero la fuente de PPP")
    after = pd.read_csv(ROOT / ARCHIVOS[0])
    joined = before.merge(after, on=["fecha", "emisora"], suffixes=("_antes", "_despues"), validate="one_to_one")
    changes = {}
    for f in panel.FEATURE_NAMES:
        changes[f] = float(np.abs(joined[f + "_antes"] - joined[f + "_despues"]).max())
        if f != "distancia_media_20" and changes[f] > 1e-12:
            raise AssertionError(f"Cambio inesperado de formula: {f}")
    metrics = json.loads((ROOT / "metricas_panel_15_emisoras.json").read_text(encoding="utf-8"))
    report = {
        "version_metodologia": VERSION_METODOLOGIA,
        "timestamp_aplicacion_utc": timestamp_utc(),
        "ppp_original_sha256": price_hash,
        "ppp_original_preservado": True,
        "predicciones_y_timestamps_originales_preservados": True,
        "respaldo_antes": {name: sha(backup / name) for name in ARCHIVOS},
        "salidas_despues": {name: sha(ROOT / name) for name in ARCHIVOS},
        "max_cambio_absoluto_variables": changes,
        "cortes": {"train_etiquetas_hasta": "2025-04-29", "test_etiquetas_hasta": "2026-10-27"},
        "metricas_panel_corregidas": metrics,
        "nota": "Test previamente inspeccionado: resultados exploratorios. Recalculos v2 no sustituyen emisiones originales.",
    }
    manifest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Migracion y controles de integridad completados: {manifest}")


if __name__ == "__main__":
    main()
