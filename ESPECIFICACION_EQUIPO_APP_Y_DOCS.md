# Prisma BMV: Especificación Técnica de Transferencia para el Equipo
## Proyecto Final de Big Data (7º Semestre) - Noviembre 2026

Este documento define la distribución equitativa de responsabilidades, la arquitectura modular del código y los contratos de datos sin ambigüedades para los 4 compañeros del equipo:
- Compañero 1: Desarrollador App 1 (Ingesta de Datos y Monitor de Mercado BMV en Vivo)
- Compañero 2: Desarrollador App 2 (Motor de Señales Prospectivas y Consenso IA)
- Compañero 3: Desarrollador App 3 (Auditoría Temporal $t+1$ a $t+5$ y Gobernanza AWS)
- Compañero 4: Documentador Técnico (Memoria y Reporte Final Académico)

---

## 1. Arquitectura Modular de la Aplicación (Para Evitar Conflictos de Código)

Para que los tres desarrolladores puedan trabajar en paralelo sin pisarse el código ni generar conflictos de fusión (merge conflicts), la aplicación se estructura en módulos aislados:

```
D:\Universidad\7mo Semestre\Big Data\Proyecto final\
├── app.py                                   # Orquestador principal (Streamlit)
├── modulos/
│   ├── __init__.py
│   ├── conector_datos.py                   # Responsabilidad: Desarrollador 1
│   ├── vista1_mercado_en_vivo.py           # Responsabilidad: Desarrollador 1
│   ├── vista2_senales_consenso.py          # Responsabilidad: Desarrollador 2
│   └── vista3_auditoria_rendimiento.py     # Responsabilidad: Desarrollador 3
```

---

## 2. Asignación Equitativa de Responsabilidades

### Desarrollador 1: Ingesta de Datos y Monitor de Mercado BMV en Vivo
- Archivos a su cargo: `modulos/conector_datos.py` y `modulos/vista1_mercado_en_vivo.py`.
- Insumo de datos principal: `monitoreo_ppp_multiemisora_en_vivo.csv`.
- Tareas a desarrollar:
  - Crear la función `cargar_datos_mercado()` con caché (`@st.cache_data`) que lea el CSV local o desde S3/Athena.
  - Diseñar la Vista 1 con los siguientes componentes:
    - Selector interactivo de fecha (por ejemplo, 28/10/2026, 29/10/2026, 30/10/2026).
    - Tarjetas de métricas (KPIs): Total de emisoras monitoreadas (15), Emisoras verificadas (10), Emisoras ausentes (5), Ganadora del día (mayor % alza), Perdedora del día (mayor % baja).
    - Tabla interactiva con formato visual condicional: Verde para variación positiva, Rojo para negativa, y etiqueta clara `NO_PUBLICADA` para emisoras sin cotización.
    - Filtro por Sector Económico (Minería, Banca, Telecomunicaciones, Consumo, etc.).
    - Indicador de integridad criptográfica: Muestra del hash SHA-256 oficial del boletín con enlace a la fuente oficial de la BMV.

### Desarrollador 2: Motor de Señales Prospectivas y Consenso IA
- Archivos a su cargo: `modulos/vista2_senales_consenso.py`.
- Insumos de datos principales: `registro_senales_prospectivas_walmex.csv` y `registro_senales_prospectivas_panel_g2.csv`.
- Tareas a desarrollar:
  - Crear la función `cargar_senales_ia()` para consolidar las señales de 1ª y 2ª generación.
  - Diseñar la Vista 2 con los siguientes componentes:
    - Selector de Emisora (WALMEX, GMEXICO, GFNORTE, AMX).
    - Visualizador de Consenso en Semáforo:
      - Verde Brillante: `CONSENSO_ALTO_SUBIDA` o `CONSENSO_PANEL_G2_SUBIDA`.
      - Rojo: `CONSENSO_ALTO_NO_SUBIDA` o `CONSENSO_PANEL_G2_NO_SUBIDA`.
      - Ámbar / Alerta: `DIVERGENCIA_ALERTA` (cuando el modelo lineal discrepa del Random Forest).
    - Gráfico de barras horizontales comparativo: Probabilidad de subida estimada por cada algoritmo (G1: Logística Base, Híbrido Dividendos, Random Forest; G2: Calibrado, Zona Neutral, Alta Discriminación).
    - Explicador del Factor Clave: Tarjeta explicativa con la variable de retorno relativo (`ret_10_rel_panel`), ilustrando si la acción está sobreextendida al alza o en zona de rebote estadístico por sobreventa.

