# Hallazgos en el repositorio de origen y cómo se resolvieron

Revisión del código Streamlit, de las Lambdas y de los datos de `Prisma-bmv-main`. Cada hallazgo tiene una prueba automática que impide que vuelva a aparecer.

| # | Hallazgo | Impacto | Resolución | Prueba |
|---|---|---|---|---|
| 1 | `lambda_function_con_ia.py` usaba coeficientes y escaladores escritos a mano que no coinciden con `registro_modelos_g2_oficial.json`. | WALMEX 28/10, modelo V1: la Lambda daba 0.5049 (SUBIDA) y el registro, 0.4983 (NO_SUBIDA). La clase se invertía. | La Lambda lee los parámetros oficiales desde `gold/modelos/`. | `test_features_e_inferencia_reproducen_el_registro` |
| 2 | La misma Lambda aplicaba `dropna()` y tomaba "los últimos 11/21 precios". | Juntaba sesiones no contiguas: era imputación implícita. | Ventana estricta de 21 sesiones del calendario BMV. Un hueco bloquea la emisora ese día. | `test_un_hueco_en_la_ventana_bloquea_la_emisora` |
| 3 | `ret_10_rel_panel` se guarda como fracción, pero la vista lo mostraba como porcentaje. | GMEXICO aparecía con −0.09 % en lugar de −9.47 pp, y la explicación de sobreventa nunca se activaba. | Conversión explícita a puntos porcentuales, más una desviación estandarizada con el escalador oficial. | `test_factor_clave_en_puntos_porcentuales` |
| 4 | Tarjetas de auditoría, respuestas de Prismi y el sello "57/57 tests" estaban escritos a mano. | Había cifras que no coincidían con los datos: "−13.06 %" de rezago, y un acierto de V1 en WALMEX que en realidad predijo NO_SUBIDA. | Todas las cifras se calculan a partir del lakehouse, y Prismi recibe un contexto generado de los datos. | `test_marcador_reproduce_resumen_oficial`, `test_prismi_responde_con_cifras_reales` |
| 5 | Contraseñas con un solo SHA-256 y `usuarios.json` en texto plano dentro del repositorio. | Expuesto a ataques por fuerza bruta y a fugas al compartir el repositorio. | PBKDF2-SHA256 con 600 000 iteraciones, almacén cifrado con Fernet, migración automática de las cuentas existentes y bloqueo tras 5 intentos. | `test_seguridad_y_pagos.py` |
| 6 | El registro permitía elegir Enterprise sin pagar. | El modelo freemium no se podía hacer cumplir. | Toda cuenta nace en Explorer; los planes de pago solo se activan con un cobro aprobado en la pasarela sandbox. | `test_registro_siempre_inicia_en_explorer`, `test_checkout_sandbox_activa_professional` |
| 7 | El 28/10 incluía GCARSO, KOF y ORBIA (fuera de la lista oficial, con otra firma). | El KPI mostraba 18 emisoras. | Filtro de la lista oficial al leer los datos. | `test_normalizacion_lista_oficial_y_etiqueta_unica` |
| 8 | Había dos etiquetas de hueco: `NO_PUBLICADA_…` y `NO_PUBLICADO_…`. | Los conteos de huecos salían incompletos. | Se normalizan a `NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA`. | idem |
| 9 | La Lambda escribía CSV con BOM y sobrescribía Bronze y las señales en cada ejecución. | Athena leía mal el primer encabezado, y Bronze y las señales emitidas no eran inmutables. | UTF-8 sin BOM, Bronze de solo escritura con detección de divergencias y `keep="first"` en Gold. | `test_lambda.py` |
| 10 | No existía seguimiento t+1 a t+5 en la nube: la Lambda guardaba `acierto_parcial_en_curso = None` para siempre. | La auditoría en AWS no avanzaba. | `actualizar_seguimiento`, idempotente, que solo resuelve con el PPP exacto de t+5. | `test_seguimiento_reproduce_registro`, `test_hueco_en_t5_no_se_sustituye` |
| 11 | Prismi usaba `claude-3-5-sonnet-20241022`, un modelo ya retirado. | Todas las consultas caían al motor local sin aviso. | El modelo es configurable con `PRISMI_MODEL` y tiene un valor por defecto vigente. | — |
| 12 | El parser no desescapaba entidades HTML. | `PE&amp;OLES` podía no coincidir con `PE&OLES`. | `html.unescape` en cada celda. | `test_parser_extrae_ppp_y_desescapa_entidades` |
| 13 | Rutas absolutas de un equipo personal y documentos con referencias institucionales en varios scripts de investigación. | Incumplía la regla de identidad de marca. | No se trasladaron a la plataforma, y hay una prueba que bloquea esos términos. | `test_sin_identidad_academica_en_codigo_entregado` |

## Diferencias residuales conocidas

- **G2-V1 y G2-V2:** al reconstruirlos con el registro oficial, difieren hasta 0.0013 de la probabilidad registrada por el monitor local. En dos señales de WALMEX con probabilidad casi exacta de 50 % (28/10 V2 y 29/10 V1), esa diferencia invierte la clase. La Lambda marca sus filas con `origen_inferencia = LAMBDA_RECOLECTOR_DIARIO_BMV` para distinguirlas. Se recomienda volver a exportar el JSON desde el monitor después de cada recalibración.
- **G2-V3:** se reentrena con toda la historia purgada hasta cada corte. El registro congelado lo reproduce exactamente en las fechas evaluadas, pero se irá alejando con el tiempo si no se vuelve a exportar.
- **Bronze:** los HTML históricos no venían en el ZIP (la carpeta `cache_boletines/` estaba excluida), así que Bronze empieza con la primera ejecución de la Lambda. Las filas históricas de Silver conservan su SHA-256.

## Fuera de alcance

El frontend en React (`frontend/`) y la API FastAPI (`api.py`) del repositorio de origen no forman parte de esta entrega, que se limita a la terminal Streamlit. Los scripts de investigación y experimentación siguen siendo válidos como herramientas de laboratorio y no se modificaron.
