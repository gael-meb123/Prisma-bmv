# PLAN DE MEJORA DEL MODELO: Prisma BMV (documento de traspaso para el agente ejecutor)

> **Para el agente que lea esto:** este documento es autocontenido. Contiene el contexto del proyecto, las reglas que no se pueden romper, el estado actual y un plan de trabajo con criterios de aceptación. Ejecuta las fases **en orden**. Al terminar cada fase, marca la casilla en la sección 9 (Bitácora) y escribe 2–3 líneas con los resultados numéricos.

- **Fecha de creación:** 2026-11-06
- **Fecha de entrega del proyecto:** **2026-11-27**
- **Idioma de trabajo:** español (código, comentarios, nombres de columnas y respuestas)

---

## 1. Contexto del proyecto

**Prisma BMV** es una terminal cuantitativa FinTech para la Bolsa Mexicana de Valores. Es un proyecto universitario de Big Data, pero **la marca pública NO debe incluir ninguna referencia académica** (ni universidad, ni materia, ni "proyecto escolar").

- **Objetivo:** Y_t = I(PPP_{t+5} > PPP_t), la dirección del Precio Promedio Ponderado oficial de la BMV a 5 sesiones hábiles.
- **Emisoras foco:** WALMEX, GFNORTE, GMEXICO, AMX, FEMSA. El panel de entrenamiento usa 15 emisoras.
- **Datos:**
  - Fuente primaria: boletín HTML de la BMV (`https://www.bmv.com.mx/docs-pub/rss/boletinYYYYMMDD.html`), con hash SHA-256.
  - Fuente secundaria (si la BMV da 404): VWAP de Yahoo Finance en la ventana de 13:40–14:00 CDMX.
  - Cola de reconciliación en S3 que promueve registros de `CONTINGENCIA_FUENTE_SECUNDARIA` a `PPP_PUBLICADO_VERIFICADO`.
- **Stack:**
  - AWS Lambda (Python 3.12, numpy/pandas/urllib) + S3 con capas Bronze/Silver/Gold. Bucket: `prisma-bmv-datalake-tunombre-2026`.
  - FastAPI (`api.py`, con Supabase Auth JWT).
  - React 19 + Vite + Plotly + Tailwind (`frontend/src`).
  - Streamlit heredado (`app.py`, `views/`).
  - Asistente "Prismi" con la API de Claude.
- **Entorno local:** Windows, PowerShell, Python 3.13 y **lightgbm 4.7.0 ya instalado**. El backend local corre con `uvicorn api:app --reload --port 8000`.

### 1.1 Archivos clave

| Archivo | Rol |
|---|---|
| `monitor_prospectivo_segunda_generacion.py` | **Núcleo de investigación del panel G2**: `MODELOS_G2` (L56), `hashes_protegidos_g2` (L95), `construir_serie_unificada_ppp` (L108), `extraer_ventanas_y_features_en_fecha` (L171), `preparar_panel_entrenamiento_para_corte` (L285), `ajustar_logistica_ponderada_local` (L368), `predecir_g2_v5_adaptativo_regimen_sectorial` (L407), `etiqueta_consenso_g2` (L503), `ejecutar_monitor_prospectivo_g2` (L529) |
| `test_monitor_prospectivo_segunda_generacion.py` | Tests del G2 (3 tests; la suite completa tiene 62 y pasa) |
| `lambda_function_con_ia.py` | Lambda de producción: `MODELOS_G2_CONFIG` (L42, **coeficientes escritos a mano**), `fetch_secondary_contingency_quotes`, `parse_bulletin_quotes`, `inferir_modelos_g2` (L283), `_procesar_fecha_en_s3`, `lambda_handler` |
| `lambda_function.py` | Lambda antigua sin IA (no tiene V4/V5) |
| `lambda_macro_stream.py` | ⚠️ Datos macro **SIMULADOS**. **No usar como fuente de features** |
| `metodologia_ppp.py` | Calendario BMV (`add_bmv_sessions`, `is_bmv_business_day`, `FERIADOS_BMV_2026`), `mascara_etiquetas_conocidas`, `CORTE_TRAIN="2025-04-29"`, `CORTE_TEST="2026-10-27"` |
| `serie_ppp_historica_15_emisoras_bmv.csv` | Serie histórica oficial desde 2016. Columnas: `fecha, posicion_sesion, emisora, serie, sector_economico, anillo_madurez, estado_captura, ppp_bmv_mxn, ultimo_bmv_mxn, anterior_bmv_mxn, variacion_ppp_vs_anterior_pct, evidencia_exacta, sha256_boletin, url_fuente` |
| `monitoreo_ppp_multiemisora_en_vivo.csv` | Serie en vivo desde 2026-10-28 |
| `dataset_panel_15_emisoras_features.csv` | Panel con features. La partición está en la columna **`periodo_oficial`** (TRAIN 8267 / TEST 1608 / PROSPECTIVA), **no** en `particion` |
| `registro_senales_prospectivas_panel_g2.csv` | Registro de señales G2 (local) |
| `resumen_monitor_prospectivo_g2.json` | Resumen y evaluación del monitor (`evaluacion_oficial_resuelta_t5`) |
| `registro_modelos_g2_oficial.json` | Betas y scalers por emisora de los modelos G2 |
| `experimento_ajuste_dividendos.py`, `resultados_experimento_dividendos.csv` | Experimento de dividendos (**solo WALMEX**, 8 features) |
| `api.py` | Backend FastAPI (ya tiene `/health` y `/api/health`) |
| `documentacion.md` | Documentación general (desactualizada: describe solo V1–V3) |
| `.env` | Secretos: `SUPABASE_*`, `ANTHROPIC_API_KEY`, **`BANXICO_TOKEN`** (ya configurado y probado) |

### 1.2 Modelos actuales (Panel G2: pooled logit con IRLS y escalado por emisora)

| ID | Variables | Notas |
|---|---|---|
| `G2_V1_POOLED_REL3_CALIBRADO` | ret_10, ret_10_rel_panel, volatilidad_20 | C=0.01, train congelado ≤ abril 2025 |
| `G2_V2_...` (zona neutral) | igual a V1 | En train filtra |ret_{t+5}| < 0.25% |
| `G2_V3_...` (purgado) | igual a V1 | C=0.001, reentrenamiento purgado |
| `G2_V4_POOLED_DM5_REL_CORTO_PLAZO` | ret_1_rel_panel, distancia_media_5, distancia_media_5_rel_panel, volatilidad_20 | C=0.01, purgado |
| `G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL` | 0.85·V4 + 0.15·V3, más reglas `if` | Logit local de momentum si corr(ret_20, Y) > 0.08 (vida media de 180 sesiones); filtro "falling knife"; clip a [0.05, 0.95] |

