# Reporte descriptivo histórico

El módulo `prisma.data.estadistica_descriptiva` genera un JSON reproducible para
consulta externa. La terminal también muestra el análisis en «Análisis
estadístico», por emisora y con acceso sujeto al plan. El endpoint calcula el
reporte desde los CSV locales; no ejecuta inferencia ni modifica modelos o datos.

```powershell
python -m prisma.data.estadistica_descriptiva --salida reporte_descriptivo.json
python -m prisma.data.estadistica_descriptiva --desde 2025-01-01 --hasta 2025-12-31 --emisora GMEXICO --salida gmexico_descriptivo.json
```

Los filtros son inclusivos. `--sector` acepta el nombre exacto del sector y
`--sin-ajuste` usa las variables originales del panel; por defecto usa las
ajustadas. El destino debe ser un archivo que no exista: no se sobrescribe.

El reporte distingue la cobertura de la serie histórica de la del panel, que
abarcan periodos diferentes. Cuenta todos los estados y los faltantes de cada
fuente; calcula medidas y frecuencias solo para filas con estado
`PPP_PUBLICADO_VERIFICADO`. Para el panel, el estado se vincula por fecha,
emisora y serie; las claves duplicadas producen error y las filas sin estado
se excluyen. No se imputan datos. El estado verificado de la fecha actual no
garantiza la cobertura de toda la ventana de un indicador del panel: se respetan
las variables ya calculadas y sus faltantes.

Contiene descriptivos globales y por emisora/sector, frecuencias de dirección,
datos de histograma y resúmenes de caja de la variación, serie temporal y
correlaciones Pearson/Spearman por pares completos sobre la muestra del panel
verificado. La variación histórica está en porcentaje; los rendimientos y
volatilidades del panel en escala decimal. La desviación es muestral, los
cuartiles utilizan interpolación lineal y la curtosis es exceso de Fisher.
Correlaciones exploratorias no implican causalidad; no se calculan p-valores.
