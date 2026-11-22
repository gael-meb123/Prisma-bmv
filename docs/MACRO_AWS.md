# Cinta macroeconómica con AWS

Esta pila distribuye **publicaciones oficiales**, no cotizaciones intradía.
EventBridge ejecuta Lambda cada 15 minutos; Lambda consulta Banxico, guarda una
instantánea privada en S3 y notifica a los clientes mediante API Gateway WebSocket.
La API de Prisma lee S3 y la cinta vuelve a consultar la API tras la notificación.
Cuando el socket no está disponible, el navegador consulta cada cinco minutos.
El proceso no modifica modelos ni señales.

## Antes de desplegar

1. Tener un bucket S3 existente en la misma región, privado y con cifrado.
2. Instalar AWS CLI y AWS SAM CLI, configurar credenciales y región para una cuenta
   autorizada, y comprobar acceso con `aws sts get-caller-identity`.
3. En Secrets Manager crear un secreto de **texto sin formato** cuyo contenido
   completo sea el token SIE de Banxico. Copiar únicamente su ARN. No incluir el
   token en Git, comandos, parámetros de CloudFormation ni capturas de pantalla.
4. Confirmar que la cuenta permite crear Lambda, EventBridge, API Gateway WebSocket,
   DynamoDB, IAM y logs, y revisar costos y límites. Con KMS administrado por el
   cliente se requieren permisos adicionales de descifrado para los roles.

## Despliegue

En PowerShell, desde la raíz del repositorio:

```powershell
sam validate --template-file infra/macro_aws/template.yaml
sam build --template-file infra/macro_aws/template.yaml
sam deploy --guided
```

Durante `deploy --guided`, indicar la región y el nombre de la pila, `MacroBucket`
(nombre del bucket, sin `s3://`) y `BanxicoSecretArn` (ARN, no el token).
Autorizar la creación de roles IAM solo después de revisar la plantilla. La carpeta
de código desplegada es `infra/macro_aws/src/`; no se empaquetan `.env` ni el resto
del proyecto. Conservar las salidas `WebSocketUrl`, `PublicadorNombre` y `ObjetoS3`.

En la consola Lambda, ejecutar **Test** en la función de `PublicadorNombre` con
`{}` para generar la primera instantánea, sin esperar a la programación. Confirmar
en CloudWatch que no haya errores y que `series_disponibles` sea el esperado. El
objeto de salida se guarda en `macro/indicadores.json`. Si Banxico falla, se
mantiene el último valor previo con `ultima_consulta_fallida`; sin dato previo se
marca como no disponible. No compartir logs que incluyan datos sensibles.

## Conectar la aplicación

En el `.env` privado del backend:

```text
MACRO_S3_BUCKET=nombre-del-bucket
MACRO_S3_KEY=macro/indicadores.json
```

El proceso de la API necesita credenciales AWS válidas y permiso `s3:GetObject`
exclusivamente para ese objeto; en AWS usar un rol IAM, no claves en el código.
Un error al leer S3 produce HTTP 503, no una sustitución silenciosa por datos
locales. Si la última consulta del publicador tiene más de 35 minutos, la API
marca el valor como no actualizado.

En `frontend/.env`:

```text
VITE_MACRO_WS_URL=wss://ID.execute-api.REGION.amazonaws.com/prod
```

Usar el valor de `WebSocketUrl`. Reiniciar la API y el servidor Vite; para un
frontend compilado, volver a generar y desplegar la compilación. Comprobar el
endpoint `/api/macro/indicadores`, abrir dos navegadores y volver a ejecutar el
test de la Lambda para verificar que ambos reciben la notificación. El frontend
consulta la API para leer los valores; el mensaje WebSocket no contiene datos.

Sin estas dos configuraciones, el sistema sigue funcionando en modo local con
el token de Banxico del backend y no usa la pila AWS.

## Operación y seguridad

- La API WebSocket de esta plantilla es **pública y no autenticada** porque solo
  transporta avisos, pero puede generar costos y recibir conexiones abusivas.
  Antes de producción, añadir autenticación o controles de acceso apropiados,
  cuotas/limitación, alarmas de costos y revisar los límites del entorno.
- DynamoDB elimina conexiones al desconectarse o cuando se detecta una conexión
  cerrada; TTL ayuda a limpiar conexiones abandonadas. El cliente reconecta
  automáticamente cuando el socket expira o se interrumpe.
- Configurar alarmas para errores o falta de ejecución de Lambda y supervisar
  el estado de las series; el resultado de la función incluye el número de
  series que respondieron.
- La caché en S3 es una instantánea, no historial. No habilitarla como evidencia
  prospectiva para los modelos sin diseñar almacenamiento histórico y validación.
- La plantilla debe validarse y probarse en una cuenta de desarrollo. SAM/CloudFormation
  pueden generar cargos y requerir permisos no disponibles en cuentas de laboratorio.
