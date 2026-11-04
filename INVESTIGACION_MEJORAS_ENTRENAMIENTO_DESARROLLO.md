# Investigación de Mejoras de Entrenamiento en Desarrollo (`TRAIN <= 2025-04-29`)

## 1. Resumen Ejecutivo y Hallazgos Principales

* **Módulo aislado implementado:** `experimentos_entrenamiento_desarrollo.py`
* **Directorio de artefactos:** `experimentos_entrenamiento_desarrollo/`
* **Pruebas unitarias de auditoría:** `test_experimentos_entrenamiento_desarrollo.py` (**51/51 pruebas unitarias en verde** en toda la suite del proyecto).
* **Alcance temporal estricto:** Exclusivamente el período de desarrollo `TRAIN` ($\le \text{2025-04-29}$), con 8,122 observaciones elegibles del panel PPP oficial de la BMV (1,167 en `GMEXICO B` con 803 predicciones externas en 12 semestres evaluables, y 1,829 en `WALMEX *` con 1,270 predicciones externas en 13 semestres evaluables). Cero uso de `TEST` o `PROSPECTIVA`.

* **Veredicto científico del Experimento 1 (Escalado Robusto + Ponderación por Magnitud de Retorno Individual):**
  * **Escalado Robusto (`E1_R_2VARS_ROBUST_UNIF`):** Empata prácticamente en `EXPANSIVA` con `StandardScaler` (`Brier = 0.248746` vs `0.248705`, mejorando `Balanced Accuracy` a `52.03%` y `ROC AUC` a `0.546469`), y supera ligeramente a `StandardScaler` bajo ventana móvil de 3 años (`MOVIL_3_ANIOS`: `0.250418` vs `0.250596`).
  * **Ponderación por Magnitud de Retorno (`E1_M_2VARS_STD_MAGWEIGHT`):** **Resultado negativo para calibración probabilística.** Ponderar la verosimilitud logística por $|\text{PPP}_{t+5}/\text{PPP}_t - 1|$ deteriora el Brier en `GMEXICO B` de `0.248705` a `0.249986` ($\Delta\text{Brier} = +0.001281$) y en `WALMEX *` de `0.246245` a `0.248206` ($\Delta\text{Brier} = +0.001960$). La razón matemática es que sobreponderar sesiones de alta magnitud infla la norma de los coeficientes $\beta$ y empuja las probabilidades lejos de la prevalencia base durante choques de volatilidad (el peor semestre en `GMEXICO B`, `2020-H2`, sube de `0.2628` a `0.2805`).

* **Veredicto científico del Experimento 2 (Entrenamiento en Panel Mancomunado *Pooled Panel* + Retorno Relativo Intrapanel):**
  * **Mejora sustancial y estadísticamente consistente (los intervalos de confianza al 95% por *bootstrap* de bloques excluyen el cero en `GMEXICO B`):**
  * **1. Retorno Relativo Intrapanel en entrenamiento individual (`E2_P1_INDIV_REL2_STD_UNIF`):** Reemplazar `ret_10` bruto por el retorno relativo a las emisoras publicadas en el boletín del mismo día (`ret_10_rel_panel`) reduce el Brier de `GMEXICO B` de `0.248705` a **`0.246297`** ($\Delta\text{Brier vs Benchmark 8 vars} = -0.004329$, mejorando en **9 de 12** semestres).
  * **2. Entrenamiento Mancomunado (*Pooled Panel*, `E2_P3_POOLED_2VARS_STD_UNIF`):** Entrenar los pesos de reversión (`ret_10`) y volatilidad (`volatilidad_20`) sobre el panel purgado (~7 veces más datos que una emisora aislada, estandarizando por emisora dentro de `Train`) reduce el Brier de `GMEXICO B` a **`0.245458`**:
    * $\Delta\text{Brier vs Benchmark 8 vars} = -0.005168$, IC95% por bloques `[-0.011157, -0.000184]` (**no incluye cero**).
    * $\Delta\text{Brier vs 2 vars individual} = -0.003247$, IC95% por bloques `[-0.005717, -0.000723]` (**no incluye cero**, gana en **9 de 12** semestres y supera al Dummy en **10 de 12** semestres).
    * Eleva el `Balanced Accuracy` a **`56.03%`** y el `ROC AUC` a **`0.579021`**.
  * **3. Combinación de *Pooled Panel* + Retorno Relativo Intrapanel (`E2_P4_POOLED_REL3_STD_UNIF` y `E2_P6_POOLED_REL3_CONTR05`):** Logra el mejor desempeño global de todo el estudio en `GMEXICO B`:
    * **Brier:** **`0.244904`** ($\Delta\text{Brier vs Benchmark 8 vars} = -0.005722$, IC95% `[-0.011858, -0.000639]`, **excluye cero**; $\Delta\text{Brier vs 2 vars individual} = -0.003801$, IC95% `[-0.006445, -0.001152]`, **excluye cero**, mejorando en **10 de 12** semestres).
    * **Log-Loss:** **`0.682848`** (frente a `0.694624` del Benchmark de 8 variables).
    * **Balanced Accuracy:** **`56.38%`** (frente a `55.16%` del Benchmark y `51.90%` de 2 variables individuales).
    * **ROC AUC:** **`0.582198`** (frente a `0.544149` del Benchmark).
    * **Auto-calibración natural:** En `E2_P6_POOLED_REL3_CONTR05`, el selector anidado elige $\alpha = 1.0$ en los 12 semestres porque las probabilidades estimadas con el panel mancomunado ya están bien calibradas en validación interna y no requieren contracción artificial hacia `0.5`.