### Desarrollador 3: Auditoría Temporal ($t+1$ a $t+5$) y Gobernanza AWS
- Archivos a su cargo: `modulos/vista3_auditoria_rendimiento.py` y soporte en `app.py`.
- Insumos de datos principales: `registro_senales_prospectivas_panel_g2.csv` y `serie_ppp_walmex_prospectiva.csv`.
- Tareas a desarrollar:
  - Diseñar la Vista 3 (Auditoría de Rendimiento en Vivo):
    - Gráfico temporal de líneas (usando Plotly o Altair): Evolución del precio PPP desde la sesión base $t_0$ hasta la sesión actual ($t+1, t+2$), proyectando hacia la fecha objetivo $t+5$.
    - Marcador dinámico de efectividad: Badge con `acierto_parcial_en_curso = True` (Verde: la predicción va ganando en tiempo real) o `False` (Rojo: la predicción va perdiendo).
    - Porcentaje de retorno acumulado en tiempo real frente al precio base (`retorno_parcial_pct`).
  - Diseñar la sección de Gobernanza Big Data y Nube:
    - Diagrama interactivo de la arquitectura AWS (Bronze: HTML crudo $\rightarrow$ Silver: CSVs curados $\rightarrow$ Gold: Señales IA $\rightarrow$ Amazon Athena).
    - Demostrador del contrato de validación: Indicador de que los 57/57 tests unitarios garantizan cero fuga de información temporal (*lookahead bias*).

---

## 3. Asignación del Compañero de Documentación

### Compañero 4: Documentación Técnica y Memoria de Estadía
- Insumos a su disposición:
  - Código fuente y docstrings de `metodologia_ppp.py`, `sistema_nucleo_walmex_prospectivo.py`, `etapa10_ejecutor_diario.py`, `monitor_prospectivo_segunda_generacion.py`.
  - Reportes de experimentación en `experimentos_avanzados_entrenamiento/reporte.json`.
  - Suite de pruebas de integridad: `test_evaluacion_ppp.py`, `test_monitor_prospectivo_segunda_generacion.py`, etc.
- Estructura obligatoria del Documento Final:
  - Capítulo 1: Introducción y Contexto del Negocio Bursátil en México.
    - Por qué predecir la dirección a 5 sesiones del Precio Promedio Ponderado (`PPP`) oficial de la BMV.
    - Diferencia crítica entre el PPP (promedio volumétrico regulado) y el precio de último hecho (manipulable por baja liquidez).
  - Capítulo 2: Gobernanza de Datos y Arquitectura de Big Data.
    - El principio de cero imputación sintética: por qué los días sin cotización se conservan como huecos documentados en lugar de inventar valores.
    - Trazabilidad criptográfica SHA-256 de cada boletín HTML.
    - Arquitectura Medallion en la nube (AWS S3 Bronze/Silver/Gold, Lambda serverless, EventBridge y Amazon Athena).
  - Capítulo 3: Metodología de Machine Learning (1ª y 2ª Generación).
    - Formulación matemática del target direccional: $Y_t = \mathbb{I}(\text{PPP}_{t+5} > \text{PPP}_t)$.
    - Features de 1ª generación (técnicos individuales) vs 2ª generación (retornos relativos de panel multiemisora: `ret_10_rel_panel`).
    - Algoritmos implementados: Regresión Logística regularizada ($L_2$), Random Forest y modelos de zona neutral ($\tau$).
    - Esquema de validación purgada sin fuga temporal (*Purged Walk-Forward*).
  - Capítulo 4: Resultados Empíricos y Monitoreo Prospectivo.
    - Comparativa de métricas históricas de desarrollo (Brier Score, Log-Loss, Acierto Direccional, AUC).
    - Evaluación de las señales vivas emitidas el 28, 29 y 30 de octubre de 2026 (análisis de casos de éxito como GFNORTE 100% acertado y el rally de WALMEX).
  - Capítulo 5: Manual de Operación y Reproducibilidad.
    - Pasos para correr la suite de pruebas (57/57 tests OK).
    - Pasos para iniciar el dashboard interactivo de Streamlit.
    - Consultas analíticas SQL en Amazon Athena.