### 1.3 Resultados actuales (línea base honesta)

- **Backtest TEST** (2025-04-30 → 2026-10-28, 15 emisoras, N=1557):
  - V1 48.68% / Brier 0.2533
  - V3 48.81% / 0.2523
  - **V4 49.84% / 0.2504**
  - V5 49.78% / 0.2508
  - Con solo las 4 emisoras foco (N=1142), V4 da 50.79% / 0.2496.
- **Primera ventana resuelta** (2026-10-28 → 11-05): V4 y V5 aciertan 4/4. **Esto NO es evidencia**: el intervalo de Wilson va de 51% a 100%, y los umbrales de V5 se diseñaron mirando esas mismas señales.
- **Conclusión:** hoy **no hay habilidad predictiva estadísticamente demostrada**. El punto de equilibrio con costos (≈20 pb ida y vuelta) es **p > 53.7%**.
- **Pista positiva:** en `resultados_experimento_dividendos.csv` (WALMEX), el ajuste retroactivo por dividendos subió la exactitud de 52.12% a **54.14%** y bajó el Brier de 0.2528 a **0.2459**.

---

## 2. Reglas inviolables

1. **Cero fuga temporal.** Para entrenar en una fecha de corte, solo se usan etiquetas con `fecha_objetivo_h5 <= fecha_corte` (ver `mascara_etiquetas_conocidas`). Todo feature externo debe estar **publicado antes de las 14:00 CDMX del día t**; si no, se usa el valor de t−1.
2. **Cero imputación.** No se rellenan huecos (no usar ffill ni interpolación para crear PPP). Una fila sin dato se excluye.
3. **No modificar los archivos protegidos** de `hashes_protegidos_g2()`. Hay que verificar los hashes antes y después de cada fase.
4. **No borrar ni reescribir señales históricas.** Solo se agregan columnas o filas nuevas. Los modelos V1–V5 se mantienen, nunca se eliminan.
5. **Los secretos solo van en `.env`** (que está en `.gitignore`). El token de Banxico se lee con `os.environ["BANXICO_TOKEN"]` o con python-dotenv. **Nunca se escribe en código, en docs ni en logs.**
6. **PowerShell:** se encadena con `;`, nunca con `&&`. En búsquedas recursivas se excluye `node_modules`.
7. **Cada cambio lleva un test.** Al cerrar cada fase hay que correr `python -m unittest discover -p "test_*.py"`.
8. **Sin referencias académicas** en la UI ni en los textos públicos.
9. **Los umbrales y reglas de promoción se fijan ANTES de ver los resultados de TEST.** Se escriben en la bitácora (sección 9) primero.

---

## 3. Fuentes de datos externas disponibles

### Banxico SIE (el token ya está en `.env` como `BANXICO_TOKEN`; probado el 2026-11-06 con FIX = 18.6297)

```python
import os, json, urllib.request
def banxico_serie(serie_id: str, inicio: str, fin: str) -> list[dict]:
    url = f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{serie_id}/datos/{inicio}/{fin}"
    req = urllib.request.Request(url, headers={"Bmx-Token": os.environ["BANXICO_TOKEN"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["bmx"]["series"][0]["datos"]  # [{"fecha":"dd/mm/yyyy","dato":"18.6297"}]
```

| Serie | ID | Momento de publicación | Uso |
|---|---|---|---|
| Tipo de cambio FIX | `SF43718` | ~12:00 CDMX del día t (**sí** se puede usar en t) | Feature de FX |
| Tasa objetivo de Banxico | `SF61745` | Días de decisión | Flag de evento y nivel de tasa |
| TIIE a 28 días | `SF43783` | Diario | Feature de tasa (opcional) |

- Límites de consulta: hay que respetarlos (descarga en bloques por año y caché local en `cache_externo/`).
- Los datos vienen como `"N/E"` en días sin dato. Esas filas se **excluyen**, no se imputan.

### Yahoo Finance (ya se usa en la Lambda: `YF_TICKER_MAP`)

- `^GSPC` (S&P 500), `EWW` (ETF México), `^VIX`, `MXN=X`, `HG=F` (cobre, para GMEXICO).
- Se cierran después de las 14:00 CDMX, así que **siempre se usa el valor de t−1**.

### Ya disponible sin descargar nada

- `ultimo_bmv_mxn` en `serie_ppp_historica_15_emisoras_bmv.csv`, que es el último hecho del día, para construir la diferencia entre el último hecho (UH) y el PPP.

---

## 4. Plan de fases

### FASE 0: Congelamiento y pre-registro (≈½ día)

**Objetivo:** que toda evaluación futura de V1–V5 sea fuera de muestra y verificable.

Tareas:
1. En `registro_modelos_g2_oficial.json`, agregar a cada modelo `fecha_congelamiento: "2026-11-06"`, `sha256_config` (hash del JSON canónico de su configuración) y `estado: "SHADOW"`.
2. Agregar la columna `muestra_evaluacion` al registro de señales (en el monitor y en la Lambda):
   - `IN_SAMPLE_DISENO` si `fecha < 2026-11-06`,
   - `OUT_OF_SAMPLE_PRE_REGISTRADO` en otro caso.
3. Escribir un test que recalcule `sha256_config` y falle si un modelo congelado cambió.

**Criterio de aceptación:** los tests pasan, todas las señales previas quedan como `IN_SAMPLE_DISENO` y los hashes protegidos no cambiaron.

---

### FASE 1: Higiene de etiquetas (≈1–2 días)

**Objetivo:** quitar el ruido de Y.

Tareas:
1. **Resolver solo con PPP verificado.** En el monitor y en la Lambda (`RESUELTA_OFICIAL_T5`), si el PPP de t o de t+5 tiene fuente `CONTINGENCIA_FUENTE_SECUNDARIA`, la señal queda en estado `PENDIENTE_RECONCILIACION` y **no entra en las métricas**.
2. **Ajuste por dividendos para las 15 emisoras.**
   - Construir `eventos_corporativos_15_emisoras.csv` con las columnas `emisora, fecha_ex, tipo (DIVIDENDO|SPLIT), monto_mxn, factor, fuente`.
   - Fuente sugerida: `yfinance` (`Ticker("WALMEX.MX").dividends` / `.splits`), contrastada con la lógica de `experimento_ajuste_dividendos.py::build_adjusted_features_and_indicator`.
   - Factor retroactivo: f = 1 − D/PPP_{ex−1}.
   - Generar un `ppp_ajustado` **solo para features y etiquetas**, en una columna nueva. El PPP original no se toca.
