# Avance de pendientes de expansión IPC

## 1. Reejecución y hash: implementación local

`infra/lambda/captura_ampliada_aislada/handler.py` conserva en
`experimental/v1/cuarentena/<fecha>/<sha>.html` una descarga válida para la
fecha que tenga un hash distinto al Silver o bloqueo previo. Genera un JSON
separado con diferencias de campos entre filas extraídas y el Silver previo
cuando existe exactamente uno. Nunca añade un segundo Silver automáticamente.

`FILAS_IGUALES` solo significa igualdad de las filas extraídas, exceptuando el
hash; **no** demuestra que el HTML completo sea igual ni que solo haya cambiado
un script. `FILAS_DISTINTAS` indica los campos de las parejas afectadas.
`NO_DISPONIBLE` indica que no se pudo hacer la comparación prevista. En todos
los casos el conflicto bloquea y requiere revisión humana. Archivos que no
pasan la extracción inicial no llegan a esta cuarentena; errores de escritura o
lectura tampoco generan necesariamente informe completo. No existe un flujo
de aprobación ni promoción automática.

Estas modificaciones son **locales**, no se desplegaron en AWS. El laboratorio
desplegado sigue con el comportamiento anterior documentado en
`docs/ARQUITECTURA_AWS.md`. Los tests usan S3 simulado, no AWS. La concurrencia
reservada protege solo la Lambda aislada y no impide escrituras externas. Un
Silver escrito antes de un fallo al guardar el manifiesto podría ser visible en
Athena porque la tabla lee directamente el prefijo; el manifiesto no es un
filtro de publicación transaccional. Se necesita un mecanismo de publicación
atómica o lectura por manifiesto antes de cualquier uso productivo.

## 2. Calidad y errores

Pruebas locales cubren repetición idéntica, modificación de datos, cambio sin
cambio en filas, bloqueo incompleto, fallo de red, interrupción y recuperación
con la misma firma, vacíos, duplicados contradictorios y fecha inválida.
Faltan pruebas AWS de estos cambios, concurrencia externa, errores de permisos,
fallo durante cuarentena/manifiesto, reintentos, observabilidad y mecanismo
seguro de recuperación y revisión de cuarentenas.

## 3. Adaptador de Capitales

`prisma/data/capitales_bmv_experimental.py` interpreta texto suministrado por el
llamador, sin llamadas HTTP ni escrituras. No ejecuta JavaScript. Separa PPP
positivo, último precio, fecha y hora de fuente y hora de observación con zona.
Cero, ausente, no numérico y no finito pasan a PPP no disponible; positivos
siguen **no validados**. Rechaza pares duplicados y respuestas inesperadas.
No infiere fecha de sesión si la fuente no la aporta, ni composición IPC.

Tests sintéticos únicamente; faltan cotejo de una respuesta real con PPP
positivo del mismo corte que el boletín, validación de frescura y definición
de fecha, permisos aplicables, variaciones de formato y política de captura.
No hay integración con Silver, API, frontend ni señales.

## 4. API y AWS

Inspección local: `core/data_provider.py` usa CSV y JSON relativos a la raíz
del repositorio. `core/terminal_api.py` usa `RepositorioLocal`, caché de 60
segundos y también lee CSV históricos locales. `api.py` puede leer macro de
S3 cuando se configura `MACRO_S3_BUCKET`; esto no demuestra conexión de los
endpoints de mercado con el lake. Estas observaciones son del código local,
no identifican el paquete ni fuentes efectivos de una API desplegada.

El 19-11-2026 a las 10:34 UTC−6 se revisó la cuenta AWS `886457183564` en
modo solo lectura, principalmente en `us-east-1`, después de renovar las
credenciales:

- ECS no lista clústeres; API Gateway REST y v2 no listan APIs; Amplify no
  lista aplicaciones en esa región. La única EC2 encontrada está etiquetada
  para `practica1-ecommerce`, no se investigó como si fuera Prisma.