---

## 4. Diccionario de Datos Rápido (Contrato de Datos Sin Ambigüedades)

### Insumo 1: `monitoreo_ppp_multiemisora_en_vivo.csv`
- `fecha`: Fecha de la sesión bursátil (formato YYYY-MM-DD).
- `emisora`: Clave de cotización oficial (ej. WALMEX, GMEXICO, GFNORTE, AMX, etc.).
- `serie`: Serie accionaria oficial (ej. *, B, O, A, CPO).
- `ppp_bmv_mxn`: Precio Promedio Ponderado oficial en pesos mexicanos (puede ser nulo si no cotizó).
- `variacion_ppp_vs_anterior_pct`: Rendimiento porcentual respecto a la sesión previa.
- `estado_captura`: `PPP_PUBLICADO_VERIFICADO` (si cotizó) o `NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA` (si estuvo ausente).
- `sha256_boletin`: Firma criptográfica del boletín HTML del cual se extrajo.

### Insumo 2: `registro_senales_prospectivas_walmex.csv`
- `fecha_senal`: Fecha en que el modelo emitió el pronóstico.
- `fecha_objetivo_h5`: Fecha exacta de maduración (5 sesiones hábiles posteriores en calendario BMV).
- `algoritmo`: Nombre del modelo (Logística Base, Retador Dividendos, Random Forest).
- `ppp_base_mxn`: Precio al momento de emitir la señal.
- `prob_subida_pct`: Probabilidad estimada de que el precio suba (0% a 100%).
- `prediccion_etiqueta`: `SUBIDA` (si prob > 50%) o `NO_SUBIDA` (si prob <= 50%).
- `estado_consenso`: `CONSENSO_ALTO_SUBIDA`, `CONSENSO_ALTO_NO_SUBIDA` o `DIVERGENCIA_ALERTA`.

### Insumo 3: `registro_senales_prospectivas_panel_g2.csv`
- `emisora`: Emisora del panel (AMX, GFNORTE, GMEXICO, WALMEX).
- `modelo_g2`: Clave del modelo (`G2_V1_POOLED_REL3_CALIBRADO`, `G2_V2_POOLED_REL3_ZONA_NEUTRAL`, `G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO`).
- `ppp_base_t`: Precio PPP base al momento de la señal.
- `ret_10_rel_panel`: Rendimiento a 10 días de la emisora menos el promedio de las 4 emisoras del panel.
- `probabilidad_subida`: Probabilidad calibrada en rango [0.0, 1.0].
- `estado_consenso_g2`: Consenso del panel para la emisora (`CONSENSO_PANEL_G2_SUBIDA` o `CONSENSO_PANEL_G2_NO_SUBIDA`).
- `sesiones_transcurridas`: Número de sesiones transcurridas desde la emisión ($t+1, t+2$).
- `ppp_parcial_reciente`: Precio observado en la sesión más reciente.
- `retorno_parcial_pct`: Rendimiento observado en curso desde la señal base.
- `acierto_parcial_en_curso`: `True` si la dirección actual coincide con la predicción; `False` si va perdiendo.
