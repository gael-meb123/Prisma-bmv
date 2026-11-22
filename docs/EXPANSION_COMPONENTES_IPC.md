# Expansión de Prisma BMV a los componentes del IPC

Estado del documento: inventario inicial parcial; contrato Gold corregido en AWS.
Revisión: 18 de noviembre de 2026.

## Objetivo y reglas

Incorporar los componentes y series vigentes del S&P/BMV IPC a captura, mercado
y estadística, y considerar señales y consenso únicamente después de validar
datos, modelos y autorización. La composición cambia: «35» es la meta solicitada,
no un catálogo confirmado ni una constante permanente.

- Conservar los datos y señales emitidos con su universo y metodología originales.
- No imputar PPP faltantes, copiar escaladores de otras emisoras ni presentar
  métricas del panel anterior como validación del universo ampliado.
- Separar pertenencia al índice, disponibilidad de precios, acceso por plan y
  elegibilidad por modelo. La clave debe distinguir emisora y serie.
- No desplegar ni modificar AWS hasta verificar recursos reales y aprobar la
  migración. Los cambios locales existentes deben preservarse.
- Cada fase requiere pruebas y aprobación antes de pasar a producción; las
  decisiones de señales y de planes de acceso requieren confirmación.

## Lista de pasos y criterios de aceptación

Avance local de reconciliación, pruebas de calidad, adaptador gratuito,
revisión de API y diseño de catálogo: `docs/AVANCE_PENDIENTES_CAPTURA_IPC.md`.
No constituye despliegue ni cierre de las fases.

### 0. Inventario y fuentes — EN CURSO

- [x] Revisar catálogo, fuentes locales y las implementaciones de Lambda y modelos.
- [x] Intentar verificar composición oficial y acceso a AWS; registrar resultados.
- [ ] Obtener composición oficial o autorizada, con fecha de corte, fuente,
  vigencia y series exactas; comparar con el catálogo actual.
- [x] Identificar referencia provisional NAFTRAC y contrastar ejemplos de
  precios con el boletín BMV; ver `docs/IPC_CANDIDATOS_20261117.md`.
- [ ] Confirmar disponibilidad, cobertura, licencia y características del boletín
  y del historial, incluidas acciones corporativas y ajustes.
- [x] Con credenciales vigentes, inventariar AWS en modo solo lectura y comparar
  el paquete desplegado, configuración y artefactos disponibles.
- [x] Probar lectura efectiva de Silver, Gold e histórico en Athena.
- [x] Corregir y comprobar el contrato Gold de la Lambda activa en Glue.
- [ ] Confirmar fuentes de la API desplegada y procedencia efectiva de los
  parámetros durante cada ejecución.
- [ ] Elegir y documentar la ruta operativa de ingesta e inferencia y definir
  responsable y criterios de aprobación.

**Cierre:** fuente y universo verificables; inventario AWS y diferencias
documentados; faltantes, permisos y riesgos resueltos o aceptados explícitamente.

### 1. Catálogo versionado

- [x] Construir instantánea provisional versionada y lector aislado para los
  15 actuales y 20 candidatos, sin integrarlo en captura ni producción.
- [ ] Definir esquema con identificador, emisora, serie, nombre, sector, alias,
  fuente, fecha de consulta, vigencia y versión; conservar bajas y cambios de serie.
- [ ] Preparar catálogo inicial cotejado con fuente autorizada y pruebas de
  unicidad, vigencia, alias y claves por emisora/serie.
- [ ] Sustituir listas duplicadas en dominio, API y frontend; mantener
  autorización en backend y cobertura independiente de elegibilidad de modelos.
- [ ] Definir proceso de actualización y responsable ante rebalanceos.

**Cierre:** catálogo reproducible y fechado, sin ambigüedades ni cambios
retroactivos silenciosos; permisos probados.

#### Instantánea de referencia implementada

`prisma/domain/catalogos/naftrac_2026-11-17_v1.json` registra el corte,
procedencia, 15 pares del catálogo actual y 20 pares propuestos a partir de los
tickers de la cartera NAFTRAC. **No confirma composición del índice ni
vigencias**: los 35 tienen estado provisional, incluso los 15 existentes.
Los 20 pares nuevos son propuestas, no verificación de series; en particular
`RA` se propone como `R` / `A` y debe contrastarse. `LIVEPOLC.1` se vincula
provisionalmente al par local `LIVEPOL` / `C-1`.

`prisma/domain/catalogo_ipc.py` carga explícitamente esa versión, valida claves
y alias duplicados por fuente y resuelve únicamente el corte de la instantánea.
El alias `blackrock` es el símbolo publicado en la cartera; el alias `yahoo`
solo se incluyó para las 15 claves que ya tenían mapeo en
`lambda_function_con_ia.py`. Estos alias también son propuestas y no acreditan
disponibilidad ni licencia; los 20 nuevos conservan `null`.
No se derivan automáticamente símbolos Yahoo ni se quita puntuación.

Uso de consulta, fuera de producción:

```python
from datetime import date
from prisma.domain.catalogo_ipc import catalogo_naftrac_20261117

catalogo = catalogo_naftrac_20261117()
candidato = catalogo.resolver("blackrock", "LIVEPOLC.1", date(2026, 11, 17))
# candidato.emisora == "LIVEPOL"; candidato.serie == "C-1"
# candidato.estado_mapeo == "PROPUESTO_PENDIENTE_VERIFICACION"
```

La lectura para cualquier otra fecha falla, ya que un corte no prueba una
vigencia. No se habilitan permisos, datos de mercado ni señales. Una composición
oficial futura debe guardarse como una versión nueva, con fuente y vigencias
comprobadas, sin sobrescribir esta instantánea. Sigue pendiente integrar un
catálogo de producción tras validar identidades, series, permisos y fuentes.

### 2. Ingesta y calidad

- [x] Crear y probar una captura **local aislada** para el corte provisional,
  sin S3 ni inferencia; véase el resultado más abajo.
- [ ] Adaptar extracción del boletín y pruebas con ejemplos reales autorizados
  de todas las series; distinguir fuente primaria y contingencias.
- [ ] Conservar HTML, URL, hash, fecha y versión de catálogo; registrar
  publicados, ausentes, inválidos y errores de extracción sin inventar datos.
- [ ] Validar duplicados por fecha/emisora/serie, valores y cambios corporativos.
- [ ] Diseñar reintentos, concurrencia e idempotencia; separar resultados
  de Bronze, Silver e inferencia.
- [ ] Ejecutar pruebas con huecos, boletines cambiados, series ambiguas,
  errores de red y ejecuciones repetidas.

**Cierre:** cobertura reconciliada contra la fuente por sesión y sin duplicados.

#### Captura local aislada del corte provisional

`scripts/captura_ampliada_aislada.py` usa el catálogo de
`2026-11-17` y `prisma/data/captura_ampliada.py`. Solo admite ese corte, ya
que el catálogo no establece vigencia en otras fechas. No invoca Yahoo ni
produce Gold, señales, permisos, cambios en producción o escrituras en AWS.
Si la fecha del HTML no es inequívoca, no coincide con el corte o no existen
tablas de cotizaciones con el encabezado esperado, la ejecución falla.

Cada pareja propuesta produce una fila, incluyendo estado de composición y
mapeo provisional. Se conservan celdas vacías; precios no positivos, filas
incompletas o duplicados contradictorios bloquean esa fila. Una clave no
encontrada en las tablas seleccionadas no implica que no se haya negociado.
El boletín contiene solo tablas parciales. No se sustituye ningún PPP por
cierre secundario.

Ejemplo de ejecución (el directorio de salida **no debe existir**):

```powershell
python scripts/captura_ampliada_aislada.py --fecha 2026-11-17 --descargar --salida <directorio-nuevo>
```

Se crean `boletin.html`, `precios_provisionales.csv` y `manifiesto.json`, con
URL, SHA-256, fecha, versión de catálogo y conteos. `--html <archivo>` permite
usar un archivo local, pero en ese caso la URL BMV es solo una fuente declarada
y no verifica su procedencia. Si falla una escritura puede quedar un directorio
parcial; no se sobrescribe automáticamente.

Prueba ejecutada en
`C:\Users\GAELMENDOZABALLARDO\AppData\Local\Temp\opencode\prisma-captura-ampliada-20261117-v1`:
35 filas, 16 observaciones PPP con mapeo provisional y 19 no encontradas en
las tablas. Los cuatro candidatos nuevos observados fueron KIMBER A (39.43),
GCARSO A1 (174.11), ALSEA * (58.19) y VOLAR A (15.14). Las 15 claves actuales
coincidieron en precio o hueco con una copia de Silver del 17-11-2026 consultada
anteriormente; no se trata de una auditoría integral. Se identificaron tres
tablas con encabezado reconocido, y el HTML descargado tiene SHA-256
`7dbe5e4f54129c70a037aa0e8010f8cf17b7abc5b8ab4b64be9ed165a5b7a044`.
Este resultado vive en un directorio temporal local, no en S3; se debe acordar
su conservación conforme a la autorización recibida.

Pendiente: verificar pares y composición oficial, probar más formatos y fechas
con catálogos correspondientes, validación independiente y permisos de otras
fuentes.

#### Ejecución AWS aislada

Se desplegó y probó el recolector en el stack independiente
`prisma-bmv-captura-aislada-2026`, con tabla
`prisma_bmv_captura_aislada_2026.silver_captura_provisional_v1` y bucket propio.
Athena confirmó 35 pares únicos, 16 PPP y 19 huecos. Los datos extraídos
coincidieron con la captura local excepto el SHA-256 del HTML: las dos copias
diferían en un script dinámico posterior al HTML. Se agregó una barrera para
rechazar una segunda firma de la misma fecha; una reejecución real fue
bloqueada y no creó un segundo Silver. Hay un solo catálogo fechado, por lo que
la sesión 2026-11-18 fue rechazada antes de descargar. Se requieren otros
catálogos fechados para evaluar otras sesiones.

Los recursos permanecen en AWS y pueden generar costos. No existe Scheduler,
Gold, inferencia ni promoción productiva. El procedimiento y limitaciones están
en `docs/ARQUITECTURA_AWS.md`, sección «Laboratorio AWS de captura provisional».

