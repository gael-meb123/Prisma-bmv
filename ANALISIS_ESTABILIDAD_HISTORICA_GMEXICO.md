# Estabilidad historica de GMEXICO dentro de desarrollo

- Version: `ESTABILIDAD_DESARROLLO_GMEXICO_V1`.
- Dictamen: **signo contrarian estable, desempeno predictivo heterogeneo**.
- El aporte incremental de USD/MXN y cobre resulta desfavorable en este
  diagnostico, tanto con entrenamiento expansivo como con ventana movil.
- No se entreno, ajusto ni evaluo con observaciones de Test o prospectiva.
- No se emitieron senales ni se cambiaron parametros de produccion.

## Datos y alcance

- Fuente local: `experimento_gmexico_macro/dataset_experimento.csv`.
- Se filtra `periodo_oficial == TRAIN` y origen no posterior a 29/04/2025
  antes de convertir las variables y los objetivos a numeros.
- Solo se admiten etiquetas disponibles y con fecha objetivo no posterior al corte.
- Desarrollo elegible: **1,167 ejemplos PPP**, de los cuales **968** tienen
  las dos variables externas completas.
- Fechas efectivamente presentes: origen 28/11/2016 a 04/04/2025;
  ultima fecha objetivo observada 11/04/2025. La diferencia respecto al corte
  nominal refleja los huecos documentados, no un arrastre de precios.
- Evaluacion externa: semestres desde 2019-H1 a 2025-H1 parcial.
- 2016-2018 aportan historia inicial de entrenamiento, no pronosticos evaluados.
- Cada modelo/politica tiene **12 bloques externos evaluables**.
- Observaciones fuera de muestra interna: **803 PPP completas** y **664 pareadas**.
- El bloque 2023-H2 queda documentado como insuficiente: 3 ejemplos PPP y
  2 pareados. Se exige un minimo de 20 observaciones por bloque de validacion.

## Diseno sin anticipacion entre periodos

- Politicas de entrenamiento:
  - Expansiva: toda la historia anterior elegible.
  - Movil: origen dentro de los tres anios anteriores al inicio de validacion.
- En cada bloque externo:
  - Toda etiqueta de Train vence antes del inicio calendario de validacion.
  - Toda etiqueta evaluada vence dentro del propio bloque externo.
  - La logistica L2 no utiliza ponderacion de clases.
  - La regularizacion se selecciona de nuevo mediante validaciones internas
    semestrales contenidas estrictamente en ese Train externo.
  - Minimos: 100 observaciones de Train, 20 de validacion y dos folds internos.
  - Candidatos: `C = 0.01, 0.1, 1, 10`.
  - Regla: menor C dentro de un error estandar del mejor Brier medio interno.
  - El escalado se ajusta de nuevo exclusivamente en cada Train.
  - El Dummy usa la prevalencia del Train disponible en ese paso, no la del
    desarrollo completo ni la del bloque evaluado.
- Todos los ajustes externos seleccionaron **C = 0.01** mediante su pasado.
  Es estabilidad dentro del catalogo evaluado; no demuestra optimalidad fuera de el.
- No se reutiliza retroactivamente el C elegido con todo el desarrollo como
  si hubiera sido conocido en 2019.
- Los modelos pareados PPP y PPP + factores tienen identicos Train, fechas de
  validacion y presupuesto de ajuste. El modelo PPP completo se presenta aparte
  para diagnosticar la sensibilidad a perder cobertura.

## Resultado PPP con toda su cobertura

- Entrenamiento expansivo, 803 predicciones:
  - Brier **0.250626**.
  - Dummy recalculado en cada paso: **0.251416**.
  - Balanced Accuracy **55.16%**.
  - Supera al Dummy por Brier en **7 de 12** bloques.
  - Diferencia global modelo menos Dummy: **-0.000790**.
  - IC95 por bloques: **[-0.007126, +0.007658]**; incluye cero.
  - La probabilidad constante 0.5 tiene Brier **0.250000**, ligeramente mejor
    que este modelo agregado. La mejora sobre el Dummy de prevalencia no basta
    para afirmar una ventaja probabilistica robusta.
- Ventana movil de tres anios, sobre las mismas 803 fechas:
  - Brier **0.253217**, frente a Dummy **0.253519**.
  - Balanced Accuracy **53.82%**.
  - Supera al Dummy en **7 de 12** bloques.
  - IC95 de su diferencia frente al Dummy: **[-0.006112, +0.007372]**.
- Acortar la historia no elimina la inestabilidad y empeora el resultado agregado
  sobre la cobertura PPP completa.

## Variacion entre periodos

- Ejemplos del PPP completo con politica expansiva:
  - 2019-H2: n=40; Brier **0.255274**; Balanced Accuracy **46.74%**.
  - 2020-H1: n=58; Brier **0.262554**, frente a Dummy **0.252986**.
  - 2022-H2: n=122; Brier **0.240743**; Balanced Accuracy **61.14%**.
  - 2023-H1: n=39; Brier **0.230061**; Balanced Accuracy **69.84%**.
  - 2025-H1 parcial: n=50; Brier **0.232852**; Balanced Accuracy **70.93%**.
- Descriptivamente, los ultimos cinco bloques observables mejoran al Dummy.
  No son cinco semestres consecutivos completos: 2023-H2 no es evaluable.
