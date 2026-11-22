"""Valida evidencia exportada de SQS y propone reintento; no borra ni invoca."""
import argparse
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.planificar_scheduler_seguro import FUNCION


def preparar_reintento(evidencia):
    contexto = evidencia.get("requestContext", {})
    if contexto.get("functionArn", "").removesuffix(":$LATEST") != FUNCION:
        raise ValueError("Función no admitida")
    if contexto.get("condition") not in ("RetriesExhausted", "EventAgeExceeded"):
        raise ValueError("Condición de fallo no reconocida")
    evento = evidencia.get("requestPayload")
    if not isinstance(evento, dict):
        raise ValueError("Evento inválido")
    if set(evento) == {"fecha"}:
        fecha = date.fromisoformat(evento["fecha"])
        if fecha.isoformat() != evento["fecha"]:
            raise ValueError("Fecha no canónica")
    elif set(evento) == {"instante_programado"}:
        instante = datetime.fromisoformat(evento["instante_programado"].replace("Z", "+00:00"))
        if instante.tzinfo is None:
            raise ValueError("Instante sin zona")
        fecha = instante.astimezone(ZoneInfo("America/Mexico_City")).date()
    else:
        # {} no fija la fecha original; no volver a ejecutar como si fuera hoy.
        raise ValueError("Evento sin fecha determinista; requiere revisión manual")
    if fecha.year != 2026:
        raise ValueError("Calendario no validado")
    return {"fecha": fecha.isoformat()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidencia", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps({"evento_propuesto": preparar_reintento(json.loads(args.evidencia.read_text(encoding="utf-8-sig"))),
                      "requiere_revisar_conflicto_y_fuente": True}))


if __name__ == "__main__":
    main()