---

## 2. Resultados Detallados en `GMEXICO B` (Régimen Principal `EXPANSIVA`, $N = 803$, 12 Semestres)

* **Referencias Base:**
  * `DUMMY_PREVALENCIA`:
    * Brier: `0.251416`
    * Log-Loss: `0.695981`
    * Balanced Accuracy: `47.66%`
    * ROC AUC: `0.450199`
  * `REFERENCIA_CONSTANTE_05`:
    * Brier: `0.250000`
    * Log-Loss: `0.693147`
    * Balanced Accuracy: `50.00%`
    * ROC AUC: `0.500000`

* **Experimento 1 (Escalado Robusto y Ponderación por Magnitud en Entrenamiento Individual):**
  * `E1_A_BENCHMARK_8VARS_STD_UNIF` (Benchmark 8 variables, `StandardScaler`, pesos uniformes):
    * Brier: `0.250626`
    * Log-Loss: `0.694624`
    * Balanced Accuracy: `55.16%`
    * ROC AUC: `0.544149`
    * Semestres que supera al Dummy: `7 de 12`
    * Peor período: `2020-H1` (`Brier = 0.262554`)
  * `E1_C_BASE_2VARS_STD_UNIF` (Base 2 variables `ret_10`, `volatilidad_20`, `StandardScaler`, pesos uniformes):
    * Brier: `0.248705` ($\Delta\text{Brier vs Benchmark 8 vars} = -0.001921$)
    * Log-Loss: `0.690554`
    * Balanced Accuracy: `51.90%`
    * ROC AUC: `0.545551`
    * Semestres que supera al Benchmark 8 vars: `7 de 12`
    * Peor período: `2020-H2` (`Brier = 0.262836`)
  * `E1_R_2VARS_ROBUST_UNIF` (2 variables, `RobustScaler` con *winsorizing* `[1%, 99%]` en `Train`, pesos uniformes):
    * Brier: `0.248746` ($\Delta\text{Brier vs Base 2 vars} = +0.000041$, IC95% `[-0.000504, +0.000549]`)
    * Log-Loss: `0.690641`
    * Balanced Accuracy: `52.03%`
    * ROC AUC: `0.546469`
    * Semestres que supera al Benchmark 8 vars: `7 de 12`
  * `E1_M_2VARS_STD_MAGWEIGHT` (2 variables, `StandardScaler`, pesos por magnitud $|\text{ret}_{t \to t+5}|$ en `Train`):
    * Brier: `0.249986` ($\Delta\text{Brier vs Base 2 vars} = +0.001281$, IC95% `[-0.000865, +0.003702]`)
    * Log-Loss: `0.693137`
    * Balanced Accuracy: `51.93%`
    * ROC AUC: `0.543348`
    * Peor período: `2020-H2` (`Brier = 0.280503`)
  * `E1_RM_2VARS_ROBUST_MAGWEIGHT` (2 variables, `RobustScaler` + pesos por magnitud):
    * Brier: `0.250174` ($\Delta\text{Brier vs Base 2 vars} = +0.001469$, IC95% `[-0.000632, +0.003818]`)
    * Log-Loss: `0.693539`
    * Balanced Accuracy: `52.45%`
    * ROC AUC: `0.543435`
  * `E1_RMC_2VARS_ROBUST_MAG_CONTR05` (`RobustScaler` + magnitud + contracción anidada hacia `0.5`):
    * Brier: `0.250000` (el selector interno colapsa $\alpha = 0.0$ en los 12 semestres para defenderse de la sobreconfianza inducida por la ponderación de magnitud).

