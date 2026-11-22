"""Ensaya configuración y reversión en Scheduler aislado; prepara el real solo desactivado."""
import argparse
import hashlib
import json
import uuid
from scripts.planificar_scheduler_seguro import planificar


def main():
    import boto3
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preparar-real-desactivado", action="store_true")
    args = p.parse_args()
    session = boto3.Session(region_name="us-east-1")
    if session.client("sts").get_caller_identity()["Account"] != "886457183564":
        raise ValueError("Cuenta incorrecta")
    scheduler = session.client("scheduler")
    actual = scheduler.get_schedule(Name="DisparadorDiarioBMV", GroupName="default")
    seguro = planificar(actual, "preparar")
    nombre = "prisma-ensayo-" + uuid.uuid4().hex
    # Fecha muy posterior: el ensayo verifica configuración, no invoca la ingesta.
    ensayo = {**seguro, "Name": nombre, "ScheduleExpression": "at(2099-01-01T12:00:00)"}
    for k in ("StartDate", "EndDate"):
        ensayo.pop(k, None)
    scheduler.create_schedule(**ensayo)
    try:
        scheduler.update_schedule(**{**ensayo, "State": "ENABLED"})
        assert scheduler.get_schedule(Name=nombre)["State"] == "ENABLED"
        scheduler.update_schedule(**{**ensayo, "State": "DISABLED"})
        assert scheduler.get_schedule(Name=nombre)["State"] == "DISABLED"
        # Reversión de destino manteniendo DISABLED.
        restaurado = {**ensayo, "Target": actual["Target"]}
        scheduler.update_schedule(**restaurado)
        leido = scheduler.get_schedule(Name=nombre)
        assert leido["State"] == "DISABLED" and leido["Target"]["Arn"] == actual["Target"]["Arn"]
    finally:
        scheduler.delete_schedule(Name=nombre, GroupName="default")
    if args.preparar_real_desactivado:
        raw = json.dumps(planificar(actual, "restaurar"), default=str, sort_keys=True).encode()
        sha = hashlib.sha256(raw).hexdigest()
        key = f"operacion/scheduler/respaldo-{uuid.uuid4().hex}-{sha}.json"
        s3 = session.client("s3")
        bucket = "prisma-bmv-aislado-prueba-2026-bucket-pumqsjizexvp"
        s3.put_object(Bucket=bucket, Key=key, Body=raw, IfNoneMatch="*", ContentType="application/json")
        assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == raw
        reciente = scheduler.get_schedule(Name=actual["Name"], GroupName="default")
        if planificar(reciente, "restaurar") != planificar(actual, "restaurar") or reciente["State"] != "DISABLED":
            raise ValueError("Configuración cambió durante el ensayo")
        scheduler.update_schedule(**seguro)
        final = scheduler.get_schedule(Name=actual["Name"], GroupName="default")
        assert final["State"] == "DISABLED" and final["Target"]["Arn"] == seguro["Target"]["Arn"]
        print(json.dumps({"ensayo_control_plane": "OK", "scheduler_real": "PREPARADO_DISABLED",
                          "respaldo_bucket": bucket, "respaldo_key": key, "sha256": sha,
                          "invocacion_programada": "NO_EJECUTADA"}))
    else:
        print(json.dumps({"ensayo_control_plane": "OK", "scheduler_real": "SIN_CAMBIOS"}))


if __name__ == "__main__":
    main()
