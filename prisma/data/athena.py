"""
Prisma BMV - Acceso SQL al lakehouse.

* `ClienteAthena`: ejecuta SQL en Amazon Athena (Trino) y lee el CSV de resultados que
  Athena deja en s3://<bucket>/athena-results/.
* `MotorSQLLocal`: emula las mismas tablas con DuckDB sobre los CSV locales, para trabajar
  sin cuenta de AWS. La interfaz lo indica explícitamente cuando se usa.
* `validar_sql_lectura`: defensa en profundidad para la consola Enterprise. La barrera
  principal sigue siendo IAM/workgroup; esto evita escrituras y tablas fuera del catálogo.
"""

from __future__ import annotations

import io
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

TABLAS_PERMITIDAS = frozenset(
    {"bmv_silver_ppp", "bmv_gold_senales_g2", "bmv_gold_senales_g1", "v_senales_g2_tipadas"}
)
_PROHIBIDAS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|MSCK|UNLOAD|GRANT|REVOKE|MERGE|CALL|"
    r"EXECUTE|PREPARE|DEALLOCATE|VACUUM|OPTIMIZE|TRUNCATE|COPY|ATTACH|PRAGMA|"
    r"INSTALL|LOAD|EXPORT|IMPORT)\b",
    re.IGNORECASE,
)
_TABLAS_REF = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w.\"]*)", re.IGNORECASE)
_FUNCIONES_ARCHIVO = re.compile(r"\b(read_csv\w*|read_parquet|read_json\w*|glob)\s*\(", re.IGNORECASE)


class ErrorSQL(ValueError):
    pass


def _sin_comentarios(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


def validar_sql_lectura(sql: str, limite: int, tablas: frozenset[str] = TABLAS_PERMITIDAS) -> str:
    """Devuelve el SQL normalizado con LIMIT o lanza ErrorSQL con un motivo claro."""
    limpio = _sin_comentarios(sql).strip().rstrip(";").strip()
    if not limpio:
        raise ErrorSQL("Escriba una consulta.")
    if ";" in limpio:
        raise ErrorSQL("Solo se permite una instrucción por ejecución.")
    if not re.match(r"^(SELECT|WITH)\b", limpio, re.IGNORECASE):
        raise ErrorSQL("Solo se permiten consultas de lectura (SELECT o WITH).")
    if m := _PROHIBIDAS.search(limpio):
        raise ErrorSQL(f"La palabra clave {m.group(1).upper()} no está permitida en la consola.")
    if _FUNCIONES_ARCHIVO.search(limpio):
        raise ErrorSQL("No se permite leer archivos directamente; consulte las tablas del catálogo.")
    ctes = {c.lower() for c in re.findall(r"\b(\w+)\s+AS\s*\(", limpio, re.IGNORECASE)}
    for ref in _TABLAS_REF.findall(limpio):
        nombre = ref.replace('"', "").split(".")[-1].lower()
        if nombre not in tablas and nombre not in ctes:
            raise ErrorSQL(f"La tabla '{nombre}' no está disponible. Tablas: {', '.join(sorted(tablas))}.")
    return f"SELECT * FROM (\n{limpio}\n) AS consulta LIMIT {int(limite)}"


@dataclass
class ResultadoSQL:
    datos: pd.DataFrame
    motor: str
    bytes_escaneados: int | None = None
    milisegundos: int | None = None
    id_consulta: str | None = None


class ClienteAthena:
    def __init__(self, database: str, workgroup: str, salida_s3: str, region: str, timeout_s: int = 45):
        import boto3

        if not salida_s3:
            raise ValueError("Configure PRISMA_S3_BUCKET o PRISMA_ATHENA_OUTPUT para Athena.")
        self.database, self.workgroup, self.salida = database, workgroup, salida_s3
        self.timeout_s = timeout_s
        self._athena = boto3.client("athena", region_name=region)
        self._s3 = boto3.client("s3", region_name=region)

    def ejecutar(self, sql: str, leer_resultados: bool = True) -> ResultadoSQL:
        qid = self._athena.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": self.database},
            WorkGroup=self.workgroup,
            ResultConfiguration={"OutputLocation": self.salida},
        )["QueryExecutionId"]

        espera, inicio = 0.25, time.monotonic()
        while True:
            q = self._athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
            estado = q["Status"]["State"]
            if estado == "SUCCEEDED":
                break
            if estado in ("FAILED", "CANCELLED"):
                raise ErrorSQL(q["Status"].get("StateChangeReason", f"Consulta {estado}"))
            if time.monotonic() - inicio > self.timeout_s:
                self._athena.stop_query_execution(QueryExecutionId=qid)
                raise ErrorSQL(f"La consulta superó {self.timeout_s} s y se canceló.")
            time.sleep(espera)
            espera = min(espera * 2, 2.0)

        stats = q.get("Statistics", {})
        if not leer_resultados:  # DDL: Athena deja un .txt sin tabla de resultados
            return ResultadoSQL(pd.DataFrame(), "Amazon Athena", stats.get("DataScannedInBytes"),
                                stats.get("EngineExecutionTimeInMillis"), qid)
        destino = urlparse(q["ResultConfiguration"]["OutputLocation"])
        cuerpo = self._s3.get_object(Bucket=destino.netloc, Key=destino.path.lstrip("/"))["Body"].read()
        return ResultadoSQL(
            datos=pd.read_csv(io.BytesIO(cuerpo)) if cuerpo else pd.DataFrame(),
            motor="Amazon Athena",
            bytes_escaneados=stats.get("DataScannedInBytes"),
            milisegundos=stats.get("EngineExecutionTimeInMillis"),
            id_consulta=qid,
        )


class MotorSQLLocal:
    """Mismas tablas que en Athena, servidas por DuckDB en memoria."""

    def __init__(self, tablas: dict[str, pd.DataFrame]):
        import duckdb

        self._con = duckdb.connect(database=":memory:")
        for nombre, df in tablas.items():
            self._con.register(nombre, df)
        # Sin acceso a archivos ni red desde SQL: solo las tablas registradas.
        self._con.execute("SET enable_external_access = false")

    def ejecutar(self, sql: str) -> ResultadoSQL:
        inicio = time.monotonic()
        try:
            df = self._con.execute(sql).fetchdf()
        except Exception as e:  # duckdb.Error y derivados
            raise ErrorSQL(str(e).split("\n")[0]) from e
        return ResultadoSQL(df, "DuckDB local (emulación sin AWS)",
                            milisegundos=int((time.monotonic() - inicio) * 1000))


def leer_sql(ruta: Path) -> str:
    return Path(ruta).read_text(encoding="utf-8")