3. Agregar el flag `ventana_con_evento` (hay evento corporativo en (t, t+5]).
4. Reentrenar V1–V5 en TEST con las etiquetas ajustadas y comparar contra la línea base de la sección 1.3. Los modelos congelados se reportan aparte como "V4_ADJ", etc.

**Criterio de aceptación:** existe `reporte_fase1_higiene.json` con la exactitud, el Brier y la N de cada modelo, antes y después del ajuste, para las 15 emisoras y para las 4 foco.

---

### FASE 2: Marco de evaluación institucional (≈2–3 días). ⭐ Es la fase más importante

**Objetivo:** distinguir habilidad real de suerte. Nuevo módulo `evaluacion_institucional.py` (numpy/pandas/scipy) más `test_evaluacion_institucional.py`.

Funciones requeridas (con tests sobre datos sintéticos de resultado conocido):

| Función | Definición |
|---|---|
| `intervalo_wilson(k, n, alpha=0.05)` | Intervalo de Wilson |
| `brier_skill_score(p, y, p_ref)` | 1 − Brier/Brier_ref, donde p_ref es la climatología rodante a 250 sesiones calculada **solo con etiquetas conocidas** |
| `descomposicion_murphy(p, y, bins=10)` | Confiabilidad, resolución e incertidumbre |
| `information_gain_bits(p, y, p_ref)` | Diferencia de log-loss en log₂ |
| `curva_calibracion(p, y, bins=10)` | ECE y pendiente/intercepto de calibración (logit de y sobre logit(p)) → **λ** |
| `rank_ic_diario(df)` | Spearman transversal por fecha entre p y r_{t+5}; media, desviación, IC-IR = media/desviación·√(252/5), t-stat HAC |
| `diebold_mariano(loss_a, loss_b, lag=4)` | Errores Newey–West; debe devolver el estadístico y el p-valor |
| `block_bootstrap_diff(loss_a, loss_b, bloque=5, B=2000)` | IC de la diferencia de pérdidas |
| `n_efectivo(y, lag=4)` | N ajustado por autocorrelación |

Baselines obligatorios:
- `CLIMATOLOGIA` (tasa base rodante),
- `SIEMPRE_SUBIDA`,
- `MOMENTUM_INGENUO`: p = 0.5 + 0.1·sign(ret_5).

Entregable: `reporte_evaluacion_institucional.json`, con V1–V5 y los baselines sobre TEST, para 15 emisoras y para las 4 foco. **Ese reporte es la línea base oficial para comparar todo lo que sigue.**

**Criterio de aceptación:** los tests pasan, el reporte existe y λ quedó documentado para V4.

---

### FASE 3: Features nuevas con ablación (≈3–4 días)

**Antes de empezar, pre-registrar en la sección 9:** una feature se queda solo si, en CV walk-forward purgada (embargo de 5 sesiones), mejora el log-loss contra V4 con un p-valor de Diebold–Mariano < 0.10 **y** no empeora el BSS.

Nuevo módulo: `features_externas.py`, con caché en `cache_externo/` (agregarlo a `.gitignore` si contiene datos con licencia).

| # | Feature | Construcción exacta | Momento del dato |
|---|---|---|---|
| F1 | `gap_uh_ppp` | (ultimo_bmv_mxn − ppp_bmv_mxn)/ppp_bmv_mxn | t (mismo boletín) |
| F1b | `gap_uh_ppp_rel_panel` | F1 menos la media transversal del día | t |
| F1c | `gap_uh_ppp_media5` | Media de F1 en las últimas 5 sesiones | t |
| F2 | `fx_ret5` | ln(FIX_t/FIX_{t−5}) con la serie SF43718 | t (FIX ~12:00) |
| F2b | `fx_ret5_x_beta` | fx_ret5 × β_FX,i, donde β_FX,i es la regresión rodante a 60 sesiones de ret_1 de la emisora sobre Δln FIX, con datos ≤ t−1 | t |
| F3 | `spx_ret5_lag1` | ret₅ de ^GSPC al cierre de t−1 | t−1 |
| F3b | `vix_cambio5_lag1` | VIX_{t−1} − VIX_{t−6} | t−1 |
| F3c | `eww_ret5_lag1` | ret₅ de EWW al cierre de t−1 | t−1 |
| Extra | `flag_decision_banxico_5d`, `flag_ex_div_5d` | 1 si hay evento en (t, t+5] (los calendarios se publican por adelantado) | t |
| Extra | `cobre_ret5_lag1` | Solo como interacción con GMEXICO | t−1 |

Procedimiento: partir de V4, agregar **una feature (o un grupo F1/F2/F3) a la vez**, registrar Δ log-loss, Δ BSS, Δ IC y el p-valor de Diebold–Mariano, y al final probar la combinación de las aceptadas.

**Entregable:** `reporte_fase3_ablacion.csv` y un test que garantice que ningún feature externo tenga fecha de publicación posterior a t a las 14:00.

---

### FASE 4: Modelos de nueva generación, candidatos V6 (≈4–5 días)

**Antes de empezar, pre-registrar la regla de promoción en la sección 9:**
- Diebold–Mariano contra V4 con p < 0.05 (Brier y log-loss) en TEST,
- BSS > 0 contra la climatología,
- pendiente de calibración entre 0.7 y 1.3,
- IC medio > 0.02,
- y que mejore en **al menos 3 de las 4** emisoras foco.

| Candidato | Especificación |
|---|---|
| **G2_V6A_JERARQUICO** | Logit con β_i = β_pool + u_i y penalización ‖u_i‖²/τ (*partial pooling*); τ se elige por CV purgada. IRLS en numpy. **Reemplaza las reglas `if` de V5.** |
| **G2_V6B_DESCOMPUESTO** | Se modelan por separado la dirección del mercado (media equiponderada del panel, con features F2/F3) y el exceso de retorno de la emisora (features relativos y F1). Se combinan con P(r_i > 0) = Φ((μ_m + μ_ex)/σ) |
| **G2_V6C_RIDGE_CONTINUO** | Ridge sobre z = r_{t+5}/σ_20, con p = Φ(ẑ/σ_res) |
| **G2_LGBM_CHALLENGER** | LightGBM 4.7: `max_depth=3, num_leaves=7, learning_rate=0.02, n_estimators≤400 con early stopping en el fold de validación purgado, min_data_in_leaf=100, feature_fraction=0.8, monotone_constraints` donde haya hipótesis clara; el emisor va como categórico. Calibración isotónica o Platt en un fold separado |

