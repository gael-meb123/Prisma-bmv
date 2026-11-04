# Módulo 1: Monitor de Mercado BMV en Vivo (Oficial PPP)
## Guía de Desarrollo para Desarrollador 1

> **Objetivo de este módulo:** Construir la vista de cotizaciones oficiales de las 15 emisoras del IPC mexicano, destacando la política de cero imputación y el sello criptográfico SHA-256 de cada boletín diario.

---

### 1. ¿Cómo trabajar de forma 100% independiente?

No necesitas esperar a tus compañeros ni modificar `app.py`. Para programar y ver tus cambios en tiempo real en tu navegador web, ejecuta únicamente tu módulo:

```powershell
streamlit run modulos/modulo1_mercado/vista_mercado.py
```

Tu archivo `vista_mercado.py` cuenta con un ejecutor independiente al final que te permite probar tu pantalla de forma aislada.

---

### 2. Insumos y Funciones que tienes disponibles

En `core.data_provider` ya tienes las funciones de datos listas y cacheadas con `@st.cache_data`. No tienes que programar conexión a bases de datos:

* `cargar_monitoreo_en_vivo() -> pd.DataFrame`:
  * Devuelve el DataFrame completo con el monitoreo de las 15 emisoras.
  * Columnas clave: `fecha`, `emisora`, `serie`, `sector_economico`, `ppp_bmv_mxn`, `anterior_bmv_mxn`, `variacion_ppp_vs_anterior_pct`, `estado_captura`, `sha256_boletin`, `url_fuente`.
* `obtener_fechas_mercado() -> list[str]`:
  * Devuelve la lista ordenada de fechas disponibles (ej. `['2026-10-30', '2026-10-29', '2026-10-28']`).
* `obtener_kpis_mercado(fecha) -> dict`:
  * Devuelve métricas calculadas: `total_emisoras`, `total_verificadas`, `total_ausentes`, `top_alza_ticker`, `top_alza_pct`, `top_baja_ticker`, `top_baja_pct`, `sha256_boletin`, `url_fuente`.

---

### 3. Componentes Visuales que debes construir / mejorar

1. **Selector de Fechas y Filtro por Sector:**
   * Selector interactivo para cambiar de sesión bursátil.
   * Filtro desplegable por sector económico (Minería, Banca, Consumo, Telecomunicaciones, Infraestructura).
2. **5 Tarjetas de Métricas Ejecutivas (KPIs):**
   * Total de emisoras en lista (15).
   * Cotizaciones PPP verificadas en boletín (Verde).
   * Huecos bursátiles documentados por cero imputación (Ámbar).
   * Mayor alza del día (% ganancia y ticker).
   * Mayor caída del día (% pérdida y ticker).
3. **Tabla Interactiva de Cotizaciones:**
   * Mostrar columnas ordenadas: Ticker, Serie, Sector, PPP Oficial ($MXN), Variación %, Precio Anterior, Estado de Captura.
   * Formato condicional: Valores positivos en verde, negativos en rojo, y `NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA` en gris o ámbar para evidenciar que no se inventan datos.
4. **Tarjeta de Auditoría Criptográfica SHA-256:**
   * Cuadro visible con el hash SHA-256 del boletín oficial y un botón/enlace que abra la fuente en `bmv.com.mx`.

---

### 4. Reglas de Estilo Institucional
- Mantener la paleta oscura: Fondos oscuros (`#0A0E17`), verde esmeralda (`#10B981`) para alzas, rojo (`#EF4444`) para bajas.
- No incluir menciones académicas (todo con tono de terminal financiera profesional).