* **Experimento 2 (Entrenamiento en Panel Mancomunado *Pooled Panel* y Retorno Relativo Intrapanel):**
  * `E2_P1_INDIV_REL2_STD_UNIF` (Individual con `ret_10_rel_panel`, `volatilidad_20`):
    * Brier: `0.246297` ($\Delta\text{Brier vs Base 2 vars} = -0.002408$, IC95% `[-0.005708, +0.000394]`)
    * Log-Loss: `0.685624`
    * Balanced Accuracy: `51.72%`
    * ROC AUC: `0.559500`
    * Semestres que supera al Benchmark 8 vars: `9 de 12`
    * Semestres que supera al Dummy: `9 de 12`
  * `E2_P2_INDIV_REL3_STD_UNIF` (Individual con `ret_10`, `ret_10_rel_panel`, `volatilidad_20`):
    * Brier: `0.247060` ($\Delta\text{Brier vs Base 2 vars} = -0.001645$, IC95% `[-0.003602, +0.000170]`)
    * Log-Loss: `0.687159`
    * Balanced Accuracy: `52.47%`
    * ROC AUC: `0.556869`
    * Semestres que supera al Benchmark 8 vars: `8 de 12`
  * `E2_P3_POOLED_2VARS_STD_UNIF` (*Pooled Panel* en 8,122 filas elegibles con `ret_10`, `volatilidad_20`):
    * Brier: **`0.245458`**
    * $\Delta\text{Brier vs Base 2 vars}$: **`-0.003247`**, IC95% `[-0.005717, -0.000723]` (**IC95% no incluye cero**)
    * $\Delta\text{Brier vs Benchmark 8 vars}$: **`-0.005168`**, IC95% `[-0.011157, -0.000184]` (**IC95% no incluye cero**)
    * Log-Loss: `0.683985`
    * Balanced Accuracy: **`56.03%`**
    * ROC AUC: **`0.579021`**
    * Semestres que supera a Base 2 vars: `9 de 12`
    * Semestres que supera al Dummy: `10 de 12`
    * Desviación estándar semestral del Brier: `0.007525` (reduce 31% la dispersión semestral respecto al Benchmark `0.010959`)
  * `E2_P4_POOLED_REL3_STD_UNIF` (*Pooled Panel* con `ret_10`, `ret_10_rel_panel`, `volatilidad_20`):
    * Brier: **`0.244904`**
    * $\Delta\text{Brier vs Base 2 vars}$: **`-0.003801`**, IC95% `[-0.006445, -0.001152]` (**IC95% no incluye cero**)
    * $\Delta\text{Brier vs Benchmark 8 vars}$: **`-0.005722`**, IC95% `[-0.011858, -0.000639]` (**IC95% no incluye cero**)
    * Log-Loss: **`0.682848`**
    * Balanced Accuracy: **`56.38%`**
    * ROC AUC: **`0.582198`**
    * Semestres que supera a Base 2 vars: `10 de 12`
    * Semestres que supera al Dummy: `10 de 12`
    * Peor período: `2020-H2` (`Brier = 0.260696`)
  * `E2_P5_POOLED_REL3_ROBUST_MAG` (Fusión *Pooled Panel* + `ret_10_rel_panel` + `RobustScaler` + Magnitud):
    * Brier: **`0.244915`** ($\Delta\text{Brier vs Benchmark 8 vars} = -0.005711$, IC95% `[-0.011566, -0.000273]`, **IC95% no incluye cero**)
    * Balanced Accuracy: `55.05%`
    * ROC AUC: `0.580932`
    * Semestres que supera al Benchmark 8 vars: `8 de 12`
  * `E2_P6_POOLED_REL3_CONTR05` (*Pooled Panel* + `ret_10_rel_panel` + Contracción anidada hacia `0.5`):
    * Brier: **`0.244904`** (idéntico a `E2_P4_POOLED_REL3_STD_UNIF` porque la validación interna selecciona $\alpha = 1.0$ en los 12 semestres).