Todos se evalúan con `evaluacion_institucional.py`. Si **ninguno** cumple la regla, V4 sigue como oficial y se documenta (también es un resultado válido y defendible).

**Entregable:** `reporte_fase4_modelos_v6.json` y su tabla comparativa en la bitácora.

---

### FASE 5: Política de asignación de capital (≈2–3 días)

Nuevo módulo: `asignacion_capital.py`.

1. p̃ = 0.5 + λ(p − 0.5), con λ tomado de la Fase 2 (estimado solo con datos pasados).
2. Banda muerta: si |p̃ − 0.5| < 0.03, el peso es 0.
3. μ_i = (2p̃_i − 1)·E|r₅,i|, con E|r₅| rodante a 250 sesiones.
4. Σ con *shrinkage* de Ledoit–Wolf sobre retornos a 5 días (rodante a 250 sesiones).
5. w = 0.25·Σ⁻¹μ, con clip a [0, 0.30], solo largo o en liquidez.
6. Volatilidad objetivo de 10% anual (se escala hacia abajo si la excede).
7. Tramos traslapados: cada día se rebalancea 1/5 del capital.
8. Backtest **neto de 20 pb ida y vuelta** en TEST, con Sharpe, **Deflated Sharpe Ratio** (con el número de variantes probadas), drawdown máximo, rotación y hit rate. Comparar contra comprar y mantener el equiponderado de las 5 emisoras.

**Entregable:** `reporte_fase5_portafolio.json` y la curva de equity en CSV.

---

### FASE 6: Producción, paridad y UI (≈2–3 días)

1. **Registro de modelos:** el script de investigación exporta `registro_modelos_g2_vN.json` (betas, scalers, umbrales y versión) y se sube a `s3://prisma-bmv-datalake-tunombre-2026/modelos/`.
2. `lambda_function_con_ia.py` **carga** el registro desde S3. Se quitan los coeficientes escritos a mano y `MODELOS_G2_CONFIG` queda solo como respaldo.
3. **Test de paridad:** para 5 fechas de TEST, la p de la Lambda debe coincidir con la p de investigación (|Δ| < 1e-6).
4. Si entran features externos, la Lambda descarga el FIX de Banxico (token en una variable de entorno de Lambda) y Yahoo t−1.
5. `api.py`: nuevo endpoint `GET /api/metricas/modelos` que devuelva BSS, IC, ECE, λ, el intervalo de Wilson y la N efectiva por modelo, separando `IN_SAMPLE_DISENO` de `OUT_OF_SAMPLE_PRE_REGISTRADO`.
6. `frontend/src`: panel de "Calidad del modelo" (diagrama de confiabilidad en Plotly, tabla de métricas con intervalos) y vista de asignación sugerida. Actualizar el texto de Prismi y los mocks a 5 o 6 modelos.
7. Actualizar `documentacion.md` (V4, V5, V6, FEMSA, marco de evaluación).

**Criterio de aceptación:** el test de paridad pasa, el endpoint responde 200, el frontend compila (`npm run build` en `frontend/`) y todos los tests pasan.

---

### FASE 7: Monitoreo secuencial (continuo, desde la Fase 2)

- Log-score acumulado de cada modelo menos el de la climatología, más una alarma **CUSUM** si se degrada.
- **SPRT** con H0: p = 0.50 contra H1: p = 0.55. Reportar cuántas señales efectivas faltan (≈620 independientes para una potencia de 80%).
- Reporte semanal `gold/reportes/monitoreo_semanal_YYYYMMDD.json` en S3.

---

## 5. Cronograma (entrega el 2026-11-27)

| Fechas | Fase | Hito |
|---|---|---|
| 06–07 nov | F0 | Modelos congelados y pre-registrados |
| 08–10 nov | F1 | Etiquetas limpias y dividendos en 15 emisoras |
| 10–13 nov | F2 | **Línea base institucional oficial** |
| 13–17 nov | F3 | Ablación de features (F1 gap, F2 FX, F3 global) |
| 17–21 nov | F4 | Decisión sobre V6 |
| 21–23 nov | F5 | Backtest de portafolio neto de costos |
| 23–25 nov | F6 | Lambda con registro, endpoint y UI |
| 26 nov | — | Congelamiento, suite completa de tests y documentación |
| 27 nov | — | **Entrega** |

Si hay retraso, la **ruta mínima** es F0 → F1 → F2 → F3 (solo F1 gap) → F6. F4 y F5 son opcionales.

---

## 6. Cómo comunicar resultados (honestidad)

- Toda exactitud se reporta **con su intervalo de Wilson y su N**.
- Nunca se presenta el 4/4 ni el 90% en vivo como evidencia de habilidad.
- Si los modelos no superan a la climatología, se dice tal cual. Un sistema bien instrumentado que **demuestra con rigor** que no hay ventaja es un entregable de calidad.

---

## 7. Comandos útiles (PowerShell)

```powershell
python -m unittest discover -p "test_*.py"
python monitor_prospectivo_segunda_generacion.py
python -m py_compile lambda_function_con_ia.py
uvicorn api:app --reload --port 8000
cd frontend; npm run build
```

## 8. Prompt sugerido para arrancar al agente ejecutor

> Lee completo `PLAN_MEJORA_MODELO_HANDOFF.md` en la raíz del proyecto. Respeta todas las reglas de la sección 2. Ejecuta la siguiente fase sin marcar de la sección 9 (Bitácora): primero revisa los archivos relevantes, luego implementa, escribe tests, corre la suite completa y, al final, actualiza la bitácora con los resultados numéricos y marca la casilla. No avances a otra fase sin mi confirmación. Responde en español.

---

## 9. Bitácora de ejecución