#### Reporte por clave

`docs/REPORTE_VALIDACION_35_PPP_20261117.md` reúne las 35 claves, su evidencia
BMV, presencia en NAFTRAC y disponibilidad puntual de PPP. Se observaron 16
pares con PPP, `MEGA CPO` solo en paquetes sin PPP y otros 18 no observados en
las tablas revisadas. Ninguna de esas evidencias confirma por sí sola la
pertenencia oficial al IPC. La composición y los alias ambiguos siguen pendientes.

#### Investigación de fuente PPP

`docs/INVESTIGACION_FUENTE_BMV_PPP.md` identifica el Web Service oficial
`obtenQuoteEmisorasMC`, cuyo esquema documentado incluye PPP por emisora y
serie. El WSDL público respondió, pero faltan credenciales y autorización
específica para una prueba de datos; tampoco se ha demostrado acceso histórico
ni se compararon sus valores con el boletín. Las bases históricas de BMV son
otra candidata, sin PPP confirmado en su descripción pública.

Prueba gratuita intradía del 19-11-2026: la página de Capitales devolvió los
35 pares de referencia, pero el campo PPP fue cero para las 96 acciones
recibidas. No hay PPP utilizable en esa respuesta. Detalles y próximos pasos
en `docs/PRUEBA_CAPITALES_BMV_20261119.md`.

### 3. Historia y backfill

- [ ] Inventariar fuentes históricas, licencias, rango, calidad y ajustes;
  acordar qué representan PPP, cierre y precios ajustados.
- [ ] Preparar carga histórica trazable en área aislada; preservar faltantes,
  origen y vigencia del componente, sin mezclar precios no equivalentes.
- [ ] Conciliar cantidades y muestras con la fuente y documentar cobertura por
  serie y fecha. Separar datos históricos de captura prospectiva.

**Cierre:** cobertura y limitaciones verificadas; o comenzar captura prospectiva
cuando no exista historia autorizada.

### 4. Datos y migración AWS

- [ ] Diseñar prefijos versionados separados para pruebas y producción y un
  manifiesto con esquema, universo y procedencia.
- [ ] Mantener Bronze original y evitar que Athena lea simultáneamente archivos
  duplicados; diseñar tablas/vistas por versión y política de unión.
- [ ] Acordar contrato de columnas: OpenCSVSerde lee por posición; si cambia el
  esquema, coordinar DDL, productores y consumidores.
- [ ] Respaldar referencias actuales y preparar reversión comprobable; no
  sobrescribir señales históricas ni asumir que los históricos usan 35 componentes.
- [ ] Comprobar IAM, cifrado, costos, particiones y consultas; medir memoria y
  duración de Lambda antes de modificar capacidad.

**Cierre:** consultas reconciliadas, migración y reversión probadas en aislamiento.

### 5. API, permisos y dashboard

- [ ] Hacer que selector y filtros consulten el catálogo; revisar textos con
  «15» y añadir búsqueda por emisora/serie.
- [ ] Definir cobertura por plan con el usuario y verificar permisos en backend.
- [ ] Conectar mercado y estadísticas a la fuente de datos aprobada; identificar
  muestras de 15 y universo ampliado, cobertura y datos insuficientes.
- [ ] Mostrar estados diferenciados: sin dato, historia insuficiente, modelo
  no validado y señal disponible. Probar acceso, filtros y presentación.

**Cierre:** ninguna emisora ni métrica se presenta como disponible si no lo está.

### 6. Modelos y consenso — sujeta a decisión y validación

- [ ] Inventariar artefactos, modelos, series, escaladores y universo operativo;
  resolver discrepancias entre rutas antes de generar nuevas señales.
- [ ] Evaluar datos suficientes y tratamiento de dividendos; versionar variables,
  parámetros y composición del panel. Revisar cómo cambian variables relativas
  incluso para emisoras existentes.
- [ ] Diseñar entrenamiento y escalado sin fuga temporal; comparar referencias,
  pruebas cronológicas y resultados por emisora y sector.
- [ ] Probar nuevos modelos en shadow y definir criterios de promoción y
  monitoreo; nunca usar como sustituto automático el escalador de otra emisora.
- [ ] Activar señal por modelo y emisora solo con aprobación; el consenso debe
  exigir sus participantes y horizontes correctos y mostrar cobertura incompleta.

**Cierre:** informe de validación aprobado, versiones y límites claramente
identificados; el alcance puede mantenerse en mercado y estadística.

### 7. Despliegue, operación y seguimiento

- [ ] En ambiente aislado, comparar ejecuciones anterior y nueva, incluidos
  datos, señales existentes, cobertura, latencia, costos y permisos.
- [ ] Configurar alertas de captura parcial, errores Gold, ventanas, costos y
  anomalías; probar recuperación y reprocesamiento.
- [ ] Aprobar ventana de despliegue, responsables, criterios de aceptación,
  respaldo y reversión. Promover gradualmente sin mezclar versiones.
- [ ] Monitorear sesiones posteriores y documentar alta/baja de componentes.

**Cierre:** resultados reconciliados y operación y reversión verificadas.

## Resultado del punto 0: evidencia inicial

### Composición y fuentes

