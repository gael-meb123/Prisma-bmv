# Estado del despliegue público educativo

**Revisión:** 19-11-2026, región `us-east-1`. **Estado: incompleto; no hay
frontend publicado ni API pública verificada.**

## Validaciones y recursos

- Amplify permitió crear la aplicación vacía
  `prisma-bmv-frontend-educativo`, ID `d315dh37vi024o`; no tiene ramas ni
  despliegues. El dominio por defecto asignado es
  `d315dh37vi024o.amplifyapp.com`; no debe tratarse como URL funcional.
  El recurso permanece en la cuenta; consultar costos y conservación antes de
  su eliminación. No se creó CloudFront directamente.
- El frontend React compiló localmente con `npm run build`. El `dist` resultante
  no se publicó: su configuración de API apunta a `http://localhost`, que en
  el navegador del visitante apunta a su propio equipo, no al backend.
  Además, el cliente puede mostrar mocks ante fallos de conexión; se requiere
  asegurar que un despliegue no confunda esos datos con información real.
- `RunInstances --dry-run` para `t3.micro` devolvió `DryRunOperation`; esa
  operación parece autorizada en ese momento, pero **no** verifica capacidad,
  cuotas, arranque, red, perfil IAM, instalación, HTTPS ni costos. No se
  lanzó ninguna EC2 ni se modificó la instancia de otro proyecto.
- AWS Budgets mostró presupuesto mensual **USD 1.00**, gasto real **USD 0.85**
  y pronóstico **USD 0.981** al momento de la consulta. Son cifras de la
  herramienta, no una garantía de gasto final ni un límite automático;
  desconocemos el crédito disponible. No se puede asegurar que alojar una EC2
  sea gratis o que el presupuesto detenga recursos.

La [documentación oficial de precios de Amplify](https://aws.amazon.com/amplify/pricing/)
describe cargos por almacenamiento y transferencia y posibles condiciones de
capa gratuita. La [documentación de despliegue manual](https://docs.aws.amazon.com/amplify/latest/userguide/manual-deploys.html)
confirma que una app estática puede publicarse sin repositorio Git.
No se ha confirmado la elegibilidad de esta cuenta a una cuota gratuita.

## Bloqueos técnicos y de seguridad

Se desplegó infraestructura aislada Cognito/DynamoDB para reemplazar Supabase;
no se integró a la aplicación ni hay usuarios. Ver
`docs/MIGRACION_SUPABASE_A_COGNITO.md`.

1. Un frontend HTTPS necesita una API HTTPS alcanzable desde el navegador; no
   se ha localizado ni desplegado una. Sin ella el sitio no funcionaría para
   terceros. Una IP EC2 con HTTP no resuelve contenido mixto ni confidencialidad.
2. El backend FastAPI local lee archivos locales de mercado; conectar solo
   Streamlit a S3 no conecta React ni FastAPI al lake. Debe diseñarse y probarse
   una ruta de datos consistente, con autenticación, permisos y contratos.
3. Supabase usa clave `service_role` en el backend. Solo se comprobó presencia
   de variables en archivos locales, no su validez o la seguridad de su
   configuración. Nunca incluirla en el bundle público ni en el repositorio.
4. La ampliación de 35 sigue provisional; fuentes y modelos no validados no
   deben exponerse como componentes o señales oficiales.
5. Para HTTPS en una EC2 se necesita una solución de certificado verificable
   y una identidad de host adecuada; no se ha confirmado dominio, DNS,
   seguridad de red ni permisos. La instancia de otro proyecto queda intacta.

## Decisiones y pruebas necesarias

- Confirmar presupuesto máximo adicional y periodo de operación antes de
  iniciar EC2 u otro recurso con costo. No habilitar servicios de pago
  adicionales por suposición.
- Determinar dominio o alternativa HTTPS autorizada, plan de autenticación y
  manejo seguro de secretos. Revisar acceso administrativo y endpoints públicos.
- Definir fuente de datos del backend y probar end-to-end, sin fallback
  silencioso a datos simulados cuando se anuncien como reales.
- Solo después compilar con la URL HTTPS definitiva de la API, revisar el
  bundle, publicar una rama Amplify y probar acceso, CORS, login, expiración,
  autorización y datos. El despliegue debe ser reversible sin afectar S3,
  Scheduler, Lambda existente ni los laboratorios.