- App Runner y CloudFront devolvieron `AccessDenied`, de modo que no pueden
  descartarse como alojamiento. CloudFront es global; los otros inventarios
  citados son regionales. Tampoco se descarta alojamiento externo a AWS u
  otras regiones. No se identificó la API desplegada ni su origen efectivo.
- El frontend local toma `VITE_API_URL` durante su compilación; si no existe
  usa `http://localhost:8000/api`. Esto no demuestra qué URL se compiló en
  una aplicación publicada.
- La Lambda de ingesta `recolector-diario-bmv` sigue existente, con último
  cambio reportado el 08-11-2026 y Scheduler habilitado a las 16:45 de lunes a
  viernes, zona Ciudad de México, sin reintentos. No es por sí misma evidencia
  de una API. Se revisaron solo nombres de variables, sin leer sus valores.
- El código de ingesta previamente identificado busca registro de modelos en
  archivos locales, luego dos claves S3, y después una configuración interna;
  el origen efectivo por ejecución no se confirmó. Consultar los logs
  disponibles tampoco bastaría si no identifican explícitamente la ruta usada.

Para continuar: identificar URL y región/proveedor de alojamiento de la API o
conseguir permisos de consulta de App Runner y CloudFront; después verificar
versión, artefacto, archivos montados, configuración sin exponer secretos y
sincronización efectiva. No se modificó AWS ni se invocaron funciones.

## 5. Diseño de catálogo versionado

La implementación existente solo admite una instantánea provisional por corte;
no se le añadió vigencia inferida. Diseño propuesto para una versión futura:

- Cada publicación inmutable: `version`, fecha de publicación y consulta,
  fuente, identificador o hash de evidencia, tipo y estado de confirmación.
- Cada instrumento: identificador estable sustentado por fuente, emisora,
  serie, nombre y sector cuando estén respaldados; el par no se deriva de un
  alias. Cambios de serie usan una nueva clave y relación explícita sustentada.
- Pertenencia: fecha efectiva inicial y final **solo si la evidencia las
  respalda**; si existe solo un corte, registrar únicamente ese corte.
  Intervalos con extremos definidos como inclusivo inicial y exclusivo final.
- Bajas y correcciones se agregan en nuevas versiones fechadas, nunca reescriben
  la instantánea anterior ni alteran señales históricas. Una corrección debe
  referenciar su versión anterior y evidencia.
- Alias independientes por fuente, con estado y evidencia, sin borrar signos;
  validar unicidad y solapamientos por fuente y vigencia. Mapeos no confirmados
  no conceden pertenencia, permisos ni habilitación de modelos.
- Pruebas futuras: duplicados, límites de vigencia, solapamientos, alias
  ambiguos, bajas, cambio de serie, fuente inexistente y cortes sin evidencia.

Esto es un **diseño**, no un esquema ejecutable ni un catálogo oficial nuevo.
Faltan fuente fechada oficial, decisiones de identificadores y responsable de
actualización, implementación y pruebas antes de integrarlo al sistema.

## Qué falta para completar la ampliación

1. Comprobar una fuente gratuita autorizada con PPP final positivo y cobertura,
   contrastada por la misma sesión; identificar fuente e historial adecuados.
2. Obtener composición oficial fechada y evidencia de alias, con nuevas
   versiones del catálogo; no extrapolar NAFTRAC a otras fechas.
3. Localizar la API desplegada, revisar permisos de lectura y verificar
   su procedencia y configuración efectivas.
4. Completar las pruebas de laboratorio, la publicación transaccional, la
   revisión manual de divergencias, mínimo privilegio, monitoreo y reversión.
5. Diseñar e implementar integración de Mercado y estadística, con faltantes y
   procedencia explícitos; probar reconciliación y aprobar antes de desplegar.
6. Evaluar por separado entrenamiento, escaladores y métricas de modelos para
   nuevas series; no habilitar señales o consenso sin evidencia y aprobación.
