# Arquitectura para cuenta educativa AWS

**Estado:** adaptación local preparada; conexión completa y publicación todavía
no validadas. Revisión: 19-11-2026, cuenta `886457183564`, región `us-east-1`.

La exploración posterior de publicación creó una aplicación Amplify vacía, sin
desplegar la web, y comprobó que EC2 responde positivamente a `DryRun`. Detalles
y límites de presupuesto en `docs/ESTADO_DESPLIEGUE_PUBLICO_EDUCATIVO.md`.
Posteriormente se creó un laboratorio vacío Cognito/DynamoDB, aún no conectado
al frontend ni a la API; ver `docs/MIGRACION_SUPABASE_A_COGNITO.md`.

## Evidencia y restricciones

AWS indica que [AWS Academy Learner Lab](https://aws.amazon.com/training/awsacademy/)
da acceso a servicios seleccionados y a un presupuesto de laboratorio; esa
descripción pública no identifica los permisos concretos de esta cuenta ni
garantiza disponibilidad perpetua o costo cero. En [IAM](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html)
un permiso depende de las políticas aplicables. Una respuesta `AccessDenied`
para listar un servicio no demuestra que todas sus operaciones estén
prohibidas, aunque el usuario confirmó que no dispone de App Runner ni
CloudFront. Se excluyen ambos de la propuesta.

Pruebas observadas, no una promesa de acceso futuro:

| Operación | Evidencia |
|---|---|
| S3 | `HeadBucket` del lake exitoso; `HeadObject` de Silver, G1 y G2 exitosos |
| Glue | lectura de `default.bmv_silver_ppp` y listado de tablas exitosos |
| Athena | workgroup `primary` habilitado; lectura Silver probada anteriormente |
| Lambda | función de ingesta y Lambda de laboratorio existentes; captura aislada probada anteriormente |
| Scheduler | lectura de programación de ingesta existente exitosa |
| CloudFormation | stacks de laboratorio creados y descritos anteriormente |
| EC2 | se listó una instancia de otro proyecto; no se reutiliza |
| API Gateway | listado REST y v2 vacío; esto no prueba permiso de crear |

En la consulta actual, Glue `default` **no tiene `bmv_gold_senales_g1`**.
El repositorio Athena existente espera esa tabla; no se declara funcional la
terminal completa sobre Athena. La lectura del workgroup no prueba ejecución
de consultas. Athena [cobra por consultas](https://docs.aws.amazon.com/athena/latest/ug/what-is.html)
y S3, Lambda, logs, almacenamiento y transferencia también pueden consumir
presupuesto; no se promete gratuidad. Confirmar crédito, límites y duración
del laboratorio con el docente antes de crear recursos.

## Arquitectura adaptada

```text
BMV -> Lambda y Scheduler existentes -> S3 Bronze/Silver/Gold
                                           |-> Glue + Athena (análisis controlado)
                                           |-> Streamlit en la computadora local
                                                usando S3 y credenciales temporales
React + FastAPI locales -> archivos locales (ruta actual, independiente)
```

La interfaz local no necesita App Runner, CloudFront, servidor público,
instancia nueva ni exponer puertos a Internet. S3 sigue privado. Este diseño
es para demostración y desarrollo; la sesión de laboratorio puede detenerse o
caducar, por lo que **no es un servicio público persistente ni arquitectura
productiva**. No se copia ni modifica el lake existente.

Hay dos interfaces distintas: Streamlit puede configurarse para leer S3, pero
FastAPI y React conservan sus fuentes locales actuales. No se afirma que las
dos interfaces muestren los mismos datos ni que FastAPI use S3. Macro puede
configurarse por separado. Las consultas S3 leen archivos por separado: no
garantizan una instantánea transaccional entre Silver, G1 y G2.

## Ajuste implementado para Streamlit y S3

El repositorio S3 permite ahora seleccionar explícitamente
`PRISMA_S3_MODELOS_KEY`. Sin la variable conserva el valor anterior
`gold/modelos/registro_modelos_g2_oficial.json`, evitando cambios silenciosos.
En este entorno la búsqueda de metadatos mostró que la ruta anterior responde
404 y que existe `modelos/registro_modelos_g2_oficial.json`; la nueva variable
permite elegir esta última **sin copiar ni sobrescribir el objeto**. La
existencia del objeto no confirma que todo su contenido o las vistas sean
compatibles.

Para una prueba manual local, con dependencias y credenciales temporales
instaladas y vigentes, configurar en PowerShell solo para la sesión:

```powershell
$env:PRISMA_DATA_SOURCE = "s3"
$env:AWS_REGION = "us-east-1"
$env:PRISMA_S3_BUCKET = "prisma-bmv-datalake-tunombre-2026"
$env:PRISMA_S3_MODELOS_KEY = "modelos/registro_modelos_g2_oficial.json"
python -m streamlit run app.py --server.address 127.0.0.1
```

Solo instalar dependencias del proyecto en un entorno virtual controlado.
No colocar claves o tokens en código, Markdown, frontend o repositorio; utilizar
el mecanismo temporal del laboratorio. Ejecutar en local no equivale a
autorizar redistribución de datos. Las cuentas demo no son seguridad de
producción. Se requiere comprobar integridad, fechas, G1/G2 y permisos de
visualización antes de compartir capturas o resultados.

No se pudo hacer prueba integral Streamlit-S3 en el intérprete actual: falta
`boto3` (figura en `requirements.txt`). Tests de selección de clave usan un
S3 simulado. No se instaló nada ni se modificó el entorno del usuario.

## Comprobación repetible, sin escrituras

Con dependencias instaladas:

```powershell
python scripts/diagnostico_aws_educativo.py --region us-east-1 --bucket prisma-bmv-datalake-tunombre-2026 --database default
```

Solo consulta identidad, `HeadBucket`, metadatos Glue, workgroup Athena,
configuración Lambda y Scheduler. No imprime secretos ni valores retornados,
ni ejecuta SQL, invoca Lambda, crea recursos o cambia permisos. `LECTURA_OK`
aplica únicamente a esa operación; no certifica acceso a cada objeto,
permisos de escritura o ausencia de costos. En este intérprete el script se
detuvo por falta de `boto3`; las comprobaciones equivalentes enumeradas arriba
se hicieron con AWS CLI. El test automatizado usa dobles.

## Pendientes antes de usar como servicio

1. Instalar dependencias en un entorno virtual y probar Streamlit-S3 de extremo
   a extremo, comprobando esquema, fechas, actualización, G1 y G2.
2. Si se desea Athena en la interfaz, diseñar y validar por separado la fuente
   G1 ausente, sin crear tablas o alterar contratos productivos sin aprobación.
3. Resolver credenciales temporales, permisos mínimos y revisión de costos,
   expiración y eventual eliminación de recursos del laboratorio.
4. Diseñar acceso remoto seguro solo si es necesario: EC2 y acceso privado son
   opciones a evaluar, no recursos verificados como disponibles para crear ni
   gratis. No reutilizar la instancia de otro proyecto.
5. Mantener pendientes la fuente PPP completa, catálogo IPC fechado y validación
   de modelos; este cambio de infraestructura no los resuelve.
