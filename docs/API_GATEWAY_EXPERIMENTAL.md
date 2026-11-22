# API Gateway y Cognito: experimento aislado

**Estado: API parcial desplegada en laboratorio; no conectada al frontend.**
Rama `experimento/api-gateway-cognito`, trabajo en worktree
independiente. Los cambios previos sin commit se copiaron para tener contexto;
los archivos ignorados, incluidos `.env`, no se copiaron.

## Arquitectura y alcance

```text
Navegador -> API Gateway HTTP (HTTPS)
                    |-> GET /health -> Lambda experimental
                     |-> GET /api/me -> autorizador JWT Cognito -> Lambda -> DynamoDB
                    |-> GET /api/mercado/{fechas,resumen} -> Lambda -> S3
                    |-> GET /api/terminal/serie, /api/serie/walmex -> JWT -> Lambda -> DynamoDB y S3
```

La plantilla `infra/api_gateway_aislada/template.yaml` define estas rutas.
El autorizador de API Gateway verifica firma, emisor, audiencia y
tiempos; la Lambda exige `token_use=access` y consulta el perfil por `sub`.
Sin perfil o con rol/plan desconocido se deniega el acceso; una falla de
DynamoDB devuelve 503 sin exponer detalles. `GET /health` solo comprueba que
la función responde, no que Cognito o DynamoDB funcionen.

**No reemplaza la API FastAPI**: faltan parte de mercado, estadística, señales,
admin, macro, completar el frontend Cognito y demás funciones. No conecta las 35 candidatas ni
modifica producción. La verificación offline de JWT de Gateway no garantiza
detectar revocación anticipada; requiere política adicional de sesión.

El handler confía en los claims proporcionados por API Gateway; no debe
concederse invocación directa a otros principales que puedan falsificar un
evento. La plantilla autoriza a API Gateway únicamente sobre la función y
restringe el origen al API creado, pero no elimina otros permisos IAM. El rol
de ejecución debe tener lectura de la tabla y logs; `LabRole` es amplio y no
se ha validado mínimo privilegio. CORS requiere un origen HTTPS explícito.
Las cuotas de concurrencia y throttling **no** son límites de gasto fiables.

## Pruebas realizadas

- CloudFormation `validate-template`: aceptada la estructura; no crea nada ni
  valida permisos de creación, políticas efectivas o ruta real.
- Pruebas unitarias con DynamoDB simulado: salud, ruta desconocida, rechazo de
  ID token, perfil ausente, perfil inválido, lectura consistente por `sub`,
  separación de planes y error de lectura. No prueban firma JWT ni IAM real.
- `iam simulate-principal-policy` para `LabRole` y `dynamodb:GetItem` sobre la
  tabla actual devolvió `allowed`; la simulación no garantiza autorización real
  con todas las políticas y circunstancias del despliegue.
- Empaquetado: `python scripts/empaquetar_api_gateway_aislada.py --salida <zip-nuevo>`.
  El ZIP contiene únicamente `handler.py`; no incluye secretos ni datos.
- Se desplegó el stack `prisma-bmv-api-aislada-2026` en `us-east-1`, luego de
  revisar un changeset compuesto únicamente por recursos nuevos. URL:
  `https://j42hw8l6rl.execute-api.us-east-1.amazonaws.com`.
- Las pruebas HTTPS reales devolvieron `200` en `/health`, `401` en `/api/me`
  sin token y con token falso, y `204` en OPTIONS con CORS para
  `https://demo.d315dh37vi024o.amplifyapp.com`. Ese origen no indica que la
  rama de Amplify esté publicada.
- Se creó el usuario sintético `prisma-prueba-2026@example.invalid` en el
  pool aislado y un perfil `user`/`explorer` en DynamoDB. Mediante SRP se
  obtuvo un access token real: `/api/me` devolvió `200`, plan `explorer` y
  solo `WALMEX`; un ID token real devolvió `401`. La contraseña se generó
  aleatoriamente en memoria y no se almacenó; el usuario requiere un nuevo
  procedimiento de contraseña para volver a utilizarse. Los recursos de
  prueba siguen activos y pueden generar costos.
- React tiene un adaptador **opcional** para Cognito mediante
  `VITE_AUTH_PROVIDER=cognito`, con login SRP y renovación de sesión, y
  `VITE_REQUIRE_REAL_API=true` evita los mocks de cinco métodos del cliente de
  API. El build local pasó. Hay pantallas locales sin prueba real para
  MFA, recuperación y primer cambio de contraseña; faltan la inscripción TOTP,
  el registro y el cambio de plan.
  El frontend completo no se ha probado con el usuario y no se ha publicado.
  Otros componentes todavía usan mocks por su cuenta: esa variable no prueba
  que toda la interfaz esté libre de datos simulados.
- El artefacto inmutable se guardó en el bucket del laboratorio sintético bajo
  `artifacts/api-gateway/32c2ec2e5172ac92bffff32c8b11b133668252dc7b61d6ab1fe0f6de0907f03c.zip`.

## Costos y trabajo pendiente

