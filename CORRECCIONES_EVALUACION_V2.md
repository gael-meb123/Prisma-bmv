# Correcciones de evaluacion PPP — version 2

- Estado: correccion aplicada al panel y a los reportes derivados. La fuente original
  `serie_ppp_historica_15_emisoras_bmv.csv` conserva su hash SHA-256.
- Evidencia de migracion: `auditoria_evaluacion_v2/manifiesto.json`.
- Resultados anteriores: `auditoria_evaluacion_v2/antes/`.

## Contrato de variables

- `metodologia_ppp.py` concentra el orden de las ocho entradas y sus formulas.
- Se requieren 21 PPP reales, finitos, positivos y consecutivos en el calendario.
- `distancia_media_20 = PPP_t / media(PPP_{t-19}, ..., PPP_t) - 1`.
- La misma funcion se utiliza en el panel, el ejecutor diario y las entradas
  transformadas del experimento de dividendos.
- Version de entradas: `PPP_V2_MEDIA20`. El panel anterior usaba 21 precios
  para esa media; las senales originales de GMEXICO conservan esa identificacion.
- Los parametros congelados del control WALMEX siguen siendo compatibles con
  la media de 20 precios: la prueba reproduce su probabilidad registrada.
- El ajuste por dividendos es una variante de entradas transformadas; nunca
  reemplaza el PPP utilizado para resolver el objetivo.

## Cortes y etiquetas

- Train: origen y fecha objetivo no posteriores a `2025-04-29`.
- Test: origen dentro de Test y fecha objetivo no posterior a `2026-10-27`.
- Las etiquetas que terminan el `2026-10-28` se conservan en el dataset,
  pero quedan fuera de las metricas de ese Test.
- Por esa razon GMEXICO pasa de 291 a 290 ejemplos evaluados. Mantiene 1,167
  ejemplos de entrenamiento; no se encontro fuga de frontera en esa muestra.
- El ejecutor filtra los retadores por `fecha_fin_label_h5 <= fecha_senal` y
  comprueba la ultima fecha de etiquetas de los parametros congelados.
- El Test ya fue inspeccionado: la comparacion corregida sigue siendo exploratoria.

## Resolucion y huecos

- Se consulta el PPP de la fecha bursatil objetivo exacta; no se cuenta la quinta
  cotizacion disponible. Los huecos intermedios no desplazan el vencimiento.
- Si falta el PPP objetivo y la serie ya alcanzo esa fecha, el estado es
  `NO_RESOLUBLE_PPP_OBJETIVO_AUSENTE`. No se calculan acierto, Brier ni log-loss.
- Se limpian metricas antiguas antes de resolver para evitar resultados residuales
  de un vencimiento desplazado. Las senales anuladas no se evaluan.
- La actualizacion diaria conserva fechas sin captura como huecos documentados,
  sin precios imputados. Una ausencia de WALMEX en el boletin tambien se registra.
- La captura en vivo utiliza el parser estricto de la reconstruccion historica;
  no interpreta una columna de variacion como PPP cuando se omite el precio.
- Se rechazan fechas base y vencimientos no verificables. En particular, no se
  extienden las reglas de 2026 a un calendario 2027 aun no incorporado.
- El vencimiento del origen `2026-10-28` sigue siendo `2026-11-05`.

## Emisiones y versiones

- Se distinguen `fecha_corte_datos`, `timestamp_emision_utc` y
  `fecha_emision_real` (America/Mexico_City).
- Los timestamps originales desconocidos permanecen desconocidos. No se infiere
  retrospectivamente un momento de emision a partir de la fecha del precio.
- Las probabilidades, clases, precios base, fechas objetivo e IDs originales
  se conservan y se comparan con el respaldo durante la migracion.
- El marcador agrupa por rol y versiones de metodologia/entradas. Solo incorpora
  a sus metricas prospectivas emisiones con timestamp documentado, no anterior
  a la fecha de datos y anterior a la fecha objetivo. Esta regla diaria conservadora
  no acredita ejecucion intradia ni rentabilidad negociable.
- `reporte_investigacion_profunda_gmexico.json` guarda la simulacion corregida bajo
  `recalculo_retroactivo_20261028`, separada de los registros de emision.
- `registrar_senales_gmexico.py` actualiza exclusivamente trazabilidad del registro
  existente; no vuelve a emitir ni sobrescribe pronosticos historicos recalculados.

## Algoritmos

- Elastic Net normaliza la penalizacion por el numero de muestras para hacerla
  coherente con la perdida promediada. Comprueba convergencia con residuo proximal
  KKT; con `l1_ratio=0` reproduce la logistica L2 IRLS dentro de tolerancia numerica.
- El GBDT ajusta arboles de regresion a residuos reales de log-loss. No convierte
  sus signos en etiquetas binarias para repetir el mismo clasificador.
- Las correcciones de implementacion no seleccionan hiperparametros con Test.

## Resultados corregidos de GMEXICO

- Muestra: 1,167 Train y 290 Test.
- Dummy de prevalencia Train: Brier **0.251529**.
- Logistica L2 balanceada: Brier **0.249589**, Balanced Accuracy **56.00%**.
- Elastic Net: Brier **0.249292**, Balanced Accuracy **56.60%**.
- MLP: Brier **0.249067**, Balanced Accuracy **55.93%**.
- Estos resultados no demuestran por si solos significancia estadistica ni
  rentabilidad. Las metricas anteriores permanecen en el respaldo.

## Verificacion reproducible

- Ejecutar `python -B -m unittest -v test_evaluacion_ppp`.
- Las pruebas utilizan PPP reales del panel y archivos temporales aislados.
- Incluyen feriado del 2 de noviembre, huecos omitidos, target ausente,
  purga temporal, compatibilidad WALMEX, emision completa, trazabilidad,
  regularizacion y ajuste de residuos del GBDT.
- La migracion se ejecuta con `python -B corregir_evaluacion_ppp.py` y es idempotente.
- El ejecutor diario acepta `python -B etapa10_ejecutor_diario.py --fecha YYYYMMDD`.
  La fecha predeterminada corresponde al dia actual en Mexico.
