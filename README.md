# Prisma BMV - Quantitative Terminal

Terminal de inteligencia cuantitativa sobre el mercado accionario mexicano. Estima la probabilidad de que el Precio Promedio Ponderado (PPP) oficial de la BMV sea mayor dentro de cinco sesiones hábiles: $Y_t = \mathbb{1}(\mathrm{PPP}_{t+5} > \mathrm{PPP}_t)$.

## Inicio rápido (sin AWS)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
streamlit run app.py
```

La terminal arranca con la instantánea de `datos/` y tres cuentas de demostración con la contraseña `Prisma-Demo-2026`:

| Cuenta | Plan |
|---|---|
| `explorer@demo.prismabmv.com` | Explorer |
| `pro@demo.prismabmv.com` | Professional |
| `enterprise@demo.prismabmv.com` | Enterprise |

En desarrollo, la llave de cifrado se genera sola en `.estado/`. Para producción, siga estos pasos:

```bash
cp .env.example .env
python scripts/generar_llave_maestra.py   # pegue el resultado en PRISMA_MASTER_KEY
# PRISMA_ENV=production y PRISMA_SEED_DEMO=false
```

Para que Prismi responda con Claude, defina `ANTHROPIC_API_KEY`. Sin ella, Prismi responde con el motor local, que usa las mismas cifras del lakehouse.

## Pruebas

```bash
python -m pytest -q
```

La suite tiene 66 pruebas y no necesita AWS. Cubre:

- **Paridad con el registro oficial:** las features y la inferencia G2 reproducen las señales registradas.
- **Cero imputación:** un hueco en la ventana bloquea la emisora, y un hueco en t+5 deja la señal como no evaluable.
- **Lambda contra un S3 simulado:** inmutabilidad de Bronze, idempotencia y divergencia de hash.
- **Seguridad:** PBKDF2, almacén cifrado, bloqueo de cuentas y migración de hashes antiguos.
- **Pasarela sandbox:** nunca guarda el número de tarjeta ni el CVC.
- **Prismi:** guardrails de alcance y de asesoría.
- **Consola SQL:** guardia de solo lectura.
- **Interfaz de extremo a extremo:** cada plan, el checkout y la regla de identidad de marca.

## Planes

| | Explorer ($0) | Professional ($49/mes) | Enterprise ($249/mes) |
|---|---|---|---|
| Boletín BMV | Diferido una sesión | Al cierre (16:45 CDMX) | Al cierre |
| Señales | Modelo base G1 de WALMEX | G1 completo + panel G2 (WALMEX, GMEXICO, GFNORTE, AMX) | Igual que Professional |
| `ret_10_rel_panel` y descomposición | — | ✓ | ✓ |
| Auditoría t+1 a t+5 | WALMEX | Panel completo | Panel completo |
| Prismi con Claude | 5 consultas al día | Ilimitado | Ilimitado |
| SQL sobre Athena / S3 | — | — | ✓ |
| Exportación masiva | — | — | ✓ |
| Auditoría forense SHA-256 | — | — | ✓ |

Todos los derechos se definen en `prisma/plans.py`; ninguna vista compara nombres de plan directamente.

## Estructura

```
app.py                      Orquestador Streamlit
prisma/
  domain/bmv_core.py        Núcleo puro: calendario, parser, ventana de 21, inferencia, seguimiento
  data/                     Repositorios (local, S3, Athena), analítica, SQL, integridad SHA-256
  services/                 Cuentas, pasarela sandbox, Prismi
  security/crypto.py        PBKDF2 y almacén cifrado con Fernet
  ui/                       Tema, componentes y vistas
infra/
  lambda/recolector_diario_bmv/   Lambda (se empaqueta junto con bmv_core.py)
  athena/                   DDL y consultas de referencia
  iam/                      Políticas de mínimo privilegio y bucket solo-TLS
  eventbridge/              Programación DisparadorDiarioBMV
  deploy_aws.sh             Despliegue idempotente
scripts/                    Carga inicial, tablas de Athena, llave maestra, migración de usuarios
datos/                      Instantánea del lakehouse (Silver y Gold) para trabajar sin AWS
docs/                       Arquitectura AWS y auditoría del repositorio de origen
tests/
```

## Despliegue en AWS

Vea `docs/ARQUITECTURA_AWS.md`. En resumen:

```bash
BUCKET=prisma-bmv-datalake-<sufijo> LAYER_ARN=<ARN de AWSSDKPandas-Python311> ./infra/deploy_aws.sh
PRISMA_DATA_SOURCE=athena PRISMA_S3_BUCKET=<bucket> streamlit run app.py
```

## Aviso

Las señales de Prisma BMV son probabilidades estadísticas. No constituyen recomendación, asesoría ni mandato de compra o venta de valores.

## Otros componentes del repositorio

- `frontend/`: sitio web React/Vite con la mascota Prismi, el recorrido guiado
  (`components/Mascot.jsx`, `Tour.jsx`, `Guide.jsx`, `guide/tour.mjs`) y el acceso con Supabase.
  Requiere Node 20 o superior. Copie `frontend/env.example` a `frontend/.env` y ejecute
  `npm ci && npm run dev`.
- `api.py`: API FastAPI que usa el frontend (valida el token de Supabase en `/api/me`).
  Lee `.env` de la raíz (ver `env.example`): `uvicorn api:app --reload`.
- Los scripts `*.py` de la raíz son la investigación original y no forman parte de la terminal.
