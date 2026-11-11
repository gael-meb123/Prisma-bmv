#!/usr/bin/env bash
# =============================================================================
# Prisma BMV - Despliegue de la arquitectura en AWS (idempotente)
#
#   S3 (SSE-S3, acceso público bloqueado, solo TLS) -> Lambda recolector-diario-bmv
#   (Python 3.11, 512 MB, 60 s, sin VPC, Layer AWSSDKPandas-Python311) ->
#   EventBridge Scheduler DisparadorDiarioBMV -> CloudWatch Logs (7 días) -> Athena
#
# Requisitos: AWS CLI v2 con credenciales activas, python3 con requirements instalados.
#
# Variables:
#   BUCKET      (obligatoria) nombre globalmente único del bucket
#   LAYER_ARN   (obligatoria) ARN de AWSSDKPandas-Python311 para su región. Consúltelo en
#               https://aws-sdk-pandas.readthedocs.io/en/stable/layers.html o en la consola
#               de Lambda > Capas > "Capas de AWS".
#   REGION      (us-east-1)
#   ROLE_ARN    (arn:aws:iam::<cuenta>:role/LabRole)  rol de ejecución de la Lambda
#   SCHEDULER_ROLE_ARN (= ROLE_ARN)                    rol que asume el Scheduler
#   WORKGROUP   (primary)
#
# Uso: BUCKET=prisma-bmv-datalake-xyz LAYER_ARN=arn:aws:lambda:... ./infra/deploy_aws.sh
# =============================================================================
set -euo pipefail

: "${BUCKET:?Defina BUCKET}"
: "${LAYER_ARN:?Defina LAYER_ARN (ver encabezado del script)}"
REGION="${REGION:-us-east-1}"
WORKGROUP="${WORKGROUP:-primary}"
FUNCION="recolector-diario-bmv"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ROLE_ARN="${ROLE_ARN:-arn:aws:iam::${ACCOUNT_ID}:role/LabRole}"
SCHEDULER_ROLE_ARN="${SCHEDULER_ROLE_ARN:-$ROLE_ARN}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
export AWS_DEFAULT_REGION="$REGION"

paso() { printf '\n==> %s\n' "$*"; }

# ---------------------------------------------------------------- 1. S3 -----
paso "Bucket s3://$BUCKET"
if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET"
  else
    aws s3api create-bucket --bucket "$BUCKET" --create-bucket-configuration LocationConstraint="$REGION"
  fi
fi
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":true}]}'
sed "s/\${BUCKET}/$BUCKET/g" "$RAIZ/infra/iam/politica_bucket_solo_tls.json" > /tmp/prisma_bucket_policy.json
aws s3api put-bucket-policy --bucket "$BUCKET" --policy file:///tmp/prisma_bucket_policy.json
# Resultados de Athena: se purgan solos a los 30 días.
aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" --lifecycle-configuration \
  '{"Rules":[{"ID":"purgar-athena-results","Status":"Enabled","Filter":{"Prefix":"athena-results/"},"Expiration":{"Days":30}}]}'

# ------------------------------------------------------- 2. Carga inicial ---
paso "Carga inicial de Silver y Gold"
python3 "$RAIZ/scripts/bootstrap_lakehouse.py" --bucket "$BUCKET" --region "$REGION"

# ------------------------------------------------------------ 3. Lambda -----
paso "Empaquetando Lambda $FUNCION"
TMP="$(mktemp -d)"
cp "$RAIZ/infra/lambda/recolector_diario_bmv/lambda_function.py" "$TMP/"
cp "$RAIZ/prisma/domain/bmv_core.py" "$TMP/"
(cd "$TMP" && zip -q -r lambda.zip lambda_function.py bmv_core.py)
ENV_VARS="Variables={BUCKET_NAME=$BUCKET}"

if aws lambda get-function --function-name "$FUNCION" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FUNCION" --zip-file "fileb://$TMP/lambda.zip" >/dev/null
  aws lambda wait function-updated --function-name "$FUNCION"
  aws lambda update-function-configuration --function-name "$FUNCION" --runtime python3.11 \
    --handler lambda_function.lambda_handler --memory-size 512 --timeout 60 \
    --role "$ROLE_ARN" --layers "$LAYER_ARN" --environment "$ENV_VARS" \
    --vpc-config SubnetIds=[],SecurityGroupIds=[] >/dev/null
else
  aws lambda create-function --function-name "$FUNCION" --runtime python3.11 \
    --handler lambda_function.lambda_handler --memory-size 512 --timeout 60 \
    --role "$ROLE_ARN" --layers "$LAYER_ARN" --environment "$ENV_VARS" \
    --zip-file "fileb://$TMP/lambda.zip" \
    --description "Ingesta diaria del boletin BMV: Bronze, Silver y Gold (sin VPC)" >/dev/null
fi
aws lambda wait function-updated --function-name "$FUNCION"
LAMBDA_ARN="$(aws lambda get-function --function-name "$FUNCION" --query Configuration.FunctionArn --output text)"

# ------------------------------------------------------ 4. CloudWatch -------
paso "Grupo de logs con retención de 7 días"
aws logs create-log-group --log-group-name "/aws/lambda/$FUNCION" 2>/dev/null || true
aws logs put-retention-policy --log-group-name "/aws/lambda/$FUNCION" --retention-in-days 7

# ---------------------------------------------- 5. EventBridge Scheduler ----
paso "Programación DisparadorDiarioBMV (16:45 CDMX, lunes a viernes)"
TARGET="{\"Arn\":\"$LAMBDA_ARN\",\"RoleArn\":\"$SCHEDULER_ROLE_ARN\",\"Input\":\"{}\",\"RetryPolicy\":{\"MaximumRetryAttempts\":2,\"MaximumEventAgeInSeconds\":3600}}"
ARGS=(--name DisparadorDiarioBMV --schedule-expression "cron(45 16 ? * MON-FRI *)"
      --schedule-expression-timezone America/Mexico_City --flexible-time-window Mode=OFF
      --target "$TARGET" --state ENABLED)
if aws scheduler get-schedule --name DisparadorDiarioBMV >/dev/null 2>&1; then
  aws scheduler update-schedule "${ARGS[@]}" >/dev/null
else
  aws scheduler create-schedule "${ARGS[@]}" >/dev/null
fi

# ------------------------------------------------------------ 6. Athena -----
paso "Tablas de Athena"
python3 "$RAIZ/scripts/crear_tablas_athena.py" --bucket "$BUCKET" --region "$REGION" --workgroup "$WORKGROUP"

paso "Listo"
cat <<FIN
Lambda:     $LAMBDA_ARN
Scheduler:  DisparadorDiarioBMV  cron(45 16 ? * MON-FRI *)  America/Mexico_City
Logs:       /aws/lambda/$FUNCION (7 días)
Athena:     prisma_bmv.bmv_silver_ppp, prisma_bmv.bmv_gold_senales_g2, prisma_bmv.bmv_gold_senales_g1

Prueba manual (reprocesa una sesión):
  aws lambda invoke --function-name $FUNCION --cli-binary-format raw-in-base64-out \\
    --payload '{"fecha":"20261030"}' /tmp/salida.json && cat /tmp/salida.json

Terminal contra AWS:
  PRISMA_DATA_SOURCE=athena PRISMA_S3_BUCKET=$BUCKET AWS_REGION=$REGION streamlit run app.py
FIN
