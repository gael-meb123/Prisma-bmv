# React experimental y pausa de ingesta

El 19-11-2026 el usuario autorizó pausar el recolector. El Scheduler
`DisparadorDiarioBMV` quedó `DISABLED`; conserva la expresión de lunes a
viernes a las 16:45 CDMX y la Lambda de destino. Se guardó una copia local de
su configuración previa en el directorio temporal de OpenCode. La pausa
detiene también la captura automática de BMV y Yahoo; no evita invocaciones
manuales o por otros disparadores y no se debe reactivar sin corregir el flujo.

La Lambda desplegada que se inspeccionó admite contingencia en las ventanas de
inferencia. No se modificó ni reactivó esa función. La regla local de
`prisma/domain/elegibilidad_senales.py` requiere 21 sesiones proporcionadas por
un calendario verificado, estados oficiales, precios positivos, huellas y
orígenes BMV, y dos emisoras aptas para métricas relativas. La comprobación es
de metadatos declarados: no autentica documentos ni valida modelos, y aún no
está integrada ni desplegada en el recolector. La API sigue bloqueando señales
y seguimiento. No se reescribió Gold.

React se publicó como versión **experimental e incompleta** en una rama manual
separada:

https://react-demo.d315dh37vi024o.amplifyapp.com/

La rama `demo` anterior no se sustituyó. La API acepta ambos orígenes mediante
CORS. El sitio experimental usa Cognito y la API aislada, sin fallback a mocks.
Mercado e histórico tienen cobertura parcial; estadística no incluye el panel
ajustado. Señales, consenso, seguimiento, auditoría, gobernanza, ficha,
registro y cambio de plan no se presentan como funciones completas. La
visualización pública de valores Yahoo sigue pendiente de revisar condiciones
y procedencia: el recolector anterior puede sustituir su VWAP por un cierre o
un promedio y no registra de forma fiable cuál de ellos usó.

La publicación manual más reciente (`react-demo`, trabajo 2) terminó
`SUCCEED`. Una prueba Chrome headless con seguridad web habilitada y el usuario
sintético comprobó acceso, terminal, estadística parcial HTTP 200, señales y
ficha bloqueadas, y presencia del control de verificación de correo. No probó
entrega de correo ni recuperación real. Se ejecutaron 30 pruebas Python y 10
JavaScript seleccionadas; el build compiló. Son pruebas parciales, no una
certificación integral ni de producción.

Se creó una cuenta de prueba Explorer para el correo suministrado. Cognito
aceptó el envío de la invitación, pero la entrega y la verificación del correo
no se han comprobado. La cuenta quedó inicialmente en `FORCE_CHANGE_PASSWORD`
y `email_verified=false`. No se marcó el correo como verificado manualmente.
La sección Seguridad permite solicitar un código y verificar el correo desde
el navegador. No compartir claves, contraseñas ni códigos por chat. El flujo
real de recuperación todavía requiere que la persona reciba el correo,
complete la verificación y pruebe la recuperación.
