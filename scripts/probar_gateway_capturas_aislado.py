"""Ejecuta una prueba HTTP destructiva solo por adición en un bucket de laboratorio nuevo."""
import argparse
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

STACK = "prisma-bmv-api-capturas-pruebas-2026"
ORIGEN = "prisma-bmv-aislado-prueba-2026-bucket-pumqsjizexvp"


def aws(*args):
    result = subprocess.run(["aws", *args, "--region", "us-east-1", "--output", "json"],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout or "{}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{32}", args.run_id):
        raise ValueError("Identificador inválido")
    stack = aws("cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0]
    if stack["StackStatus"] not in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
        raise ValueError("Stack no disponible")
    outputs = {x["OutputKey"]: x["OutputValue"] for x in stack["Outputs"]}
    bucket, endpoint = outputs["Fuente"], outputs["ApiEndpoint"]
    if not bucket.startswith(STACK + "-fuente-") or not endpoint.startswith("https://"):
        raise ValueError("Destino aislado inesperado")
    prefix = f"pruebas/recolector-seguro/{args.run_id}/concurrencia/"
    keys = ["snapshot.csv",
            "silver/capturas_en_curso/2026/11/captura_20261119.json",
            "silver/recolector_seguro/precios_ppp/2026/11/ppp_15_emisoras_20261119.csv",
            "silver/capturas_seguras/2026/11/captura_20261119.json"]
    existing = aws("s3api", "list-objects-v2", "--bucket", bucket)
    existentes = {item["Key"] for item in existing.get("Contents", [])}
    if existing.get("IsTruncated") or not existentes.issubset(set(keys[:3])):
        raise ValueError("La fuente contiene objetos inesperados o una prueba ya finalizada")

    def consulta(path, status=200):
        try:
            with urllib.request.urlopen(endpoint + path, timeout=20) as response:
                actual, body = response.status, response.read()
        except urllib.error.HTTPError as exc:
            actual, body = exc.code, exc.read()
        if actual != status:
            raise AssertionError(f"{path}: esperado {status}, recibido {actual}: {body[:300]!r}")
        return json.loads(body)

    root = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "opencode"
    with tempfile.TemporaryDirectory(prefix="gateway-capturas-", dir=root) as temp:
        files = {}
        for i, key in enumerate(keys):
            file = Path(temp) / str(i)
            aws("s3api", "get-object", "--bucket", ORIGEN, "--key", prefix + key, str(file))
            files[key] = file

        def publicar(key, file):
            if key in existentes:
                anterior = Path(temp) / ("existente-" + str(keys.index(key)))
                aws("s3api", "get-object", "--bucket", bucket, "--key", key, str(anterior))
                if anterior.read_bytes() != file.read_bytes():
                    raise ValueError("Objeto de prueba existente distinto; no se sobrescribe")
                return
            aws("s3api", "put-object", "--bucket", bucket, "--key", key,
                "--body", str(file), "--if-none-match", "*")

        publicar(keys[0], files[keys[0]])
        publicar(keys[1], files[keys[1]])
        publicar(keys[2], files[keys[2]])
        if consulta("/api/mercado/fechas") != ["2026-11-17"]:
            raise AssertionError("Una captura parcial apareció en fechas")
        publicar(keys[3], files[keys[3]])
        if consulta("/api/mercado/fechas") != ["2026-11-19", "2026-11-17"]:
            raise AssertionError("La captura completa no aparece en fechas")
        if consulta("/api/mercado/resumen")["fecha"] != "2026-11-19":
            raise AssertionError("El resumen no usa la captura completa")

        # Una segunda fecha sintética con hash incorrecto debe cerrar la lectura.
        corrupto = json.loads(files[keys[3]].read_bytes())
        corrupto.update({"fecha": "2026-11-18", "bronze": "bronze/2026/11/boletin_20261118.html",
                         "silver": "silver/recolector_seguro/precios_ppp/2026/11/ppp_15_emisoras_20261118.csv",
                         "sha256_silver": "0" * 64})
        mal = Path(temp) / "manifest-invalido.json"
        mal.write_text(json.dumps(corrupto), encoding="utf-8")
        publicar(corrupto["silver"], files[keys[2]])
        publicar("silver/capturas_seguras/2026/11/captura_20261118.json", mal)
        consulta("/api/mercado/fechas", 503)
    print(json.dumps({"resultado": "OK", "parcial_oculto": True, "captura_visible": True,
                      "resumen_actualizado": True, "hash_invalido_rechazado": True,
                      "bucket_aislado": bucket, "endpoint": endpoint,
                      "nota": "La fuente sintética conserva deliberadamente un manifiesto inválido."}))


if __name__ == "__main__":
    main()