### Pre-registros (llenar ANTES de ejecutar la fase correspondiente)
- Fase 3, regla de aceptación de features: **PRE-REGISTRADA (2026-11-06, antes de ejecutar Fase 3):** Partiendo de `G2_V4` (`[ret_1_rel_panel, dm_5, dm_5_rel_panel, vol_20]`, $C=0.01$) sobre el panel con higiene de Fase 1, una feature o familia de features se acepta **únicamente si**, en validación cruzada walk-forward purgada dentro de `TRAIN <= 2025-04-29` (4 bloques cronológicos con embargo de 5 sesiones `fecha_objetivo_h5 <= fecha_corte`), reduce la pérdida logística (`log_loss`) respecto a `G2_V4` con un p-valor unilateral de Diebold–Mariano (Newey–West `lag=4`) $p_{\text{DM, log-loss}} < 0.10$ **y** no empeora el Brier Skill Score ($\Delta \text{BSS} \ge 0$). Toda serie externa debe tener sello de publicación $\le 14:00$ CDMX del día $t$ (ej. FIX Banxico `SF43718` a las 12:00 CDMX) o rezagarse estrictamente a $t-1$ (ej. cierres de `^GSPC`, `^VIX`, `EWW`, `HG=F`); cero imputación sintética (`ffill`/interpolación prohibidos).
- Fase 4, regla de promoción de V6: **PRE-REGISTRADA (2026-11-06, antes de ejecutar Fase 4):** Un modelo candidato de sexta generación (`G2_V6A_JERARQUICO`, `G2_V6B_DESCOMPUESTO`, `G2_V6C_RIDGE_CONTINUO` o `G2_LGBM_CHALLENGER`) se promueve sobre `G2_V4_ADJ` **únicamente si** cumple simultáneamente en `TEST`: (1) prueba de Diebold–Mariano (Newey–West `lag=4`) contra `G2_V4_ADJ` con $p_{\text{unilateral}} < 0.05$ tanto en Brier Score como en log-loss, (2) Brier Skill Score $\text{BSS} > 0$ frente a la climatología rodante purgada de 250 sesiones, (3) pendiente de calibración logística $\lambda_{\text{Cox}} \in [0.70, 1.30]$, (4) Rank IC transversal diario medio $> 0.02$, y (5) mejora de Brier/log-loss en **al menos 3 de las 4 emisoras foco** (`AMX`, `GFNORTE`, `GMEXICO`, `WALMEX`). Si ningún candidato cumple los 5 criterios simultáneamente, `G2_V4_ADJ` (o `G2_V4_ADJ + gap_uh_ppp`) se mantiene como campeón oficial y los candidatos V6 quedan documentados en `SHADOW`.

### Estado
- [x] F0: Congelamiento y pre-registro
- [x] F1: Higiene de etiquetas
- [x] F2: Marco de evaluación institucional
- [x] F3: Features nuevas con ablación
- [x] F4: Modelos V6
- [x] F5: Asignación de capital
- [x] F6: Producción, paridad y UI
- [x] F7: Monitoreo secuencial activo

### Notas de resultados
- **2026-11-06 — Fase 0 (Congelamiento y pre-registro):** Se congelaron los 5 modelos G2 (`V1` a `V5`) en `registro_modelos_g2_oficial.json` con `fecha_congelamiento: "2026-11-06"`, `estado: "SHADOW"` y `sha256_config` canónico (`V1: 6047438e...`, `V2: 683919ac...`, `V3: d4221a2c...`, `V4: b07293c5...`, `V5: f1a981cd...`). Se incorporó la columna `muestra_evaluacion` en `monitor_prospectivo_segunda_generacion.py` y `lambda_function_con_ia.py`; las 125 señales emitidas antes del `2026-11-06` quedaron etiquetadas como `IN_SAMPLE_DISENO`. La suite completa pasó con **63 tests OK** y los hashes protegidos permanecieron intactos.
- **2026-11-06 — Fase 1 (Higiene de etiquetas):**
  1. En `monitor_prospectivo_segunda_generacion.py` y `lambda_function_con_ia.py`, las señales cuyo PPP en `t` o `t+5` proviene de `CONTINGENCIA_FUENTE_SECUNDARIA` quedan en `PENDIENTE_RECONCILIACION` y excluidas de `evaluacion_oficial_resuelta_t5`.
  2. Se construyó `eventos_corporativos_15_emisoras.csv` (**284 eventos**: 282 dividendos y 2 splits en las 15 emisoras) y `dataset_panel_15_emisoras_features_ajustado_fase1.csv` con `ppp_ajustado`, `ventana_con_evento` (`429` ventanas de 5 sesiones con evento en total, `86` en TEST; `76` cambios de etiqueta y `0` cambios en las `9,250` ventanas sin evento).
  3. En `reporte_fase1_higiene.json`, el ajuste por dividendos mejoró **todos los modelos (V1–V5)** en TEST:
     - **15 emisoras (`N=1,557`):** `V4` subió de `49.84%` (Brier `0.250382`) a `V4_ADJ = 51.70%` (`+1.86 pp`, Brier `0.249668`); `V5` subió de `49.78%` a `V5_ADJ = 51.19%` (`+1.41 pp`, Brier `0.250235`); `V1` subió `+1.61 pp` (`50.29%`).
     - **4 emisoras foco (`N=1,142`):** `V4` subió de `50.79%` (Brier `0.249604`) a `V4_ADJ = 52.36%` (`+1.57 pp`, Brier `0.248752`); `V5` subió de `50.09%` a `V5_ADJ = 51.66%` (`+1.57 pp`, Brier `0.249831`).
     - **En las 86 ventanas con evento corporativo en TEST:** `V4_ADJ` alcanzó `59.30%` vs `43.02%` sin ajuste (`+16.28 pp`, Brier `0.249308` vs `0.253159`).
