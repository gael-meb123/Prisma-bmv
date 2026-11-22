"""Publicación manual únicamente en react-demo. Requiere frontend/dist compilado."""
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path


def main():
    import boto3
    from botocore.waiter import WaiterModel, create_waiter_with_client
    dist = Path(__file__).resolve().parents[1] / "frontend/dist"
    js = "\n".join(p.read_text(encoding="utf-8") for p in (dist / "assets").glob("*.js"))
    for valor in ("us-east-1_mKU76i6gl", "3k7iv4ebko2us1bbk78v07cg09",
                  "https://j42hw8l6rl.execute-api.us-east-1.amazonaws.com"):
        if valor not in js:
            raise ValueError("Build sin configuración experimental requerida")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(dist.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(dist).as_posix())
    raw = buffer.getvalue()
    cliente = boto3.client("amplify", region_name="us-east-1")
    args = {"appId": "d315dh37vi024o", "branchName": "react-demo"}
    despliegue = cliente.create_deployment(**args)
    # URL firmada y tokens permanecen en memoria.
    with urllib.request.urlopen(urllib.request.Request(despliegue["zipUploadUrl"], data=raw, method="PUT",
                                headers={"Content-Type": "application/zip"}), timeout=60) as response:
        if response.status not in (200, 201):
            raise ValueError("No se aceptó el ZIP")
    cliente.start_deployment(**args, jobId=despliegue["jobId"])
    waiter = create_waiter_with_client("Publicado", WaiterModel({"version": 2, "waiters": {"Publicado": {
        "operation": "GetJob", "delay": 5, "maxAttempts": 120,
        "acceptors": [{"state": "success", "matcher": "path", "argument": "job.summary.status", "expected": "SUCCEED"},
                      {"state": "failure", "matcher": "path", "argument": "job.summary.status", "expected": "FAILED"},
                      {"state": "failure", "matcher": "path", "argument": "job.summary.status", "expected": "CANCELLED"}]
    }}}), cliente)
    waiter.wait(**args, jobId=despliegue["jobId"])
    print(json.dumps({"rama": "react-demo", "job": despliegue["jobId"], "estado": "SUCCEED",
                      "sha256_zip": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
