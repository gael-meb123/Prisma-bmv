"""Plan reversible del Scheduler. Por defecto solo guarda el plan, no invoca AWS."""
import argparse
import json
from pathlib import Path

FUNCION = "arn:aws:lambda:us-east-1:886457183564:function:prisma-bmv-recolector-seguro-operacion-202-Funcion-soS1hmdqF61u"
COLA = "arn:aws:sqs:us-east-1:886457183564:prisma-bmv-recolector-seguro-operacion-2026-Fallos-lmhg8svxhDp1"
CAMPOS = {"Name", "GroupName", "Description", "StartDate", "EndDate", "ScheduleExpression",
          "ScheduleExpressionTimezone", "FlexibleTimeWindow", "State", "Target",
          "KmsKeyArn", "ActionAfterCompletion"}


def planificar(actual, accion):
    if actual.get("Name") != "DisparadorDiarioBMV" or actual.get("GroupName", "default") != "default":
        raise ValueError("Scheduler inesperado")
    plan = {k: v for k, v in actual.items() if k in CAMPOS}
    if accion == "preparar":
        if actual.get("State") != "DISABLED":
            raise ValueError("Pausar antes de cambiar destino")
        plan["Target"] = {"Arn": FUNCION, "RoleArn": actual["Target"]["RoleArn"],
                          "Input": '{"instante_programado":"<aws.scheduler.scheduled-time>"}',
                          "RetryPolicy": {"MaximumEventAgeInSeconds": 3600, "MaximumRetryAttempts": 2},
                          "DeadLetterConfig": {"Arn": COLA}}
        plan["State"] = "DISABLED"
    elif accion == "activar":
        target = actual["Target"]
        if (target.get("Arn") != FUNCION or target.get("Input") != '{"instante_programado":"<aws.scheduler.scheduled-time>"}'
                or target.get("DeadLetterConfig", {}).get("Arn") != COLA):
            raise ValueError("Destino seguro no preparado")
        plan["State"] = "ENABLED"
    elif accion in ("pausar", "restaurar"):
        plan["State"] = "DISABLED"  # Nunca reactivar el recolector anterior al revertir.
    else:
        raise ValueError("Acción inválida")
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuracion", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--accion", choices=["preparar", "activar", "pausar", "restaurar"], required=True)
    args = parser.parse_args()
    actual = json.loads(args.configuracion.read_text(encoding="utf-8-sig"))
    plan = planificar(actual, args.accion)
    with args.salida.open("x", encoding="utf-8") as archivo:
        json.dump(plan, archivo, indent=2)
    print("Plan guardado. Revisar contra get-schedule actual antes de update-schedule --cli-input-json.")


if __name__ == "__main__":
    main()