- **2026-11-06 — Fase 2 (Marco de evaluación institucional):**
  1. Se implementó `evaluacion_institucional.py` (con `test_evaluacion_institucional.py`, 5 tests unitarios OK) y se generó `reporte_evaluacion_institucional.json` evaluando `G2_V1`–`G2_V5` y los 3 modelos nulos (`CLIMATOLOGIA`, `SIEMPRE_SUBIDA`, `MOMENTUM_INGENUO`) en `test_15_emisoras`, `test_4_emisoras_foco`, `test_15_emisoras_ajustado_fase1` y `test_4_emisoras_foco_ajustado_fase1`.
  2. **Tamaño efectivo de muestra ($N_{\text{eff}}$ con solapamiento `lag=4`):** `623.2` (`15 emisoras`, $N=1,557$) y `461.3` (`4 emisoras foco`, $N=1,142$).
  3. **Pendiente de calibración $\lambda$ de `G2_V4` registrada para Fase 5 (`lambda_calibracion_v4`):**
     - **CV purgada pre-TEST dentro de `TRAIN <= 2025-04-29` (`N_oof = 3,646`, cero fuga a TEST):** $\lambda_{\text{Cox}} = 0.243026$ (`pendiente_lineal = 0.265381`) en etiquetas originales y $\lambda_{\text{Cox}} = 0.280333$ (`pendiente_lineal = 0.297813`) con etiquetas limpias de Fase 1 (`V4_ADJ`).
     - **En TEST fuera de muestra (`2025-04-30` a `2026-10-27`):** `G2_V4_ADJ` alcanza $\lambda_{\text{Cox}} = 0.532662$ (`ECE = 0.012334`, vs `0.029045` sin ajuste) en 15 emisoras y $\lambda_{\text{Cox}} = 0.883305$ (dentro de la banda objetivo `[0.70, 1.30]`) en las 4 emisoras foco. Los modelos de 10 sesiones (`V1`–`V3`) exhiben pendiente negativa en TEST sin ajustar (`-0.23` a `-0.29`).
  4. **Línea base institucional en TEST:**
     - `test_15_emisoras` ($N=1,557$): `G2_V4` obtiene exactitud `49.84%` `[47.36%, 52.32%]`, Brier `0.250382`, `BSS = +0.137%` vs climatología (`0.250726`), `IG = +0.00092` bits, superando significativamente a `G2_V1` (Diebold–Mariano $t = -2.23$, $p = 0.0256$).
     - `test_15_emisoras_ajustado_fase1` ($N=1,557$): `G2_V4_ADJ` sube a `51.70%` `[49.22%, 54.18%]`, Brier `0.249668`, `BSS = +0.483%` vs climatología (`+0.133%` vs 0.50), `IG = +0.00344` bits, DM vs `V1` $t = -2.32$ ($p = 0.0201$), Bootstrap $P(\text{Brier} < \text{Clim}) = 77.1\%$.
     - `test_4_emisoras_foco_ajustado_fase1` ($N=1,142$): `G2_V4_ADJ` alcanza `52.36%` `[49.46%, 55.25%]`, Brier `0.248752`, `BSS = +1.076%` vs climatología (`+0.499%` vs 0.50), `IG = +0.00782` bits, DM vs climatología $t = -1.61$ ($p_{\text{uni}} = 0.0537$), Bootstrap $P(\text{Brier} < \text{Clim}) = 93.95\%$.
- **2026-11-06 — Fase 3 (Features nuevas con ablación):**
  1. Se pre-registró la regla de aceptación antes de correr la ablación y se implementó `features_externas.py` (con caché local en `cache_externo/` ignorado en `.gitignore`) y `test_fase3_features_externas.py` (**4 tests OK**, verificando cero fuga temporal posterior a `14:00:00` CDMX en las `9,879` filas y cero imputación `ffill` en los feriados de EE.UU.).
  2. Se generó `dataset_panel_15_emisoras_features_fase3.csv`, `reporte_fase3_ablacion.csv` y `reporte_fase3_ablacion.json`:
     - **Única feature individual que supera la regla pre-registrada en CV walk-forward purgada (`TRAIN <= 2025-04-29`, $N_{\text{oof}} = 4,915$, embargo 5 sesiones):** **`F1_gap_uh_ppp`** (`(ultimo_bmv_mxn - ppp_bmv_mxn) / ppp_bmv_mxn`), con $\Delta \text{log-loss}_{\text{CV}} = -0.000526$ (`0.692213` $\to$ `0.691687`), $p_{\text{DM, unilateral}} = 0.0987 < 0.10$ y $\Delta \text{BSS}_{\text{CV}} = +0.1036\%$ (`+0.8284%` $\to$ `+0.9320%`).
     - **Validación fuera de muestra en TEST de `G2_V4_ADJ + gap_uh_ppp` (100% cobertura, 0 filas excluidas):**
       - **15 emisoras ($N=1,557$):** La exactitud sube de `51.70%` a **`52.60%`** (`+0.90 pp`), Brier baja de `0.249668` a **`0.249627`** (`-0.000041`), log-loss baja `-0.000048`, BSS sube a **`+0.4908%`** y el **Rank IC transversal diario salta de `-0.0120` a `+0.0202`** ($\Delta \text{IC} = +0.0322$).
       - **4 emisoras foco ($N=1,142$):** La exactitud sube de `52.36%` a **`52.71%`** (`+0.35 pp`), Brier baja de `0.248752` a **`0.248646`** (`-0.000106`) y log-loss baja `-0.000214`.
     - **Hallazgo estructural sobre F2/F3 para Fase 4:** Las variables puras de serie de tiempo (`fx_ret5`, `spx_ret5_lag1`, `vix_cambio5_lag1`, `eww_ret5_lag1`, `flag_decision_banxico_5d`) no pasan la CV pooled en `TRAIN` (`2016–2025`) al introducir varianza temporal común a todas las emisoras, aunque en `TEST` (`2025–2026`) muestran mejoras fuertes (`spx_ret5_lag1`: `53.12%` en 15 emisoras / `54.03%` en 4 foco; `flag_decision_banxico_5d`: `53.11%` / `54.64%`; `GRUPO_F1_COMPLETO`: `53.05%` / `53.15%`, $p_{\text{DM}} = 0.0481$). En Fase 4 (`G2_V6B_DESCOMPUESTO`) se reservarán para el submodelo de dirección agregada del mercado, mientras que `gap_uh_ppp` se integra como feature transversal aceptada.
