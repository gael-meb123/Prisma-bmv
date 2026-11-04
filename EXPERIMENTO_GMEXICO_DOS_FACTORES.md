# Experimento GMEXICO: PPP + USD/MXN + cobre

- Estado: ejecutado como backtest exploratorio, version `GMEXICO_2_FACTORES_V1`.
- El protocolo se guardo tras explorar las fuentes y antes de construir la matriz
  pareada y calcular las metricas del experimento.
  El Test historico ya habia sido inspeccionado en investigaciones anteriores.
- Protocolo registrado: `experimento_gmexico_macro/protocolo.json`.
- Resultado completo: `experimento_gmexico_macro/reporte.json`.
- Ejecucion: `python -B experimento_gmexico_dos_factores.py`.
- Verificacion offline: `python -B -m unittest -v test_experimento_gmexico_dos_factores`.

## Fuentes

- USD/MXN: FIX por fecha de **determinacion**, Banxico. No se utiliza la columna
  de publicacion en DOF ni la de pago de obligaciones.
- Fuente: https://www.banxico.org.mx/tipcamb/tipCamMIAction.do?idioma=sp
- Metadatos oficiales: cuadro CF102 del SIE; el FIX se divulga a partir de las 12:00.
- Cobre: precio diario en USD/libra publicado por Banco Central de Chile,
  serie `LIBRA_COBRE`, matriz anual de Indicadores Diarios.
- Fuente: https://si3.bcentral.cl/indicadoressiete/secure/IndicadoresDiarios.aspx
- La fuente difunde el cobre redondeado a dos decimales. No se sustituyo por
  un contrato continuo de futuros, precios interpolados o promedios mensuales.
- Capturas HTML originales, URL, metodo, timestamp de descarga y SHA-256:
  `experimento_gmexico_macro/fuentes/manifiesto.json`.
- Las series normalizadas conservan dias sin valor como ausencias.

## Disponibilidad temporal

- Cada factor es `log(valor_t-1 / valor_t-6)` sobre las fechas de la rejilla BMV.
- Se exigen las seis observaciones reales del tramo anterior al origen.
- Si falta una, la fila se conserva documentada y se excluye del conjunto pareado.
- No se utiliza el dato del mismo dia, no hay arrastre y no se fabrican timestamps
  historicos de publicacion.
- **Limitacion:** las matrices historicas actuales no acreditan todas las horas
  originales de publicacion ni sus vintages. El rezago de una sesion es una
  hipotesis conservadora; este resultado no certifica disponibilidad point-in-time.
- Una confirmacion prospectiva debe almacenar cada captura antes de emitir la
  prediccion, con el instante efectivo de disponibilidad. No se emitieron senales
  retroactivas a partir de este experimento.

## Comparacion

- Base: ocho entradas PPP canonicas, version `PPP_V2_MEDIA20`.
- Ampliada: las mismas ocho mas dos factores externos.
- Modelo en ambas: logistica L2 sin ponderacion de clases.
- Se ajusta el escalado exclusivamente dentro de cada entrenamiento.
- Busqueda identica: `C = 0.01, 0.1, 1, 10`.
- Cuatro validaciones cronologicas en Train con etiquetas purgadas.
- Regla de seleccion: menor C dentro de un error estandar del mejor Brier medio
  entre folds. Es una regla de regularizacion, no un intervalo inferencial de Test.
- Train termina en etiquetas de 29/04/2025 y Test en etiquetas de 27/10/2026.
- Ambos modelos utilizan exactamente el mismo Train y Test pareados.
- La diferencia frente al benchmark balanceado anterior tambien incluye otro
  subconjunto y seleccion de regularizacion: no debe atribuirse al cobre o al FIX.

## Cobertura y resultados

- Train PPP elegible: 1,167; Train pareado: **968**.
- Test PPP elegible: 290; Test pareado: **215**.
- Exclusiones: 199 Train y 75 Test, por ventanas incompletas del cobre.
- Ambos modelos seleccionaron `C = 0.01` mediante Train.
- Base PPP: Brier **0.248033**; log-loss **0.688793**; Balanced Accuracy **57.95%**.
- PPP + factores: Brier **0.247689**; log-loss **0.688087**; Balanced Accuracy **57.95%**.
- Dummy de prevalencia del Train pareado: Brier **0.254925**.
- Diferencia Brier ampliada menos base: **-0.000343786**.
- Bootstrap pareado en rejilla BMV: 5,000 replicas, bloques de 20 sesiones,
  semilla 20261029; IC percentil 95% **[-0.000981162, 0.000210571]**.
- Subperiodo 2025: 102 casos; diferencia **+0.000012751**.
- Subperiodo 2026: 113 casos; diferencia **-0.000665617**.

## Decision

- **No cumple el criterio exploratorio registrado:** la mejora es menor a 0.001,
  el intervalo incluye cero y no mejora en ambos subperiodos.
- No hay evidencia suficiente para incorporar ambos factores a produccion.
- Se conserva el experimento como resultado documentado y el sistema PPP como
  referencia. Probar mas transformaciones sobre este Test requeriria declarar
  nuevos experimentos exploratorios y reservar confirmacion futura.
- Se verifican hashes de la fuente PPP, del panel y de los registros originales;
  el experimento escribe sus resultados en un directorio separado.
