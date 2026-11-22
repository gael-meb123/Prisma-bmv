"""Publicación manual en la rama Amplify ``entrega-modelos`` (evaluación histórica Gold).

Requiere ``frontend/dist`` compilado con ``VITE_GOLD_EVALUACION=true`` y la URL de la API
de solo lectura ``prisma-bmv-api-entrega-modelos-2026``. No toca ``react-demo`` ni ``main``.
"""
import argparse
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path


def main():
    import boto3
    from botocore.waiter import WaiterModel, create_waiter_with_client

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--api-url", required=True, help="Endpoint de la API prisma-bmv-api-entrega-modelos-2026")
    args = p.parse_args()

    dist = Path(__file__).resolve().parents[1] / "frontend/dist"
    js = "\n".join(x.read_text(encoding="utf-8") for x in (dist / "assets").glob("*.js"))
    for valor in ("us-east-1_mKU76i6gl", "3k7iv4ebko2us1bbk78v07cg09", args.api_url.rstrip("/")):
        if valor not in js:
            raise ValueError(f"Build sin configuración requerida: {valor}")
    if "supabase.co" in js.lower():
        raise ValueError("Build contiene referencia residual a Supabase")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(dist.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(dist).as_posix())
    raw = buffer.getvalue()

    cliente = boto3.client("amplify", region_name="us-east-1")
    target = {"appId": "d315dh37vi024o", "branchName": "entrega-modelos"}
    despliegue = cliente.create_deployment(**target)
    with urllib.request.urlopen(
        urllib.request.Request(
            despliegue["zipUploadUrl"],
            data=raw,
            method="PUT",
            headers={"Content-Type": "application/zip"},
        ),
        timeout=60,
    ) as response:
        if response.status not in (200, 201):
            raise ValueError("No se aceptó el ZIP")
    cliente.start_deployment(**target, jobId=despliegue["jobId"])
    waiter = create_waiter_with_client(
        "Publicado",
        WaiterModel({
            "version": 2,
            "waiters": {
                "Publicado": {
                    "operation": "GetJob",
                    "delay": 5,
                    "maxAttempts": 120,
                    "acceptors": [
                        {"state": "success", "matcher": "path", "argument": "job.summary.status", "expected": "SUCCEED"},
                        {"state": "failure", "matcher": "path", "argument": "job.summary.status", "expected": "FAILED"},
                        {"state": "failure", "matcher": "path", "argument": "job.summary.status", "expected": "CANCELLED"},
                    ],
                }
            },
        }),
        cliente,
    )
    waiter.wait(**target, jobId=despliegue["jobId"])
    print(json.dumps({
        "rama": "entrega-modelos",
        "url": "https://entrega-modelos.d315dh37vi024o.amplifyapp.com/",
        "job": despliegue["jobId"],
        "estado": "SUCCEED",
        "sha256_zip": hashlib.sha256(raw).hexdigest(),
    }))


if __name__ == "__main__":
    main()
