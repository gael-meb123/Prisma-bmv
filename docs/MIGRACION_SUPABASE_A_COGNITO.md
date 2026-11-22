# Migración propuesta: Supabase a AWS

**Estado: infraestructura aislada desplegada; migración no terminada.** La
aplicación sigue usando Supabase; no se han leído ni modificado sus usuarios.
El stack `prisma-bmv-auth-aislado-2026` se creó con la plantilla experimental
`infra/auth_aws_aislado/template.yaml`. No se han creado usuarios.

## Qué sustituye cada servicio

| Función actual | Alternativa propuesta | Estado |
|---|---|---|
| Login, sesiones y recuperación Supabase Auth | Cognito User Pool | plantilla experimental |
| Perfil, rol y plan `public.profiles` | DynamoDB por `sub` de Cognito | plantilla vacía |
| Administración con `service_role` | API propia con IAM de servidor | pendiente |
| Cliente Supabase del navegador | SDK Cognito/Amplify Auth | pendiente |
| Verificación actual y permisos del backend | JWT Cognito verificado + perfil DynamoDB | pendiente |
| `cambiar_plan_demo` | operación de backend explícita y controlada | pendiente |

No se deben guardar planes o roles editables por el navegador en atributos
que el cliente pueda modificar; la autorización debe consultarse en el
backend. La tabla no tiene política de acceso de navegador en la plantilla.

## Lo preparado

La plantilla define un User Pool aislado, app client sin secreto para
navegador y una tabla de perfiles bajo demanda. Bloquea el registro público
en la configuración experimental y reserva la creación de usuarios al
administrador; permite MFA por aplicación, pero no la exige. La única
propiedad de usuario editable configurada para el cliente es `name`; los
roles y planes no se alojan en atributos del cliente. Usa retención en
CloudFormation y protección de borrado para el pool.

La plantilla pasó `aws cloudformation validate-template` y una prueba local
estructural. Un despliegue real finalizó `CREATE_COMPLETE`:

- User Pool `us-east-1_mKU76i6gl`; 0 usuarios estimados, alta administrativa,
  tier Lite, MFA opcional y protección de borrado activa.
- Cliente de navegador `3k7iv4ebko2us1bbk78v07cg09`; lectura `email`,
  `email_verified`, `name`, escritura `name`; flujos SRP y renovación.
- Tabla `prisma-bmv-auth-aislado-2026-Perfiles-1JSFRU50XIG7B`, activa,
  cifrada, facturación bajo demanda y 0 elementos estimados.

Los IDs del pool y cliente no son secretos. La prueba no valida autenticación,
recuperación, permisos de backend, cuotas ni seguridad extremo a extremo.
`Retain` y la protección implican que eliminar el stack no eliminaría
automáticamente los datos; cualquier futura limpieza requiere un procedimiento
deliberado y autorización.

## Prueba de disponibilidad y costos

Antes del despliegue, `ListUserPools` y `ListTables` respondieron sin elementos.
Después se comprobó la creación mediante CloudFormation y la lectura de la
configuración de ambos recursos. No se han probado operaciones de usuarios.
El presupuesto consultado antes del despliegue era USD 0.85 de USD 1.00,
pronóstico USD 0.981; puede cambiar y no es un tope de gasto.

[Precios oficiales de Cognito](https://aws.amazon.com/cognito/pricing/)
describen una capa gratuita para usuarios activos directos en Lite/Essentials,
con condiciones y posibles cargos por mensajes y otros servicios. DynamoDB,
CloudFormation, correo y otros componentes pueden consumir recursos; no se
ha verificado elegibilidad de este laboratorio ni se garantiza costo cero.
No se enviaron correos ni se crearon usuarios o registros de perfil.

## Implementación pendiente y criterios de seguridad

1. Adaptar el cliente para SRP, sesión, renovación y desafíos Cognito,
   incluyendo alta administrativa, primer cambio de contraseña, recuperación
   y MFA. El cliente actual depende de Supabase y no entiende estos flujos.
2. Verificar en FastAPI la firma JWT con JWKS del pool configurado, algoritmo
   RS256 permitido, `iss`, `exp`, `token_use=access`, `client_id`, y scopes
   pertinentes. Rechazar tokens inválidos y errores de configuración sin
   fallback a permisos. Según la
   [guía de AWS](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html),
   la comprobación local de firma y expiración no detecta por sí sola
   revocaciones anticipadas; definir cómo atenderlas.
3. Después de autenticar, leer por `sub` el perfil desde DynamoDB con un rol
   de backend de mínimo privilegio. Sin perfil, denegar acceso. Probar
   cambios, eliminación, roles válidos y concurrencia; ningún cliente debe
   poder asignarse `admin` ni elevar su plan.
4. Implementar alta, listado y edición administrativas, manejo de fallos
   parciales entre Cognito y DynamoDB, auditoría y reversión. Rediseñar el
   cambio de plan de demostración sin conceder planes pagados por accidente.
5. Resolver migración de usuarios: conservar Supabase hasta validar; obtener
   autorización y método para migrar perfiles minimizando datos, asociar cada
   identidad antigua con el nuevo `sub`, y utilizar restablecimiento de
   contraseña o estrategia compatible documentada. **No se presupone acceso a
   contraseñas existentes ni se copian secretos.**
6. Probar identidades válidas e inválidas, claves rotadas, tokens de otro
   cliente/pool, expirados o revocados, falta de perfil, escalamiento de
   privilegios, sesión, errores y reversión. Completar backend HTTPS y
   configuración de CORS antes de publicación.
7. Solo después de comprobar costos, permisos y un laboratorio aislado con
   usuarios ficticios, planear el cambio de proveedor y su reversión. El
   frontend sigue apuntando a Supabase hasta entonces.

La identidad no sustituye los datos de mercado ni resuelve el backend público,
el presupuesto, los PPP faltantes, composición IPC o elegibilidad de modelos.