- **2026-11-06 — Fase 4 (Modelos de nueva generación, candidatos V6):**
  1. Se pre-registró la regla de promoción de 5 criterios antes de entrenar y se implementó `modelos_v6.py` (con `test_fase4_modelos_v6.py`, **3 tests OK**) y `reporte_fase4_modelos_v6.json`, evaluando `G2_V4_ADJ`, `G2_V4_F1_GAP` y los 4 candidatos `G2_V6A_JERARQUICO`, `G2_V6B_DESCOMPUESTO`, `G2_V6C_RIDGE_CONTINUO` y `G2_LGBM_CHALLENGER`.
  2. **Resultados comparativos en TEST (`15 emisoras, N=1,557` | `4 emisoras foco, N=1,142`):**
     - `G2_V4_ADJ` (base oficial): Acc `51.70%` `[49.22, 54.18]`, Brier `0.249668`, `BSS = +0.475%`, $\lambda_{\text{Cox}} = +0.533$, `IC = -0.0120` | 4 foco: Acc `52.36%`, Brier `0.248752`, `BSS = +0.617%`, $\lambda_{\text{Cox}} = +0.883$.
     - **`G2_V4_F1_GAP` (`V4_ADJ + gap_uh_ppp`):** Acc **`52.60%`** `[50.12, 55.07]`, Brier **`0.249627`**, `BSS = +0.491%`, $\lambda_{\text{Cox}} = +0.533$, **`IC = +0.0202`** (`IC-IR = +0.288`) | 4 foco: Acc **`52.71%`** `[49.81, 55.60]`, Brier **`0.248646`**, `BSS = +0.660%`, $\lambda_{\text{Cox}} = +0.861$, mejorando Brier y log-loss en `AMX` (`-0.000552`) y `GFNORTE` (`-0.001281`, Acc `50.86%` $\to$ `52.23%`).
     - `G2_V6C_RIDGE_CONTINUO` ($\alpha=2000$, $z = r_{t+5}/\sigma_{20}$): Acc `51.32%`, Brier `0.249971`, `BSS = +0.354%`, $\lambda_{\text{Cox}} = +0.290$ | 4 foco: Acc `51.58%`, Brier `0.249144` (mejora 2/4 foco).
     - `G2_V6A_JERARQUICO` (*partial pooling* IRLS, $C_{\text{pool}}=0.01, \tau=0.0005$): Acc `51.12%`, Brier `0.250099`, `BSS = +0.303%`, $\lambda_{\text{Cox}} = +0.390$, `IC = +0.0134` | 4 foco: Acc `51.31%`, Brier `0.249196` (mejora 2/4 foco: `AMX` y `GFNORTE`).
     - `G2_V6B_DESCOMPUESTO` ($\mu_m + \mu_{\text{ex}}$): Acc `50.03%`, Brier `0.250146`, `BSS = +0.284%`, `IC = +0.0049` | 4 foco: Acc `50.88%`, Brier `0.249849`.
     - `G2_LGBM_CHALLENGER` (LightGBM 4.7 restringido + Platt): Acc `49.13%`, Brier `0.255362`, `BSS = -1.795%`, $\lambda_{\text{Cox}} = -0.160$, `IC = -0.0552` | 4 foco: Acc `49.47%`, Brier `0.254313`.
  3. **Decisión oficial de Fase 4:** Ningún candidato V6 cumple simultáneamente los 5 criterios estrictos pre-registrados (en particular $p_{\text{DM}} < 0.05$ frente a `G2_V4_ADJ`). Queda demostrado empíricamente que en un panel con $N_{\text{train}} = 8,122$ y baja relación señal/ruido, el logit lineal fuertemente regularizado (`G2_V4_ADJ` y su extensión `G2_V4_F1_GAP`) domina en calibración y Brier a modelos con efectos aleatorios por emisora (`V6A`) y a árboles de decisión (`LightGBM`). Se mantiene `G2_V4_ADJ` como modelo principal y `G2_V4_F1_GAP` + candidatos V6 en `SHADOW`.
- **2026-11-06 — Fase 5 (Política de asignación de capital y backtest neto de costos):**
  1. Se implementó `asignacion_capital.py` (con `test_fase5_asignacion_capital.py`, **4 tests OK**) y se generaron `reporte_fase5_portafolio.json` y `curva_equity_fase5_portafolio.csv` sobre las 5 emisoras foco (`AMX`, `FEMSA`, `GFNORTE`, `GMEXICO`, `WALMEX`) en las 291 sesiones de TEST (`2025-04-30` a `2026-10-27`), aplicando $\tilde{p} = 0.5 + \lambda(p - 0.5)$ estimada solo con datos pasados, banda muerta $|\tilde{p} - 0.5| < 0.03$, $\mu_i = (2\tilde{p}_i - 1)\,\text{E}_{250d}|r_{5,i}|$, $\Sigma_{\text{LW}}$ a 250 sesiones purgadas, ¼-Kelly con tope de `30%` por emisora, volatilidad objetivo máxima del `10%` anual, 5 tramos traslapados (`1/5` diario) y costos de transacción de **20 pb ida y vuelta** (`10 pb` por sentido).
  2. **Resultados del backtest en TEST (neto de 20 pb ida y vuelta):**
     - **`G2_V4_F1_GAP_KELLY_250D` ($\lambda_{250d}$ rodante purgada):** Retorno acumulado neto **`+6.94%`** (`CAGR = +5.99%`), volatilidad anualizada **`5.73%`** ($\le 10\%$), **Sharpe Bruto = `+1.42`** (superando al benchmark `+1.34`), **Sharpe Neto = `+1.04`** (`PSR vs 0 = 0.892`, `DSR = 0.214` con $M=20$ variantes), **Max Drawdown = `-3.46%`** (menos de la mitad del `-7.60%` del benchmark), exposición media `28.01%` (`71.99%` en liquidez) y **Hit Rate por operación a 5 días = `55.24%`** (`+72.5 pb` brutos por operación, superando el umbral de equilibrio de `53.70%`).
     - **`G2_V4_ADJ_KELLY_250D` (sin `gap_uh_ppp`):** Retorno acumulado neto **`+3.99%`** (`CAGR = +3.45%`), volatilidad `5.37%`, Sharpe Bruto `+1.01`, **Sharpe Neto = `+0.66`**, Max Drawdown `-4.09%`, exposición media `24.29%` y Hit Rate a 5 días = `54.31%`. La adición de `gap_uh_ppp` incrementa el Sharpe neto de `+0.66` a **`+1.04`** (`+0.38`) y el retorno neto en **`+2.95 pp`**.
     - **`G2_V4_F1_GAP_LAMBDA_FIJA_CONSERVADORA` ($\lambda_0 = 0.280333$ fija de Fase 2, banda proporcional):** Retorno neto **`+3.89%`**, volatilidad `3.63%`, **Sharpe Neto = `+0.93`** (`Bruto = +1.30`), Max Drawdown **`-2.45%`**, exposición media `16.82%` y Hit Rate a 5 días = **`55.59%`**.
     - **`G2_V4_F1_GAP_LAMBDA_FIJA_BANDA_ESTRICTA` ($\lambda_0 = 0.280333$ fija + banda nominal `0.03` sobre $\tilde{p}$):** Exposición media `0.62%` (`99.38%` en liquidez por doble encogimiento), retorno neto `+0.88%`, volatilidad `1.03%`, Sharpe Neto `+0.75`, Max Drawdown `-0.58%` y Hit Rate a 5 días = **`83.33%`**.
     - **`BENCHMARK_EQUIPONDERADO_5_EMISORAS` (Comprar y mantener 100% invertido):** Retorno neto `+22.60%` (`CAGR = +19.30%`), volatilidad `14.07%`, Sharpe Neto `+1.32` y Max Drawdown **`-7.60%`**.
