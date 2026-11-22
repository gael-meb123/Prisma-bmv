import React, { useState } from "react";
import { calcularOperacion } from "../../utils/costosInversion.mjs";
import { formatMoney } from "../../utils/presentation.mjs";
import "./costos-inversion.css";

// Enlaces institucionales revisados el 18/11/2026. La disponibilidad de cada
// emisora, la serie, los servicios y la tarifa dependen de la cuenta contratada.
const INTERMEDIARIOS = [
  { nombre: "GBM Trading", url: "https://gbm.com/trading/" },
  { nombre: "Actinver Trade", url: "https://actinvertrade.actinver.com/" },
];
const CAMPOS_INICIALES = {
  acciones: "", compra: "", venta: "", comisionCompra: "", comisionVenta: "",
  iva: "", otrosCompra: "", otrosVenta: "", impuesto: "",
};

export function CostosInversion({ emisora }) {
  const [campos, setCampos] = useState(CAMPOS_INICIALES);
  const [mostrar, setMostrar] = useState(false);
  const resultado = mostrar ? calcularOperacion(campos) : null;

  function campo(nombre, etiqueta, ayuda, opciones = {}) {
    return (
      <label className="costos-campo">
        <span>{etiqueta}</span>
        <input
          type="number" inputMode="decimal" min="0" step={opciones.entero ? "1" : "any"}
          max={opciones.porcentaje ? "100" : undefined}
          value={campos[nombre]}
          onChange={(e) => setCampos((prev) => ({ ...prev, [nombre]: e.target.value }))}
          placeholder={opciones.opcional ? "Opcional" : "Captura un valor"}
        />
        {ayuda && <small>{ayuda}</small>}
      </label>
    );
  }

  return (
    <section className="bk-card bk-card-pad costos-panel" aria-labelledby="costos-titulo">
      <div>
        <span className="bk-eyebrow">SIMULADOR INFORMATIVO</span>
        <h3 id="costos-titulo">Estima el resultado de una operación · {emisora}</h3>
        <p>Prueba un precio de venta hipotético y revisa cómo afectan los cargos. Esto no ejecuta una orden ni es una recomendación.</p>
      </div>
      <div className="costos-brokers">
        <strong>Conoce intermediarios</strong>
        <div>
          {INTERMEDIARIOS.map((item) => (
            <a key={item.nombre} href={item.url} target="_blank" rel="noopener noreferrer">{item.nombre} ↗</a>
          ))}
        </div>
        <small>Enlaces oficiales de información general, no a una orden de {emisora}. Confirma disponibilidad, serie y tarifas para tu cuenta. Tarifas no verificadas; captúralas manualmente.</small>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); setMostrar(true); }}>
        <div className="costos-grid">
          {campo("acciones", "Número de acciones", "Solo títulos enteros.", { entero: true })}
          {campo("compra", "Precio de compra estimado (MXN)", "Captúralo según tu intermediario.")}
          {campo("venta", "Precio de venta hipotético (MXN)", "Es un escenario, no un pronóstico.")}
          {campo("comisionCompra", "Comisión de compra (%)", "Antes de IVA.", { porcentaje: true })}
          {campo("comisionVenta", "Comisión de venta (%)", "Antes de IVA.", { porcentaje: true })}
          {campo("iva", "IVA sobre comisiones (%)", "Indica la tasa aplicable a tu caso.", { porcentaje: true })}
          {campo("otrosCompra", "Otros cargos de compra (MXN)", "Monto total; captura 0 si no aplican.")}
          {campo("otrosVenta", "Otros cargos de venta (MXN)", "Monto total; captura 0 si no aplican.")}
          {campo("impuesto", "Estimación fiscal adicional (MXN)", "Opcional; monto total estimado por ti.", { opcional: true })}
        </div>
        <button type="submit" className="bk-btn bk-btn-primary">Calcular escenario</button>
      </form>
      {resultado?.error && <p className="costos-error" role="alert">{resultado.error}</p>}
      {resultado && !resultado.error && (
        <div className="costos-resultado" aria-live="polite">
          <h4>Desglose estimado</h4>
          <dl>
            <div><dt>Compra de acciones</dt><dd>{formatMoney(resultado.importeCompra)}</dd></div>
            <div><dt>Comisión de compra</dt><dd>{formatMoney(resultado.comCompra)}</dd></div>
            <div><dt>IVA sobre comisión de compra</dt><dd>{formatMoney(resultado.ivaCompra)}</dd></div>
            <div><dt>Otros cargos de compra</dt><dd>{formatMoney(resultado.otrosCompra)}</dd></div>
            <div><dt>Total de compra</dt><dd>{formatMoney(resultado.totalCompra)}</dd></div>
            <div><dt>Venta hipotética</dt><dd>{formatMoney(resultado.importeVenta)}</dd></div>
            <div><dt>Comisión de venta</dt><dd>{formatMoney(resultado.comVenta)}</dd></div>
            <div><dt>IVA sobre comisión de venta</dt><dd>{formatMoney(resultado.ivaVenta)}</dd></div>
            <div><dt>Otros cargos de venta</dt><dd>{formatMoney(resultado.otrosVenta)}</dd></div>
            <div><dt>Resultado bruto, sin cargos</dt><dd>{formatMoney(resultado.bruto)}</dd></div>
            <div className="costos-destacado"><dt>Resultado después de cargos, antes de impuestos sobre ganancias</dt><dd>{formatMoney(resultado.resultado)}</dd></div>
            <div><dt>Precio de equilibrio por acción, antes de impuestos sobre ganancias</dt><dd>{formatMoney(resultado.puntoEquilibrio)}</dd></div>
            {resultado.impuesto != null && <>
              <div><dt>Estimación fiscal capturada</dt><dd>{formatMoney(resultado.impuesto)}</dd></div>
              <div className="costos-destacado"><dt>Resultado después de la estimación fiscal</dt><dd>{formatMoney(resultado.resultadoConImpuesto)}</dd></div>
            </>}
          </dl>
          <p>El precio de equilibrio se muestra redondeado; el mínimo ejecutable puede variar por incrementos de cotización y redondeos del intermediario.</p>
        </div>
      )}
      <p className="costos-aviso">El PPP de la señal no es necesariamente el precio de compra o venta. Las probabilidades no indican cuánto cambiará el precio. No se incluyen automáticamente impuestos sobre ganancias, diferenciales, liquidez, dividendos ni otros cargos no capturados. Consulta a tu intermediario y asesor fiscal.</p>
    </section>
  );
}
