/**
 * Simulación de compraventa de títulos enteros, con tarifas capturadas por el
 * usuario. No calcula el impuesto fiscal efectivo ni consulta precios en vivo.
 */
export function calcularOperacion({ acciones, compra, venta, comisionCompra, comisionVenta, iva, otrosCompra, otrosVenta, impuesto }) {
  const campos = { acciones, compra, venta, comisionCompra, comisionVenta, iva, otrosCompra, otrosVenta };
  if (Object.values(campos).some((v) => v === "" || v == null || !Number.isFinite(Number(v)))) {
    return { error: "Completa todos los campos de la operación y los cargos. Captura 0 solo si corresponde." };
  }
  const n = Object.fromEntries(Object.entries(campos).map(([k, v]) => [k, Number(v)]));
  if (!Number.isSafeInteger(n.acciones) || n.acciones < 1 || n.compra <= 0 || n.venta <= 0) {
    return { error: "Indica al menos una acción entera y precios mayores que cero." };
  }
  if ([n.comisionCompra, n.comisionVenta, n.iva].some((v) => v < 0 || v > 100) || n.otrosCompra < 0 || n.otrosVenta < 0) {
    return { error: "Los porcentajes deben estar entre 0 y 100; los cargos no pueden ser negativos." };
  }
  const impuestoIngresado = impuesto !== "" && impuesto != null;
  const impuestoValor = impuestoIngresado ? Number(impuesto) : null;
  if (impuestoIngresado && (!Number.isFinite(impuestoValor) || impuestoValor < 0)) {
    return { error: "La estimación fiscal debe ser un monto no negativo." };
  }
  const tasaCompra = n.comisionCompra / 100;
  const tasaVenta = n.comisionVenta / 100;
  const tasaIva = n.iva / 100;
  const factorVenta = 1 - tasaVenta * (1 + tasaIva);
  if (factorVenta <= 0) return { error: "La comisión de venta con IVA debe ser menor al importe de venta." };
  const importeCompra = n.acciones * n.compra;
  const importeVenta = n.acciones * n.venta;
  const comCompra = importeCompra * tasaCompra;
  const comVenta = importeVenta * tasaVenta;
  const ivaCompra = comCompra * tasaIva;
  const ivaVenta = comVenta * tasaIva;
  const totalCompra = importeCompra + comCompra + ivaCompra + n.otrosCompra;
  const totalVenta = importeVenta - comVenta - ivaVenta - n.otrosVenta;
  const resultado = totalVenta - totalCompra;
  const puntoEquilibrio = (totalCompra + n.otrosVenta) / (n.acciones * factorVenta);
  const datos = { importeCompra, importeVenta, comCompra, comVenta, ivaCompra, ivaVenta,
    otrosCompra: n.otrosCompra, otrosVenta: n.otrosVenta, totalCompra, totalVenta,
    bruto: importeVenta - importeCompra, resultado, puntoEquilibrio,
    impuesto: impuestoValor, resultadoConImpuesto: impuestoIngresado ? resultado - impuestoValor : null };
  if (Object.values(datos).some((v) => typeof v === "number" && !Number.isFinite(v))) {
    return { error: "Los importes son demasiado grandes para calcularlos." };
  }
  return datos;
}
