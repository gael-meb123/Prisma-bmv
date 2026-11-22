# Plan de Cierre: Fuente BMV Completa, Precios SaaS, Modelos IPC-35 y Retiro de Supabase

**Fecha:** 21 de noviembre de 2026  
**Estado:** Implementación técnica en AWS completada (trabajo 12, API `762d336a...`, Recolector `49f704d7...`, Scheduler `ENABLED`, `silver/ipc35_provisional/` con 19 cortes); compuertas externas de datos y permisos activas.

---

## 1. ¿Qué significa «gestionar acceso a una fuente BMV completa»?

La auditoría real sobre **19 boletines RSS HTML** (`evidencias/auditorias/cobertura_ipc35_20261121T235840Z.json`) demostró que el boletín público RSS de BMV solo incluye **tablas parciales** (emisoras más negociadas / mayores alzas y bajas):
- Solo las **5 emisoras G2** (`AMX, FEMSA, GFNORTE, GMEXICO, WALMEX`) aparecieron en el 100 % de las sesiones (19/19).
- **0 de los 20 candidatos nuevos** alcanzaron 100 % diario en RSS (`VOLAR A` lideró con ~63 %, `KOF UBL` ~58 %, `PINFRA *` y `LIVEPOL C-1` tuvieron 0/19).

Para cubrir los **35 componentes del IPC todos los días sin huecos de boletín parcial**, existen dos productos oficiales de BMV (detallados en `docs/INVESTIGACION_FUENTE_BMV_PPP.md`):
1. **Web Service `obtenQuoteEmisorasMC` (Soluciones Web BMV):** servicio SOAP autenticado (usuario/contraseña + IP autorizada) cuyo esquema oficial incluye `CveEmisora`, `CveSerie`, `PPP` y `Fecha` (retraso de 20 minutos).
2. **Bases de Datos Históricas / Cierres Diarios BMV:** entrega de archivos diarios/históricos por suscripción o convenio académico.

**Cómo gestionarlo (sin comprometer compra previa):** escribir a **marketdatasales@grupobmv.com.mx** (y para la composición oficial fechada del índice a **indices@grupobmv.com.mx**) solicitando bajo convenio académico/proyecto:
- Muestra de 1 sesión y diccionario de datos con **PPP diario final por emisora y serie** para los 35 componentes (verificando `R / A` y `LIVEPOL / C-1`).
- Confirmación de si existe acceso académico gratuito o tarifa preferencial para `obtenQuoteEmisorasMC` o archivo diario de cierre.
- Confirmación por escrito de que la autorización permite **almacenamiento en AWS S3 y visualización pública en la aplicación web** (Amplify).

---

## 2. Propuesta de precios y planes (benchmark de mercado 2025–2026)

### Referencia de competidores comparables (USD/mes en facturación anual / mensual)

| Plataforma | Enfoque | Nivel gratuito | Nivel intermedio | Nivel avanzado / Pro | Institucional / API |
|---|---|---|---|---|---|
| **TradingView** | Gráficas y análisis técnico | $0 | $13–$30 | $60 | $200 |
| **Danelfin** | Señales probabilísticas con IA | $0 | $13–$29 | $35–$59 | $80–$134 |
| **Koyfin** | Terminal fundamental y screening | $0 | $39–$49 | $79 | $209–$299+ |
| **Seeking Alpha** | Ratings cuantitativos + portafolio | $0 | ~$25 ($299/año) | ~$42 ($499/año) | Bundles ~$53/mes |
| **Prisma BMV actual** (`plans.mjs`) | PPP oficial + modelos G2 (15) | $0 | $49 USD | — | $199 USD |

### Recomendación calibrada para Prisma BMV (35 componentes IPC + señales G2)

En México/LatAm, **$49 USD/mes (~$980 MXN)** en el plan intermedio es alto para inversionistas individuales frente a Danelfin ($13–$35 USD) o TradingView ($13–$30 USD). Al integrar los 35 componentes del IPC y validar los modelos G2, se recomienda la siguiente escalera:

| Plan | Precio sugerido | Cobertura y valor diferencial |
|---|---|---|
| **Explorer** | **$0 MXN / mes** | Mercado diario de los **35 componentes del IPC** (con cobertura y huecos transparentes), estadística descriptiva + serie y señales t+5 de **WALMEX**, verificación SHA-256. |
| **Professional** | **$349–$499 MXN / mes** (~$19–$25 USD; anual con 20 % desc.) | Acceso completo a los **35 componentes del IPC**: series históricas, estadística descriptiva, **señales G2, consenso multi-modelo y seguimiento t+5** para todas las emisoras con modelo validado, comparador A/B, observación secundaria Yahoo (si se aprueba permiso) y exportación PDF/CSV. |
| **Enterprise** | **$2,990–$3,990 MXN / mes** (~$149–$199 USD) | Todo Professional + acceso API REST y consultas Athena/S3 con cuotas ampliadas, múltiples cuentas analistas, bitácora auditable SHA-256 descargable y soporte prioritario para mesas, fondos o universidades. |

> *Nota:* Esta estructura es una recomendación comercial sujeta a validación final; los permisos técnicos actuales en Cognito/DynamoDB no se modificaron y las señales continúan bloqueadas hasta validar datos y modelos.

---

## 3. Plan de entrenamiento y validación de modelos para los 35 componentes del IPC

No se habilita inferencia copiando escaladores de `WALMEX` ni extrapolando métricas del panel de 5/15 emisoras. Cada nueva emisora del IPC-35 debe superar 5 compuertas:

1. **Higiene y cobertura histórica:** mínimo 252 sesiones verificadas BMV por par `(emisora, serie)`, respetando huecos sin imputación y aplicando exclusión explícita en transiciones de serie sin factor corporativo validado (como las **13 filas de transición `AMX L → AMX B` del 2023-03-28 al 2023-04-17**, ya auditadas en `evidencias/auditorias/auditoria_amx_unificacion_serie_2023.json`).
2. **Conciliación de eventos corporativos:** cerrar Ola 1 (33 eventos G2 2024–2026) y extender el cruce oficial de avisos BMV/Indeval a cada emisora antes de generar retornos ajustados (`ret_*_adj`).
3. **Entrenamiento temporal sin fuga (*walk-forward*):** escaladores independientes por `(emisora, serie)`, congelamiento de hiperparámetros previo al periodo *out-of-sample*, y cálculo explícito de variables relativas contra un universo fechado (sin *survivorship bias*).
4. **Criterios cuantitativos de aprobación:** mejora consistente *out-of-sample* frente a climatología y referencia ingenua en **Brier Score**, **log-loss**, **ROC-AUC** y calibración de probabilidades.
5. **Periodo *shadow* y promoción individual:** operar al menos 20 sesiones prospectivas en *shadow* (registrando en Gold sin exponer al usuario final) y promover por emisora individual mediante registro versionado con SHA-256.

---

## 4. Ruta de retiro de Supabase (tras validar `#/admin`)

Tu cuenta `djlexus134@gmail.com` ya tiene `rol: "admin"` en DynamoDB. Una vez que pruebes en `https://react-demo.d315dh37vi024o.amplifyapp.com/#/admin`:
1. Confirmar listado de perfiles, cambio de plan/rol e invitación administrativa real.
2. Retirar las referencias residuales a `@supabase/supabase-js` y `frontend/src/lib/supabase.mjs` únicamente cuando confirmes que no queda ningún flujo local dependiente de Supabase.
3. Conservar `api.py` / Streamlit desconectados de Supabase o migrados a Cognito si se siguen usando en local.