| Evidencia | Resultado |
|---|---|
| [Ficha oficial S&P/BMV IPC](https://www.spglobal.com/spdji/en/indices/equity/sp-bmv-ipc/) | Intento de consulta recibió HTTP 403; no se obtuvo composición ni fecha vigente. |
| Búsqueda web de componentes oficiales | El servicio de búsqueda devolvió HTTP 402. No se pudo corroborar un listado alternativo autorizado. |
| `prisma/domain/bmv_core.py`, `EMISORAS_15` | Catálogo local: GMEXICO B, GFNORTE O, FEMSA UBD, AMX B, WALMEX *, CEMEX CPO, PE&OLES *, GAP B, AC *, ASUR B, BIMBO A, GFINBUR O, VESTA *, LIVEPOL C-1 y GRUMA B. **No demuestra pertenencia actual al IPC.** |
| `prisma/domain/bmv_core.py`, `url_boletin` | Usa `https://www.bmv.com.mx/docs-pub/rss/boletinYYYYMMDD.html` para cotizaciones; no constituye una lista oficial de componentes. |
| `lambda_function.py` y `lambda_function_con_ia.py` | Incluyen contingencia Yahoo Finance; se debe comprobar semántica, permisos y procedencia antes de tratar esos precios como equivalentes al PPP BMV. |
| `core/terminal_api.py` y `prisma/data/estadistica_descriptiva.py` | Estadística lee los archivos locales `serie_ppp_historica_15_emisoras_bmv.csv` y `dataset_panel_15_emisoras_features_ajustado_fase1.csv`. Cobertura y autorización de historia adicional aún no confirmadas. |

**Pendiente:** obtener un archivo o enlace oficial/autorizado con fecha de
efectividad y series, verificar su licencia y calcular altas y bajas por clave
emisora/serie. No se puede afirmar que faltan exactamente 20 componentes sin ese
cotejo.

### AWS: acceso inicial y estado documentado

El intento inicial de `aws sts get-caller-identity` devolvió `ExpiredToken`.
Tras renovar credenciales se completó el inventario de solo lectura descrito
abajo. No se efectuaron escrituras en AWS ni despliegues.

`infra/deploy_aws.sh` y `docs/ARQUITECTURA_AWS.md` describen, pero **no prueban
que estén activos**, `recolector-diario-bmv` (Python 3.11, 512 MB, 60 s),
Scheduler `DisparadorDiarioBMV`, Bronze/Silver/Gold en S3 y tablas Athena.
El script empaqueta la Lambda de `infra/lambda/recolector_diario_bmv/` junto con
`prisma/domain/bmv_core.py`. No ejecutar el script para inventariar: crea y
modifica recursos.

Al renovar credenciales, realizar consultas **solo lectura**, en la región y
cuenta confirmadas, sin publicar credenciales, variables sensibles ni URLs
firmadas. Ejemplos (sustituir `<region>`):

```powershell
aws sts get-caller-identity
aws lambda list-functions --region <region> --query "Functions[].{Nombre:FunctionName,Runtime:Runtime,Handler:Handler,Modificada:LastModified,Hash:CodeSha256}"
aws lambda get-function-configuration --region <region> --function-name recolector-diario-bmv --query "{Nombre:FunctionName,Runtime:Runtime,Handler:Handler,Memoria:MemorySize,Timeout:Timeout,Hash:CodeSha256,Modificada:LastModified,Layers:Layers[].Arn}"
aws scheduler get-schedule --region <region> --name DisparadorDiarioBMV --query "{Estado:State,Expresion:ScheduleExpression,Zona:ScheduleExpressionTimezone,Destino:Target.Arn}"
aws s3api list-buckets --query "Buckets[].Name"
aws glue get-databases --region <region> --query "DatabaseList[].Name"
aws logs describe-log-groups --region <region> --log-group-name-prefix /aws/lambda/recolector-diario-bmv --query "logGroups[].{Nombre:logGroupName,Retencion:retentionInDays}"
```

Identificar el grupo del Scheduler si no es el predeterminado, región, bucket,
alias y versiones reales; luego revisar prefijos, tablas, versiones de objetos y
artefactos con permisos adecuados. Comparar `CodeSha256` del paquete desplegado
con el artefacto exacto de despliegue, no directamente con el hash de un archivo
fuente. Si se necesita inspeccionar el ZIP, tratar la URL temporal como sensible.
No imprimir variables de entorno ni logs que puedan contener secretos.

### Discrepancias y riesgos locales

| Elemento | Evidencia | Implicación |
|---|---|---|
| Núcleo de Lambda documentada | `prisma/domain/bmv_core.py`: 15 en captura, cuatro en `EMISORAS_PANEL_G2`, tres en `MODELOS_G2_ORDEN`, 21 sesiones; `probabilidad_g2` requiere escalador por emisora. | No asumir inferencia de cinco modelos ni cobertura de 15 o 35 en esta ruta. |
| Monitor y terminal | `monitor_prospectivo_segunda_generacion.py` define cinco G2; `core/terminal_api.py` espera cinco en `/consenso`. | Si esa API recibiera solo las tres señales del núcleo, el consenso sería incompleto. Debe verificarse su fuente efectiva y versión desplegada. |
| Lambda alternativa | `lambda_function_con_ia.py`, `inferir_modelos_g2`: V1–V4 usan respaldo `scalers_map["WALMEX"]` si falta el escalador de la emisora; `inferir_modelo_g2_v4_f1_gap` permite respaldo global o WALMEX. | Riesgo de inferencias con escalador ajeno. No demuestra uso en AWS ni valida el respaldo; resolver antes de ampliar inferencia. |
| Ingesta Silver | `infra/lambda/recolector_diario_bmv/lambda_function.py`: archivo diario `ppp_15_emisoras_...`; `actualizar_serie` deduplica por fecha y emisora, no serie. | Versionar ruta y revisar identidad para evitar perder series o duplicar lecturas. |
| Estado Gold | La Lambda documentada captura errores de inferencia en `inferencia_g2`, pero puede retornar `estado=EXITO` y HTTP 200. | No interpretar el estado general como éxito de Gold; observabilidad y estados deben separarse. |
| Contrato Athena | `infra/athena/02_bmv_silver_ppp.sql` usa OpenCSVSerde por posición y prefijo Silver actual. | Coordinar esquema y rutas; no mezclar archivos equivalentes de versiones distintas. |
| API estadística | `/estadistica` lee CSV locales con nombres del panel de 15. | Tener repositorios S3/Athena no prueba que esta API consuma esos datos. |

### Para completar el primer punto

1. Completar las pruebas de lectura de Athena y confirmar la ubicación y las
   fuentes de datos de la API desplegada; cotejar procedencia efectiva de modelos.
2. Proporcionar enlace o documento autorizado de componentes del IPC, incluida
   fecha de vigencia, y confirmar los derechos de uso de datos e historial.
3. Registrar diferencias entre lista oficial y catálogo local por emisora/serie.
4. Decidir ruta operativa y alcance de señales después de revisar los resultados.

## Actualización: inventario AWS con credenciales vigentes

Consulta del 18 de noviembre de 2026, región configurada `us-east-1`, cuenta
terminada en `3564`. Se usaron operaciones de lectura; se descargaron copias
temporales locales para comparar el ZIP y examinar metadatos de dos archivos.
Los nombres de recursos y hallazgos reflejan ese momento, no garantizan que
permanezcan iguales.

### Recursos operativos

| Recurso | Observado | Diferencia o pendiente |
|---|---|---|
| Lambda `recolector-diario-bmv` | Python 3.11, 512 MB, **120 s**, capa AWSSDKPandas Python 3.11 versión 35, sin VPC, rol `LabRole`, versión `$LATEST`; sin alias publicados. | El despliegue documentado propone 60 s. No modificar capacidad sin medir. |
| Paquete desplegado | SHA-256 de ZIP en Base64 `7Uq9nYsV6NU7ZUTJGlFD32u3Q+mhXNMIs82kFf+hYyE=` coincide con `CodeSha256`; contiene solo `lambda_function.py`. Su SHA-256 hexadecimal `c916382a70496465f8b6e171ebc45711bb003a4c2c2809802fe776b311f9ee16` coincide byte a byte con `lambda_function_con_ia.py` local. | **No es** el paquete de `infra/deploy_aws.sh`, que incluye la Lambda de `infra/` y `bmv_core.py`. Ejecutar ese script sustituiría la implementación activa; no hacerlo sin una migración aprobada. |
| Scheduler `DisparadorDiarioBMV` | Habilitado, destino `recolector-diario-bmv`, cron `45 16 ? * MON-FRI *`, zona `America/Mexico_City`. | Política observada: cero reintentos y edad máxima 86400 s; difiere de la configuración documentada de dos reintentos y 3600 s. Esto no comprueba el resultado de las invocaciones. |
| S3 `prisma-bmv-datalake-tunombre-2026` | Prefijos `bronze/`, `silver/`, `gold/`, `modelos/`, entre otros. Silver diario y serie reciente; Gold G1/G2 y registros de modelos están presentes. | Presencia de objetos no prueba integridad, autorización de fuente ni conexión de la API web. |
| Glue/Athena | Solo base Glue `default`; contiene `bmv_silver_ppp`, `bmv_gold_senales_g2` y `serie_historica_15_emisoras`. Workgroup `primary` habilitado. | La arquitectura documenta base `prisma_bmv`; no se encontró en esta región. No se ejecutaron consultas Athena. |
| CloudWatch | Existe `/aws/lambda/recolector-diario-bmv`; `retentionInDays` ausente, sin límite de retención configurado en el grupo observado. | La documentación indica siete días. No se inspeccionó el contenido de logs ni se ajustó la retención. |
| Lambda macro | Existe `prisma-bmv-macro-stream` y regla EventBridge `prisma-bmv-macro-refresh-rule` habilitada. | Es independiente del alcance IPC; no se auditó su funcionamiento. |

### Modelos y datos observados

- La Lambda activa define 15 componentes de captura y un panel de inferencia de
  **AMX, FEMSA, GFNORTE, GMEXICO y WALMEX**, frente a cuatro en el núcleo de
  `infra/`; su implementación incorpora cinco G2 y un challenger `G2_V4_F1_GAP`.
- El código desplegado busca primero registros locales, luego
  `modelos/registro_modelos_g2_v2.json` y `modelos/registro_modelos_g2_oficial.json`
  en S3 y finalmente usa parámetros internos. El ZIP inspeccionado no contiene
  esos JSON; ambos objetos existen en S3. El v2 contiene V4 y sería aceptado por
  el control del código, **si la lectura tiene éxito**. No se comprobó mediante
  logs qué registro usó cada ejecución.
- El v2 examinado contiene escaladores V1/V2 para AMX, CEMEX, FEMSA, GFNORTE,
  GMEXICO y WALMEX, y V3/V4 también para AC, GAP y PE&OLES. V5 usa una estructura
  distinta, por lo que no se infiere su cobertura a partir de esos campos.
- El código desplegado contiene el respaldo a WALMEX descrito arriba. La
  existencia del respaldo **no prueba que se haya utilizado**: en el v2 examinado
  los cinco integrantes del panel tienen escaladores propios para V1–V4. No se
  ha auditado cada ejecución ni la ruta F1.
- El registro Gold de S3 tenía 344 filas, fechas de señal entre 2026-10-28 y
  2026-11-17, cinco emisoras del panel y seis identificadores: los cinco G2
  esperados y `G2_V4_F1_GAP`. Estos conteos no prueban completitud ni validación.
- La API local `core/terminal_api.py` instancia `RepositorioLocal` directamente
  y la estadística lee CSV locales. Esto confirma el comportamiento del código
  local, no el origen efectivo de una API desplegada ni su sincronización.

### Contratos Glue y CSV: hallazgos previos a la corrección

- La tabla `default.bmv_gold_senales_g2` usa OpenCSVSerde y declara
  `fecha_objetivo_h5` como cuarta columna, pero el CSV Gold inspeccionado tiene
  `muestra_evaluacion` en esa posición y `fecha_objetivo_h5` en la quinta. Hay
  42 columnas en el CSV y 33 declaradas en la tabla anterior. Como el serde lee
  por posición, existía un **desplazamiento de columnas**. La consulta posterior
  lo confirmó y la tabla fue corregida como se documenta al final.
- La tabla `default.bmv_silver_ppp` usa OpenCSVSerde sin claves de partición;
  el archivo diario del 17 de noviembre inspeccionado tiene 15 filas y sus 13
  encabezados coinciden en orden con las 13 columnas declaradas. No se
  inspeccionaron todos los archivos ni la lectura real de Athena.
- La serie unificada de la Lambda activa deduplica por `fecha` y `emisora` y
  reemplaza registros por fecha. Antes de admitir múltiples series hay que
  rediseñar esas operaciones y probar reconciliación parcial.

### Pendientes tras el acceso

1. Mantener verificaciones del contrato Gold corregido; véase la sección final.
2. Identificar despliegue y origen real de la API, y cotejar los registros de
   modelos efectivamente utilizados sin exponer secretos.
3. Obtener la composición oficial/autorizada con fecha y serie; verificar
   fuentes, licencia y cobertura histórica.
4. Decidir tratamiento de contingencias, contratos, modelos y reversión antes
   de modificar el código operativo o infraestructura.

## Verificación de composición, historial y Athena

Revisión: 18 de noviembre de 2026. El usuario autorizó expresamente las consultas
Athena. Se ejecutaron cuatro consultas `SELECT` en `default`, workgroup `primary`;
se crearon archivos de resultados en el prefijo `athena-results/`. No se
modificaron tablas, fuentes ni configuraciones.

**Actualización posterior:** el usuario indica que BMV concedió autorización
para recolectar datos de sus boletines. No se ha revisado el documento ni su
alcance específico; documentar condiciones, plazo y usos permitidos antes del
despliegue. La autorización no establece por sí sola derechos sobre terceros.

### Composición oficial del IPC

- La [página oficial de índices BMV](https://www.bmv.com.mx/en/indices/main/)
  muestra una sección «Constituents List», pero la respuesta accesible contiene
  plantillas dinámicas sin nombres ni fecha de composición. No permitió extraer
  o verificar el universo.
- La [ficha de S&P/BMV IPC](https://www.spglobal.com/spdji/en/indices/equity/sp-bmv-ipc/)
  y el PDF de metodología de S&P devolvieron HTTP 403 en este entorno; la búsqueda
  web devolvió 402. No se confirmó una lista ni fecha de vigencia.
- La BMV publica en su página el contacto de índices:
  [indices@grupobmv.com.mx](mailto:indices@grupobmv.com.mx). Solicitar listado
  autorizado con emisora, serie, fecha efectiva y condiciones de uso. También se
  puede aportar una constancia o listado del proveedor autorizado.

**Conclusión:** composición vigente y diferencia respecto a los 15 no verificadas.
No tomar las listas actuales del repositorio como prueba de pertenencia al IPC.

### Disponibilidad y derechos del histórico

- Athena leyó `default.serie_historica_15_emisoras`: **37 725 filas**, de
  2016-10-27 a 2026-10-28, para 15 emisoras. La agregación cuenta 21 157 registros
  `PPP_PUBLICADO_VERIFICADO`, 16 313 ausentes del boletín y 255 boletines no
  disponibles. La cuadrícula contiene 2 515 filas por emisora; esto no equivale
  a 2 515 precios disponibles.
- En el CSV local, por ejemplo, WALMEX tiene 2 495 precios no vacíos, GFNORTE
  2 491, BIMBO 536 y LIVEPOL 265. Los recuentos son de valores no vacíos, no
  validaciones independientes del boletín. El MD5 del archivo local coincide con
  el ETag simple del objeto S3 observado; no sustituye una auditoría de fuente.
- `reconstruccion_ppp_15_emisoras.py` describe una reconstrucción a partir de
  boletines HTML y una rejilla heredada; documenta huecos y trazabilidad. Eso
  acredita la metodología declarada, no licencias ni exhaustividad de precios.
- La [página de bases de datos de BMV](https://www.bmv.com.mx/en/information-products/databases)
  ofrece información histórica y de cierre y pide solicitar cotización a
  [marketdatasales@grupobmv.com.mx](mailto:marketdatasales@grupobmv.com.mx).
  Debe confirmarse con BMV si ofrece **PPP histórico**, series exactas, periodo,
  ajustes corporativos, formato, costo y cobertura; la página no lo especifica.
- Los [términos de uso de BMV](https://www.bmv.com.mx/en/terms-of-use) indican
  restricciones de reproducción y extracción automatizada y mencionan
  autorización previa escrita. Que un boletín sea accesible públicamente no
  demuestra autorización de extracción, almacenamiento, análisis, despliegue o
  redistribución comercial o académica. No consta autorización específica en la
  evidencia revisada. Consultar la licencia aplicable y solicitar confirmación
  escrita; esta revisión no es un dictamen jurídico.
- La Lambda activa también contiene contingencia Yahoo. Los
  [términos generales de API de Yahoo](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html)
  incluyen restricciones, pero **no se ha comprobado** que sean los términos
  aplicables al endpoint concreto ni que exista licencia para Prisma. No asumir
  autorización o equivalencia del cierre de Yahoo con PPP de BMV.

**Decisión pendiente:** antes de ampliar la extracción o distribución, revisar el
uso actual y obtener autorización aplicable o contratar un proveedor que
autorice ingestión, conservación, análisis y presentación a usuarios. No se
demostró disponibilidad de historia autorizada para los componentes adicionales.

### Lectura efectiva de Athena antes de la corrección

| Consulta | ID | Resultado |
|---|---|---|
| Silver, muestra del 2026-11-17 | `6ee51c54-98cd-4867-af66-9e4964929a81` | `SUCCEEDED`; tres filas con emisora, serie, estado y PPP plausibles. No es una validación integral. |
| Gold, muestra de señales | `c09008dc-9bec-46fd-8ec1-ae5bb0b5354b` | `SUCCEEDED`, pero lectura **incorrecta**: en la primera fila `fecha_objetivo_h5` devuelve `IN_SAMPLE_DISENO`, `emisora` devuelve `OFICIAL_2026`, `serie` devuelve `AMX` y `modelo_g2` devuelve `Telecomunicaciones`. |
| Histórico, conteo y rango | `5d6b1c12-051b-44f5-805a-cc413692f75b` | `SUCCEEDED`; 37 725 filas, 15 emisoras, rango arriba indicado. |
| Histórico, conteos por estado | `9781e200-d6f2-473c-afcd-16a69bee1171` | `SUCCEEDED`; resultados por estado y valores presentes coinciden con el conteo del CSV local. |

Al cotejar la primera fila del CSV Gold directamente con la consulta, sus
valores correctos incluyen `muestra_evaluacion=IN_SAMPLE_DISENO`,
`fecha_objetivo_h5=2026-11-05`, `calendario_objetivo=OFICIAL_2026`,
`emisora=AMX`, `serie=B` y
`modelo_g2=G2_V1_POOLED_REL3_CALIBRADO`. La tabla anterior omitía la columna
`muestra_evaluacion` y OpenCSVSerde lee por posición. Véase la corrección y sus
límites en la sección siguiente.
La consulta histórica escaneó aproximadamente 10 MB; las otras tres también
pueden generar cargos mínimos y sus resultados permanecen en S3.

## Corrección del contrato Gold en Glue

La tabla `default.bmv_gold_senales_g2` tenía **33 columnas**, mientras el único
CSV de datos del prefijo en el momento de la comprobación tenía **42**. Al faltar
`muestra_evaluacion` en la cuarta posición, los campos posteriores se leían con
desplazamiento. Los últimos campos tampoco se exponían. Adicionalmente,
`target_y_observado` se almacena como `0.0` o `1.0`, por lo que su tipo se
definió como `DOUBLE`; los aciertos textuales permanecen `STRING`.

1. Se compararon los 42 encabezados del CSV de S3 con el contrato en
   `infra/athena/11_gold_g2_lambda_activa_referencia.sql`, en el mismo orden.
2. Se creó en Glue `default.bmv_gold_senales_g2_verificacion_contrato` con la
   misma ubicación y propiedades y se validó la lectura de prueba.
3. Athena rechazó `ALTER TABLE ... REPLACE COLUMNS` para OpenCSVSerde
   (`3e2431ee-238d-47e9-abd2-2fab098e41ac`), sin aplicar ese cambio. Se
   actualizó el catálogo con `glue update-table`, preservando ubicación,
   propiedades y serde. La tabla activa pasó de versión Glue `0` a `1`.
4. La versión anterior `0` sigue accesible mediante `glue get-table-version`;
   además se guardó una copia temporal local de la definición previa. No se
   modificó el CSV Gold: su ETag antes y después fue
   `7adc86e22229548f0419236953637e6a`.
5. La consulta posterior `ccd33e72-ee75-4568-9029-35ba9ac538ad` devolvió 344
   filas, 344 IDs únicos, 344 probabilidades, 120 objetivos no nulos, cero
   fechas objetivo inválidas y cero probabilidades nulas o fuera de rango.
   Los conteos de filas, IDs, probabilidades y objetivos coinciden con el CSV
   descargado. La muestra `60b5a601-ce98-42cc-9fef-657b440b7e26` muestra
   fechas, emisora, serie y modelo en sus columnas correctas.

La tabla auxiliar de verificación permanece en Glue; comparte el mismo CSV,
no es una copia de datos. Las consultas generan resultados en S3 y pueden
generar cargos. `tests/test_contrato_gold_lambda_activa.py` comprueba orden de
columnas contra el CSV local y tipos críticos; no sustituye verificaciones AWS.

**Riesgo residual:** el DDL `infra/athena/03_bmv_gold_senales_g2.sql` y
`infra/deploy_aws.sh` corresponden a otra implementación y otra base
(`prisma_bmv`), no a este contrato de la Lambda activa. No ejecutar ese
despliegue ni mezclar CSV de ambos formatos en el mismo prefijo sin diseñar
una migración. La plantilla SQL 11 crea la tabla activa solo si no existe;
no actualiza tablas existentes. El productor activo puede cambiar su encabezado
al combinar datos: se recomienda añadir validación automática del esquema del
CSV antes de escribir y antes de consultar, en una modificación futura separada.
Los controles realizados no demuestran validez estadística de los modelos ni
resuelven el origen de datos de la API desplegada.

## Protección del despliegue y DDL heredados

- `infra/deploy_aws.sh` está bloqueado antes de cualquier operación AWS: su
  implementación anterior sustituiría Lambda, configuración, políticas,
  programación y datos con una arquitectura distinta.
- `scripts/crear_tablas_athena.py` permite únicamente imprimir DDL históricos;
  no los ejecuta. `scripts/bootstrap_lakehouse.py` queda bloqueado para evitar
  sobrescrituras. Estas restricciones también se aplican a ambientes nuevos:
  deben diseñarse y aprobarse procedimientos específicos antes de habilitarlos.
- `infra/athena/11_gold_g2_lambda_activa_referencia.sql` documenta el contrato
  real para crear una tabla nueva en `default`. `IF NOT EXISTS` no corrige
  tablas existentes. Los DDL `0*.sql` siguen representando la otra Lambda y no
  deben apuntar a los datos activos.
- `scripts/verificar_contrato_aws.py` comprueba mediante lecturas AWS el esquema
  Glue, la ubicación y los encabezados de los CSV del prefijo Gold. Su ejecución
  comprobó 42 columnas y un CSV compatible; no cambió AWS ni ejecutó Athena.
- La consulta Silver de `RepositorioAthena` filtra por `anio`/`mes`, ausentes
  en la tabla `default.bmv_silver_ppp` observada. Es preciso adaptar y probar
  ese consumidor o crear un contrato de lectura compatible antes de afirmar que
  Streamlit funciona con la base activa.
- Cuatro pruebas locales de contratos y bloqueos pasaron. No se pudo ejecutar
  la prueba del script Bash en Windows porque este entorno no tiene `/bin/bash`;
  la guarda está antes de la primera llamada AWS.

Todavía no existe un nuevo procedimiento automatizado para desplegar en
producción. No se desplegó código ni se reescribieron datos durante esta
protección.

## Laboratorio aislado y lectura Silver

- Se creó `prisma-bmv-aislado-prueba-2026` con bucket y base Glue propios, una
  tabla Gold sintética y una Lambda de salud, sin recolector ni Scheduler.
- `scripts/entorno_aislado.py` genera la plantilla y migra versiones sintéticas
  a S3; la reversión restaura una versión de Glue dentro del mismo bucket.
  La promoción a producción y el borrado automático están fuera de su alcance.
- En AWS se migraron dos CSV sintéticos. Athena leyó `SINTETICO_2`/0.75 en
  `v2` y, tras reversión a Glue versión 1, `SINTETICO_1`/0.25 en `v1`. Los
  recursos y resultados permanecen en el laboratorio. Véanse condiciones,
  comandos y costos en `docs/ARQUITECTURA_AWS.md`.
- `RepositorioAthena` detecta mediante Glue las particiones Silver. En la base
  activa `default` detectó ninguna y leyó 195 filas con el filtro de fecha. Las
  pruebas locales cubren ambos esquemas y errores de permisos; esto no valida
  por completo Streamlit ni el resto de sus fuentes. Se requiere `glue:GetTable`.