---

## 3. Validación Cruzada Multiemisora en `WALMEX *` (`EXPANSIVA`, $N = 1,270$, 13 Semestres)

* Para comprobar que la mejora del entrenamiento mancomunado (*Pooled Panel*) no es una coincidencia específica de `GMEXICO B`, el módulo evaluó exactamente el mismo protocolo sobre `WALMEX *` en `TRAIN <= 2025-04-29`:
  * `DUMMY_PREVALENCIA`: Brier `0.251278` | Balanced Accuracy `50.00%` | ROC AUC `0.521813`
  * `E1_A_BENCHMARK_8VARS_STD_UNIF` (Individual 8 vars): Brier `0.245151` | Balanced Accuracy `56.08%` | ROC AUC `0.596309` | Peor semestre `2022-H1` (`0.274393`)
  * `E1_C_BASE_2VARS_STD_UNIF` (Individual 2 vars): Brier `0.246245` | Balanced Accuracy `56.13%` | ROC AUC `0.591923`
  * `E2_P3_POOLED_2VARS_STD_UNIF` (*Pooled Panel* 2 vars):
    * Brier: **`0.244753`** (mejora frente a `E1_A` y reduce `-0.001492` frente a `E1_C`, ganando en **8 de 13** semestres vs `E1_C` y **10 de 13** vs Dummy).
    * Balanced Accuracy: **`57.10%`** (sube `+1.02` puntos porcentuales frente al Benchmark de 8 variables).
    * ROC AUC: **`0.599670`**.
    * Peor período: baja de `0.274393` (`E1_A`) a **`0.258408`** (reducción del 39% en la desviación estándar semestral del Brier, de `0.013851` a `0.008419`).
  * `E2_P4_POOLED_REL3_STD_UNIF` (*Pooled Panel* + Retorno Relativo Intrapanel):
    * Brier: **`0.244798`** (gana en **9 de 13** semestres frente al modelo individual de 2 variables y en **10 de 13** frente al Dummy).
    * Balanced Accuracy: **`56.95%`** | ROC AUC: **`0.599467`**.
  * `E2_P5_POOLED_REL3_ROBUST_MAG`:
    * Balanced Accuracy: **`57.89%`** | Accuracy: **`57.56%`** | Brier: `0.245403`.

---

## 4. Verificación de Integridad y Controles de Auditoría

* **Aislamiento de archivos protegidos:** Los hashes `SHA-256` de `serie_ppp_historica_15_emisoras_bmv.csv`, `dataset_panel_15_emisoras_features.csv`, `registro_senales_prospectivas_walmex.csv`, `registro_senales_prospectivas_gmexico.csv` y los directorios de experimentos previos permanecieron bit a bit idénticos antes y después de la ejecución (`integridad_archivos_protegidos_intacta = true`).
* **Garantías probadas en `test_experimentos_entrenamiento_desarrollo.py`:**
  * Corromper arbitrariamente las filas `TEST` y `PROSPECTIVA` del panel no altera ni un bit de los datos ni de las predicciones de desarrollo.
  * El `RobustScaler` (percentiles `P1, P25, P50, P75, P99`) y los pesos de magnitud se ajustan exclusivamente sobre `Train`.
  * En el entrenamiento mancomunado (*Pooled Panel*), toda etiqueta de cualquier emisora incluida en `Train` vence estrictamente antes del inicio del bloque validado ($\max(\text{fecha\_objetivo\_h5}_{\text{panel, Train}}) < \min(\text{fecha}_{\text{val}})$).