- Las exactitudes altas de los bloques pequenos no acreditan una tasa estable
  de aciertos cercana a 70%. El agregado y su incertidumbre son mas prudentes.
- Se guardan tambien prevalencia Train/validacion, sesgo de probabilidad media,
  log-loss, AUC y deriva de las variables en unidades estandarizadas.

## Estabilidad de la senal contrarian

- La correlacion de `ret_10` con el objetivo permanece negativa en los
  **12 bloques de validacion** del PPP completo y del pareado.
- En el PPP completo expansivo, la correlacion de validacion oscila entre
  aproximadamente **-0.4932** y **-0.0190**: el signo persiste, la intensidad no.
- El coeficiente estandarizado de `ret_10` tambien es negativo en todos
  los ajustes de ambas politicas y variantes.
- Para el PPP completo expansivo, ese coeficiente va de **-0.1540 a -0.1030**.
- Esto respalda la persistencia descriptiva de la asociacion contraria al retorno
  reciente. No demuestra estacionariedad del precio, causalidad ni que la senal
  baste para superar de manera estable una probabilidad base.
- Los coeficientes proceden de entrenamientos solapados y no son replicas
  independientes. Tampoco se ha probado significancia individual de cada correlacion.

## Aporte incremental de USD/MXN y cobre

- Comparacion sobre **664 fechas identicas**:
  - Politica expansiva:
    - PPP pareado: Brier **0.248686**; Balanced Accuracy **56.50%**.
    - PPP + factores: Brier **0.250000**; Balanced Accuracy **56.20%**.
    - Diferencia factores menos PPP: **+0.001314**.
    - IC95: **[+0.000430, +0.002228]**.
    - Los factores mejoran Brier en **3 de 12** bloques.
  - Ventana movil de tres anios:
    - PPP pareado: Brier **0.248514**; Balanced Accuracy **56.22%**.
    - PPP + factores: Brier **0.250822**; Balanced Accuracy **54.61%**.
    - Diferencia: **+0.002309**.
    - IC95: **[+0.000662, +0.003973]**.
    - Los factores mejoran en **5 de 12** bloques.
- Una diferencia positiva significa deterioro probabilistico por incorporar
  los factores. En este diagnostico el resultado desfavorable aparece bajo
  ambas politicas de entrenamiento.
- La ventana movil mejora muy poco el Brier del PPP pareado respecto al expansivo,
  pero lo empeora en la cobertura completa. No aparece una ventaja general de
  acortar la historia que justifique cambiar la politica de referencia.

## Incertidumbre y limites

- 5,000 replicas, bloques de 20 sesiones BMV, semilla 20261029.
- La rejilla conserva ausencias; no se comprime el tiempo para unir huecos.
- Para el agregado se remuestrea dentro de cada fold y se mantienen pesos
  proporcionales a su numero original de observaciones. No se mezclan bloques
  que atraviesen fronteras de reentrenamiento.
- Las replicas sin ninguna observacion valida se descartan y se vuelven a generar;
  se documenta su conteo, sin sustituirlas por ceros.
- Los intervalos condicionan los parametros y predicciones observados; no
  incorporan toda la incertidumbre de estimacion ni corrigen multiplicidad.
- Los factores mantienen la hipotesis conservadora de rezago de una sesion.
  Las fuentes actuales no acreditan todas sus vintages y horas de publicacion.
- Los huecos y la seleccion por presencia en boletines limitan la extrapolacion
  a todas las sesiones negociadas. No se concluye rentabilidad de negociacion.
- Este es un diagnostico de desarrollo, no una nueva prueba prospectiva independiente.

## Decision recomendada

- Conservar la logistica PPP fuertemente regularizada como referencia experimental.
- No incorporar los dos factores a produccion con esta evidencia.
- Mantener la politica expansiva de referencia: la ventana movil no muestra
  una mejora consistente entre coberturas.
- Describir GMEXICO como una senal contrarian persistente pero de rendimiento
  heterogeneo, no como un modelo de precision estable ya demostrada.
- La confirmacion exige seguimiento prospectivo con reglas y disponibilidad
  registradas antes de conocer los resultados.

## Archivos y verificacion

- Codigo: `estabilidad_historica_gmexico.py`.
- Protocolo y reporte: `estabilidad_gmexico_desarrollo/protocolo.json` y `reporte.json`.
- Datos utilizados: `desarrollo_utilizado.csv`, solo desarrollo elegible.
- Resultados por periodo: `metricas_por_periodo.csv`.
- Predicciones externas internas: `predicciones.csv`.
- Periodos evaluados y omitidos: `cobertura_periodos.csv`.
- Busqueda y auditoria temporal: `busqueda_C_interna.csv`, `particiones_internas.csv`.
- Parametros y deriva: `coeficientes.csv` y metricas por periodo.
- Ejecutar: `python -B estabilidad_historica_gmexico.py`.
- Pruebas: `python -B -m unittest -v test_estabilidad_historica_gmexico`.
- **12 pruebas pasan**: incluyen contaminacion deliberada de filas futuras,
  purga anidada, reconstruccion de probabilidades, scaler y Dummy solo pasados,
  pareamiento, periodos insuficientes, agregacion y conservacion de hashes.
- Los hashes verifican la conservacion de los datos PPP, las senales originales
  y los resultados anteriores del experimento, incluyendo sus predicciones de Test.
