"""Actualiza solo ArtifactKey de stacks Prisma existentes; conserva la plantilla y parámetros."""
import argparse
import hashlib
import json
import uuid
from pathlib import Path

STACKS = {
    "prisma-bmv-api-capturas-pruebas-2026", "prisma-bmv-api-aislada-2026",
    "prisma-bmv-recolector-seguro-pruebas-2026", "prisma-bmv-recolector-seguro-operacion-2026",
    "prisma-bmv-guardia-senales-aislada-2026",
}
BUCKET = "prisma-bmv-aislado-prueba-2026-bucket-pumqsjizexvp"


def main():
    import boto3
    from botocore.exceptions import ClientError
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stack", choices=sorted(STACKS), required=True)
    p.add_argument("--archivo", type=Path, required=True)
    p.add_argument("--registro", type=Path, required=True)
    args = p.parse_args()
    if args.registro.exists():
        raise ValueError("El registro de despliegue ya existe")
    session = boto3.Session(region_name="us-east-1")
    if session.client("sts").get_caller_identity()["Account"] != "886457183564":
        raise ValueError("Cuenta incorrecta")
    s3, cf = session.client("s3"), session.client("cloudformation")
    raw = args.archivo.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    key = f"artifacts/entrega/{sha}.zip"
    try:
        s3.put_object(Bucket=BUCKET, Key=key, Body=raw, IfNoneMatch="*", ContentType="application/zip")
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("412", "PreconditionFailed"):
            raise
        if s3.get_object(Bucket=BUCKET, Key=key)["Body"].read() != raw:
            raise ValueError("Artefacto incompatible")
    stack = cf.describe_stacks(StackName=args.stack)["Stacks"][0]
    parametros = {x["ParameterKey"]: x["ParameterValue"] for x in stack["Parameters"]}
    if parametros["ArtifactBucket"] != BUCKET:
        raise ValueError("Bucket de artefactos inesperado")
    cambios = cf.create_change_set(StackName=args.stack, ChangeSetName="codigo-" + uuid.uuid4().hex,
        ChangeSetType="UPDATE", UsePreviousTemplate=True,
        Parameters=[{"ParameterKey": k, **({"ParameterValue": key} if k == "ArtifactKey" else {"UsePreviousValue": True})}
                    for k in parametros])
    cf.get_waiter("change_set_create_complete").wait(ChangeSetName=cambios["Id"])
    detalle = cf.describe_change_set(ChangeSetName=cambios["Id"])
    for c in detalle["Changes"]:
        r = c["ResourceChange"]
        if (r["Action"] != "Modify" or r.get("Replacement") != "False"
                or r["ResourceType"] not in ("AWS::Lambda::Function", "AWS::Lambda::Permission",
                                            "AWS::ApiGatewayV2::Integration", "AWS::ApiGatewayV2::Deployment")):
            raise ValueError("Cambio fuera de la actualización de código: " + r["LogicalResourceId"])
    registro = {"stack": args.stack, "anterior": parametros["ArtifactKey"], "nuevo": key, "sha256": sha,
                "change_set": cambios["Id"], "estado": "PREPARADO"}
    with args.registro.open("x", encoding="utf-8") as f:
        json.dump(registro, f, indent=2)
    cf.execute_change_set(ChangeSetName=cambios["Id"])
    cf.get_waiter("stack_update_complete").wait(StackName=args.stack)
    print(json.dumps({**registro, "estado": "UPDATE_COMPLETE"}))


if __name__ == "__main__":
    main()
