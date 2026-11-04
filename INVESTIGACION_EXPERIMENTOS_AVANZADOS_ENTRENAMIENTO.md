# Investigación de Experimentos Avanzados de Entrenamiento (`TRAIN <= 2025-04-29`)

## 1. Alcance y Verificación de Integridad

* **Módulo implementado:** `experimentos_avanzados_entrenamiento.py`
* **Directorio aislado:** `experimentos_avanzados_entrenamiento/`
* **Pruebas unitarias:** `test_experimentos_avanzados_entrenamiento.py` (**54/54 pruebas unitarias en verde** en todo el repositorio).
* **Cobertura temporal:** Exclusivamente `TRAIN` ($\le \text{2025-04-29}$), evaluando las mismas 803 predicciones externas en 12 semestres de `GMEXICO B` y 1,270 predicciones externas en 13 semestres de `WALMEX *`, sin tocar `TEST` ni `PROSPECTIVA`.

---

## 2. Resultados del Experimento 3: Filtrado de Zona Neutral (*Dead-Zone Training*)

* **Hipótesis evaluada:** En lugar de multiplicar los pesos de entrenamiento por la magnitud del retorno (lo cual infló los coeficientes en los *outliers* durante el Experimento 1), mantener pesos uniformes ($w_i = 1$) pero excluir únicamente de `Train` las sesiones con movimiento microestructural casi nulo ($|\text{PPP}_{t+5}/\text{PPP}_t - 1| < \tau$), evaluando el 100% de las fechas de validación sin filtrar.
* **Resultados en `GMEXICO B` ($N = 803$):**
  * `REF_C_INDIV_2VARS` (2 variables sin filtrar):
    * Brier: `0.248705` | Balanced Accuracy: `51.90%` | ROC AUC: `0.545551`
  * `E3_DZ15_INDIV_2VARS` (filtrando $|\text{ret}_{h5}| < 0.15\%$ en `Train`):
    * Brier: **`0.248167`** ($\Delta\text{Brier vs REF\_C} = -0.000538$, mejora en **7 de 12** semestres)
    * Balanced Accuracy: `51.86%` | ROC AUC: **`0.551266`**
  * `E3_DZ25_INDIV_2VARS` (filtrando $|\text{ret}_{h5}| < 0.25\%$ en `Train`):
    * Brier: **`0.248265`** ($\Delta\text{Brier vs REF\_C} = -0.000440$)
    * Balanced Accuracy: **`52.10%`** | ROC AUC: **`0.550199`**
  * `E3_DZ_ANIDADO_POOLED_REL3` (Zona neutral anidada sobre el *Pooled Panel* con retorno relativo):
    * Brier: **`0.244744`** (**el menor Brier Score de todas las variantes en `GMEXICO B`**, superando a `REF_P4_POOLED_REL3` `0.244904` en **8 de 12** semestres y al Benchmark de 8 variables `0.250626` por `-0.005882`).
    * Balanced Accuracy: **`55.90%`** | ROC AUC: **`0.582806`**.
* **Resultados en `WALMEX *` ($N = 1,270$):**
  * `E3_DZ_ANIDADO_POOLED_REL3`:
    * Brier: **`0.244847`** | Balanced Accuracy: **`57.22%`** | ROC AUC: **`0.599687`**.

---

## 3. Resultados del Experimento 4: Regularización Jerárquica Emisora + Panel

* **Hipótesis evaluada:** Combinar la probabilidad del modelo individual de la emisora con la del modelo mancomunado del panel ($p_{\text{mix}} = \gamma p_{\text{indiv}} + (1 - \gamma) p_{\text{panel}}$) seleccionando $\gamma \in \{0.0, 0.25, 0.50, 0.75, 1.0\}$ en validación interna anidada.
* **Hallazgo empírico:**
  * Tanto en `GMEXICO B` como en `WALMEX *`, la validación interna anidada selecciona **$\gamma = 0.0$ (100% de peso al modelo *Pooled Panel*)** en todos los semestres para `E4_JERARQ_2VARS`, `E4_JERARQ_REL3` y `E4_JERARQ_8VARS_VS_POOLED_REL3`.
  * **Interpretación:** Una vez que el modelo mancomunado incluye las variables estandarizadas por emisora y el retorno relativo intrapanel (`ret_10_rel_panel`), la varianza de estimación del panel es tan inferior a la del ajuste individual que mezclar pesos individuales no reduce el Brier interno.

---

## 4. Resultados del Experimento 5: Frontera de Regularización ($C < 0.01$) y Auditoría de `class_weight='balanced'`

* **Hallazgo 5A — Diagnóstico de la configuración prospectiva `V1` (`E5_BALANCED_8VARS_C1`):**
  * En `GMEXICO B`, entrenar las 8 variables con `balanced=True` y regularización débil $C = 1.0$ (la configuración de `V1_LOGREG_BALANCEADA`) produce el **peor Brier de todo el estudio (`0.254762`)**, empeorando en `+0.004136` frente al Benchmark regularizado sin balanceo (`0.250626`) y alcanzando un Brier de `0.303956` en su peor semestre (`2020-H2`).
  * Cuando se aplica selección anidada de $C$ ($C = 0.01$) a `balanced=True` (`E5_BALANCED_8VARS_CANIDADO`), la fuerte penalización L2 corrige la sobreconfianza (`Brier = 0.248892`, `Balanced Accuracy = 55.76%` en `GMEXICO B` y `Brier = 0.243854`, `Balanced Accuracy = 56.22%` en `WALMEX *`), demostrando que el deterioro de `V1` provenía de usar $C=1.0$ sin regularización suficiente sobre 8 variables colineales.

* **Hallazgo 5B — Desbloqueo de $C \in \{0.001, 0.002, 0.005\}$ en Individual vs Panel:**
  * En los modelos **individuales** (`E5_CGRID_FINO_INDIV_8VARS` y `E5_CGRID_FINO_INDIV_2VARS`), permitir $C = 0.001$ con solo ~400–1,000 filas sobre-regulariza (*underfits*) la señal individual, reduciendo el `ROC AUC` a `0.5242` y `0.5090`.
  * En cambio, en el **modelo de Panel Mancomunado (`E5_CGRID_FINO_POOLED_REL3`)**, donde el número de observaciones de entrenamiento es ~7 veces mayor (`2,176` a `7,510` filas) y por tanto la suma de la verosimilitud es 7 veces más grande, una penalización $C \in \{0.001, 0.002\}$ equilibra exactamente la escala del gradiente del panel y logra la **mayor precisión direccional y capacidad de ordenamiento (`ROC AUC`) de todo el proyecto**:
    * **En `GMEXICO B`:**
      * **Balanced Accuracy:** **`57.95%`** (`Accuracy = 57.78%`, frente a `55.16%` del Benchmark).
      * **ROC AUC:** **`0.592939`** (frente a `0.544149` del Benchmark).
      * **Brier:** **`0.245498`** ($\Delta\text{Brier vs Benchmark 8 vars} = -0.005128$, ganando en **8 de 12** semestres y en **10 de 12** frente al Dummy).
      * **Estabilidad récord:** El peor semestre de toda la historia (`2020-H2`) tiene un Brier de apenas **`0.251048`** (frente a `0.262554` del Benchmark) y la desviación estándar semestral cae un **61%** (`0.004277` vs `0.010959`).
    * **En `WALMEX *`:**
      * **Balanced Accuracy:** **`57.83%`** (`Accuracy = 57.56%`, frente a `56.08%` del Benchmark).
      * **ROC AUC:** **`0.596631`**.