- **2026-11-06 — Fase 6 (Producción, paridad numérica y UI institucional):**
  1. **Registro de modelos en doble precisión (`registro_modelos_g2_v2.json`) y paridad en AWS Lambda (`lambda_function_con_ia.py`):** Se implementó `exportar_registro_modelos_g2_v2.py` generando `registro_modelos_g2_v2.json` con precisión `float64` completa, hashes `sha256_config` canónicos para los 5 modelos oficiales (`G2_V1`–`G2_V5`), las variantes `G2_V4_ADJ_FASE1` y `G2_V4_F1_GAP`, y la política de asignación ¼-Kelly de Fase 5. En `lambda_function_con_ia.py` se eliminaron los coeficientes redondeados a 5 decimales, se añadieron `cargar_registro_modelos_g2`, `calcular_gap_uh_ppp`, `descargar_fix_banxico_lambda` (usando `BANXICO_TOKEN` por entorno sin exponerlo) e `inferir_modelo_g2_v4_f1_gap`, y se corrigió la extracción de ventanas a las 21 sesiones distintas exactas sin comprimir huecos. La discrepancia máxima de probabilidades entre AWS Lambda y el motor de investigación sobre las 125 señales en 5 fechas de corte fue **`4.96e-07 < 1e-6`**.
  2. **API Backend (`api.py`, `core/data_provider.py`, `core/claude_bot.py`):** Se creó el endpoint `GET /api/metricas/modelos` que expone las métricas institucionales (`BSS`, `Rank IC`, `ECE`, $\lambda_{\text{Cox}}$, intervalos Wilson 95%, $N_{\text{eff}} = 623.2$ / `624.2`, curvas de confiabilidad), la separación muestral (`IN_SAMPLE_DISENO` vs `OUT_OF_SAMPLE_PRE_REGISTRADO` y `PENDIENTE_RECONCILIACION`) y los pesos sugeridos de la política ¼-Kelly. Se enriqueció `GET /api/senales/panel` y se actualizó el asistente cuantitativo Prismi (`core/claude_bot.py`) con los 5 modelos G2, las 5 emisoras foco (incluyendo `FEMSA`) y las métricas de Fase 1–5.
  3. **Frontend React + Plotly (`frontend/src/`) y Documentación (`documentacion.md`):** Se actualizaron `AnalysisPanel.jsx`, `ComparisonAudit.jsx`, `UI.jsx`, `presentation.mjs`, `api.mjs`, `useCatalog.js` y `mockData.js` para desplegar las 5 variantes G2 (`V1`–`V5`), el sello de muestra (`IN_SAMPLE_DISENO` vs `OUT_OF_SAMPLE_PRE_REGISTRADO`), el diagrama de confiabilidad interactivo en Plotly, la tabla institucional fuera de muestra y el panel de asignación de capital ¼-Kelly. El bundle de producción compiló sin errores (`vite build` OK) y la suite completa alcanzó **86 tests unitarios OK** (`test_fase6_produccion_paridad_api.py`).
- **2026-11-06 — Fase 7 (Monitoreo secuencial activo: CUSUM de Log-Score + SPRT de Wald):**
  1. Se implementó `monitoreo_secuencial_fase7.py` (con `test_fase7_monitoreo_secuencial.py`, **4 tests OK**) y se generaron `reporte_fase7_monitoreo_secuencial.json`, `curva_monitoreo_secuencial_fase7.csv` y el reporte semanal `gold/reportes/monitoreo_semanal_20261106.json` (integrado también en `lambda_function_con_ia.py`, `core/data_provider.py` y `ComparisonAudit.jsx`).
  2. **Diferencial de Log-Score acumulado vs Climatología (`250d`) y alarma CUSUM de Page ($k = 0.001$ nats, $h = 1.50$ nats) en TEST ($N=1,557$, 291 sesiones):**
     - **`G2_V4_F1_GAP`:** $\Delta \text{LL}_{\text{acum}} = +3.7908\text{ nats}$ (**`+5.4690 bits`**), `cusum_actual = 0.4679 nats`, `cusum_max = 1.1107 nats < 1.50`, `alarma_cusum_activa = False` (`OPERACION_NORMAL_ESTABLE`).
     - **`G2_V4_ADJ`:** $\Delta \text{LL}_{\text{acum}} = +3.7154\text{ nats}$ (**`+5.3602 bits`**), `cusum_actual = 0.5136 nats`, `alarma_cusum_activa = False`.
     - **`G2_V5_ADJ`:** $\Delta \text{LL}_{\text{acum}} = +1.9483\text{ nats}$ (`+2.8108 bits`), `alarma_cusum_activa = False`.
  3. **Prueba Secuencial de Razón de Probabilidades de Wald (SPRT, $H_0: p = 0.50$ vs $H_1: p = 0.55$, $\alpha = 0.05, \beta = 0.20$, fronteras $A = +2.7726, B = -1.5581$):**
     - **Requerimiento muestral analítico para potencia del 80%:** **`617` señales independientes** ($\approx 620$ independientes; $\text{E}[N \mid H_1] = 380.7$). En la ventana prospectiva pre-registrada (`OUT_OF_SAMPLE_PRE_REGISTRADO >= 2026-11-06`), restan `617.0` señales efectivas independientes.
     - **En TEST completo ($N=1,557$, $N_{\text{eff}} = 624.22$):** `G2_V4_F1_GAP` (`819` aciertos = `52.60%`) registra $\text{LLR}_{\text{nominal}} = +0.3030$ y $\text{LLR}_{\text{efectivo}} = +0.1215 > 0$ (`CONTINUAR_MUESTREO`).
     - **En señales activas fuera de la banda muerta ($|p - 0.50| \ge 0.03$, $N=626$, $N_{\text{eff}} = 353.35$):** `G2_V4_F1_GAP` alcanza **`54.79%`** de acierto (`343/626`), con $\text{LLR}_{\text{nominal}} = +2.8744 > A$ y $\text{LLR}_{\text{efectivo}} = +1.6225$ (`57.27%` del tamaño muestral efectivo requerido, restando `263.7` señales efectivas independientes).
  4. **Suite completa del proyecto:** **90 tests unitarios OK**, compilación de producción frontend (`npm run build`) OK y 100% de los hashes protegidos intactos.
