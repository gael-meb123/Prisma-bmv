# Administración, conciliación y pruebas: 19-11-2026

## Administración

La API aislada expone `GET /api/admin/usuarios` y
`PATCH /api/admin/usuarios/{uid}`, protegidas por Cognito y por rol en
DynamoDB. El listado consulta de forma consistente, recorre páginas y devuelve
error en lugar de truncar silenciosamente por encima de 1000 perfiles. El PATCH
valida los campos y usa una transacción DynamoDB: verifica que el actor siga
siendo administrador y que el perfil objetivo exista; impide la autodemoción.
Cuando actor y objetivo son el mismo perfil, la condición y la actualización
se ejecutan en una sola operación transaccional.

Prueba real con el usuario sintético: rol normal `403` para listar y editar;
sin token `401`; rol admin `200` para listado y cambios de plan,
autodemoción `400`, plan inválido `422` y objetivo inexistente `409`. El
perfil se restauró a `user/explorer`. No se imprimió el listado ni las
credenciales. El alta de usuarios no se ha migrado: coordinar Cognito y
DynamoDB requiere un flujo seguro para fallos parciales e invitaciones; React
local oculta el formulario de alta en modo Cognito.

Las rutas de señales y seguimiento fueron creadas con JWT y control de plan,
pero responden **503 explícito** mientras no se valide la procedencia. Esto no
es una migración funcional de sus datos. No devuelven arrays vacíos que puedan
interpretarse como ausencia de señales.
Prueba HTTPS con token real de Explorer: panel y seguimiento de WALMEX `503`;
señal AMX fuera de plan `403`; sin token e ID token `401`. Último artefacto de
la API:
`artifacts/api-gateway/e9371feceb670ed1efd673fee2ab6a1d1a70c4ad0aa465325ba56c7707b5be51.zip`.

## Cruce con Silver diario y Bronze

`scripts/auditar_senales_por_corte.py` compara Gold con Silver diario usando
fecha, emisora y serie exactas. No cambia objetos ni certifica modelos.

- 17-11: 30 filas Gold coinciden en clave y precio con el Silver diario marcado
  verificado; las 30 tienen hash distinto al Silver diario. El SHA-256 del HTML
  Bronze y su archivo `.sha256` coinciden con el de Silver
  (`679ea77d638f4776333eb86605b574f4ae55fe64e7d2f062535a3990cb9301ae`),
  mientras las 30 filas Gold registran
  `f506a5dd4df1726d796cd26dcee7396d13eb7468fd93c5ce44a54c3d971205bd`.
  No se ha identificado el origen de esa diferencia.
- 19-11: 30 filas Gold coinciden en clave, precio y hash con Silver de
  contingencia Yahoo. No son PPP verificados de BMV.

Estos resultados refinan el cruce anterior con la instantánea unificada, que
había perdido series para esas fechas. Ninguno acredita las ventanas de datos,
los resultados t+5 ni la integridad de una inferencia. No se reescribieron
señales ni datos. La URL BMV del 19 seguía respondiendo 404 y no se ha
confirmado composición oficial fechada ni alias de las candidatas.

## Pruebas de navegador y React

Una prueba Chrome headless accedió al sitio Amplify real, cargó datos desde la
API y verificó 14 filas de contingencia, sin precios PPP o variaciones
mostrados como oficiales. Es la vista preliminar, no la aplicación completa.
El React local bloquea la ficha heredada en modo de API real porque contenía
precio y hash de ejemplo, limpia datos anteriores mientras se recarga una
sección y permite que falle una ruta sin descartar todos los demás recursos.
Una prueba local de Chrome detectó y ayudó a corregir un error de arranque
(`global` no definido) y limitaciones de concurrencia de Lambda. Se añadió una
cola cancelable de dos peticiones a la interfaz y carga por sección.
En una repetición, Cognito real inició sesión con el usuario sintético, la
terminal cargó y estadística respondió `200`, indicando correctamente que el
panel ajustado no está disponible. La ficha de ejemplo permaneció bloqueada.
En esa prueba local Chrome tenía `--disable-web-security` para permitir el
origen localhost, por lo que **no valida CORS de producción**. El CORS del
origen Amplify y su vista preliminar se probaron por separado; React completo
no está publicado ni fue probado íntegramente. La ruta macro respondió `404`.

El panel ajustado sigue sin conectarse a la API. Se identificó una fuente
local con 9879 filas históricas hasta el 28-10-2026, enlazadas por clave al
histórico local, pero aún no se han acreditado las ventanas ni los derechos
de redistribución. No se publicó ni se presentó como panel actual.

Una comprobación adicional reproducible en `scripts/auditar_panel_estadistico.py`
encontró que las 9879 claves y precios base coinciden con el histórico local;
9866 tienen los 21 estados de captura anteriores declarados como verificados y
13 contienen al menos un faltante o estado diferente. Esta comprobación no
certifica las evidencias, el cálculo de los indicadores ajustados ni la
autorización para distribuirlos. Los SHA-256 son
`92201443e18dfe92f27038b232d038c6314d5e9029b523c55c089e900f665067`
para el histórico y
`b72463e85623242e61dc1bbad5a5c945c02b7ac5d4c014d5a2594f437a37ba4b`
para el panel.