AWS [cobra por uso de API Gateway](https://aws.amazon.com/api-gateway/pricing/),
además de posibles costos de Lambda, DynamoDB, logs y transferencia. No se
confirmó que el laboratorio tenga capa gratuita aplicable. El presupuesto
consultado fue USD 0.85 de USD 1.00 con pronóstico USD 0.981; no es un límite
automático. El usuario autorizó uso con costo. Cost Explorer devolvió para el
  1 al 19 de noviembre USD 0.8496376676 `UnblendedCost`, **estimado**; puede
  no incluir todavía todos los cargos del despliegue y no representa el historial
  total de la cuenta ni una estimación del costo incremental de esta API.
  Para enero–noviembre de 2026 el total de las cifras mensuales consultadas fue
  aproximadamente USD 0.9169853 en toda la cuenta (octubre 0.0673476301,
  noviembre 0.8496376676; meses previos aproximadamente cero). Incluye otros
  proyectos y noviembre es estimado. `UnblendedCost` no es necesariamente
  dinero pagado ni saldo de crédito restante; no permite atribuir el costo
  de Prisma ni garantiza que se hayan reflejado todos los cargos.

Faltan revisar el ciclo completo de credenciales y revocación, probar perfil
inexistente con token real y validar el origen de la rama Amplify cuando
exista. Faltan las demás rutas y completar frontend desde Supabase; solo parte
de mercado y serie se han migrado; estadística, señales y administración no. Es necesario retirar
o etiquetar explícitamente los mocks adicionales y probar el frontend con el
backend antes de publicarlo. Ninguna prueba debe exponer datos reales o secretos.

Fuentes: [autorizadores JWT de API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html)
y [precios de API Gateway](https://aws.amazon.com/api-gateway/pricing/).

## Avance local posterior: acceso y datos sin respaldo simulado

- Se añadieron en React el desafío de primer cambio de contraseña, la
  respuesta a desafíos MFA SMS/TOTP y el inicio y confirmación de recuperación
  por correo. Son cambios locales: **no se han probado en navegador ni con
  desafíos reales de Cognito**. El pool tiene MFA TOTP opcional y recuperación
  mediante correo verificado; la interfaz no permite inscribir un autenticador
  TOTP ni resolver el desafío de configuración inicial de MFA. La cuenta
  sintética `.invalid` tampoco puede recibir correos de recuperación.
- Se oculta el registro público en modo Cognito, pues el pool solo permite
  creación administrativa. El componente de auditoría heredado se deshabilita
  cuando `VITE_REQUIRE_REAL_API=true` porque mezcla métricas reales y cifras de
  ejemplo; en modo demostración se muestra una advertencia. Se eliminaron los
  bins de calibración simulados de la sección de calidad y las fechas ficticias
  del proveedor Python cuando no hay datos. La barrera del cliente también
  notifica fallos de red en modo real. **Esto no constituye una auditoría
  completa de todos los valores y pantallas del frontend**.
- El build React pasó. Se ejecutaron 9 pruebas Python seleccionadas, incluidas
  tres para fechas sin datos, y 11 pruebas JavaScript existentes. No prueban
  los desafíos de identidad ni el sistema de extremo a extremo.
- Inspección de `silver/serie_unificada_reciente.csv` en el bucket histórico:
  última modificación el 18-11-2026; corte más reciente 17-11-2026 con 12
  filas; en el archivo hay estados verificados, ausentes y de contingencia.
  Esto no demuestra captura completa o actualizada ni permite presentar esa
  contingencia como PPP BMV. El bucket aislado ampliado tiene otra captura
  experimental y no debe mezclarse automáticamente con este contrato.
- En un avance posterior se actualizó la API aislada, no Amplify. Se añadieron
  fechas, resumen de mercado y dos rutas de serie, las últimas protegidas por
  Cognito y filtradas por plan. La lectura es de la instantánea indicada; PPP
  de contingencia y faltantes se muestran como `null` y no se inventan
  variaciones. Se conserva la indicación de cobertura parcial y última
  modificación del objeto; la lista de filas no es un catálogo completo.
- Prueba HTTPS con usuario sintético y token real: serie WALMEX 200 con 53
  puntos hasta 17-11-2026; AMX fuera del plan 403; sin token y con ID token
  401. La prueba concurrente previa recibió un 503 en lugar del 403 esperado;
  la prueba secuencial pasó. Investigar y probar carga antes de uso público.
  Para la prueba se renovó la contraseña aleatoria del usuario sintético; no
  se almacenó. `scripts/probar_serie_aws_aislada.py` limita explícitamente esa
  operación a dicho usuario.
- Las rutas restantes de mercado, estadística, señales y administración siguen
  pendientes de migración, autorización y pruebas. Amplify sigue sin ramas. No
  se ha publicado ni probado el frontend con datos reales de extremo a extremo.
  Último artefacto desplegado:
  `artifacts/api-gateway/e644c06f9ea66cbbde9ee76129677deecdb9542afa709d50df8659dfac590325.zip`.
