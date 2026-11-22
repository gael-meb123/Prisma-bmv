# Avance: Silver diario y elegibilidad de inferencias

## API de mercado

La API aislada consulta primero la instantánea para conocer fechas y, cuando
existe, utiliza el CSV Silver diario correspondiente. Comprueba fecha, campos
y claves de emisora/serie. Solo si S3 informa que el objeto no existe usa la
instantánea anterior; errores de permisos, formato o duplicados devuelven 503
sin respaldo silencioso. No modifica Silver.

En la prueba real para 2026-11-17 se observaron 15 filas, 12 PPP marcados
verificados y 12 variaciones, frente a 12 filas y ninguna variación en la
instantánea. Para 2026-11-19 hubo 15 filas, cero PPP y cero variaciones
verificadas; no se mostró la contingencia como dato oficial. La fuente en la
respuesta es `silver_diario_s3`; las cifras dependen de los estados declarados
en Silver y no certifican por sí solas el documento ni su licencia.

React experimental indica el tipo de fuente, evita atribuir a un estado ausente
que no hubo operación y señala que la conciliación automática está pausada.
La API se publicó con el artefacto
`80315bcbdf119e724761327ef8c0e291a66c54ad355fa44ab8072efaeddb0e11.zip`.

## Ventanas de señales

`scripts/auditar_ventanas_diarias.py` utiliza el calendario local existente
para generar 21 sesiones, lee archivos diarios locales y aplica
`prisma/domain/elegibilidad_senales.py`. La regla exige por fecha clave única,
estado oficial, precio positivo, hash declarado, URL BMV del corte y una serie
consistente. Para variables relativas exige al menos dos emisoras elegibles.
No verifica que el hash corresponda al HTML ni certifica los modelos.

Se descargaron copias locales de los Silver diarios de octubre y noviembre de
2026 sin modificarlos. Para el corte 19-11, la ventana va del 20-10 al 19-11:
14 archivos presentes y 7 ausentes. Cada una de las cinco emisoras AMX, FEMSA,
GFNORTE, GMEXICO y WALMEX tiene 7 fechas sin archivo y 3 estados no oficiales.
Ninguna pasa la regla conservadora con este conjunto de archivos. Ausencia de
archivo no demuestra que BMV no publicara datos: podría existir otra fuente.

La auditoría no emite ni altera señales. La regla sigue **sin integración en
la Lambda activa**, por lo que el Scheduler permanece deshabilitado y la API
mantiene bloqueadas las señales.

## Fuente secundaria

`prisma/data/yahoo_secundario.py` interpreta una respuesta JSON aportada por el
llamador, sin HTTP ni escrituras. Valida símbolo, moneda, fecha y un único
cierre positivo; conserva el hash de la respuesta y lo identifica como cierre
diario secundario no validado, nunca como PPP. Las pruebas son sintéticas.
No está conectado a la ingesta, a la API ni a la publicación; faltan pruebas
reales, condiciones de uso y política de conservación y redistribución.

## Fórmulas históricas y navegador

`scripts/auditar_formulas_panel.py` contrasta ocho indicadores ajustados del
panel contra sus propios precios ajustados, únicamente cuando las posiciones
de sesión son consecutivas y existen todos los valores necesarios. Con
tolerancia absoluta `1e-8`, no se detectaron diferencias en los grupos
comparables: retornos a 1, 5, 10 y 20 sesiones (9709, 9090, 8388 y 7175),
distancias a medias 5 y 20 (9239 y 7281), y volatilidades 5 y 20 (9090 y
7175). Esto es coherencia aritmética interna, no prueba que los precios
ajustados, dividendos, fechas, derechos o valores no comparables sean válidos.
El panel sigue sin habilitarse en la API.

La prueba del React publicado, usando Chrome con seguridad web activa y la
cuenta sintética, completó acceso y seleccionó 17-11: aparecieron 15 filas,
con precio y variación de WALMEX, y fuente Silver diario. También confirmó
estadística parcial y bloqueos de ficha y señales. En una prueba anterior se
detectó una condición de carrera de carga de perfil y un 503 temporal; se
corrigió la sincronización y se añadió un solo reintento cancelable a lecturas
públicas de mercado/sectores, sin reintentar escrituras o señales. La prueba
posterior pasó, pero no sustituye pruebas de carga ni validación integral.
