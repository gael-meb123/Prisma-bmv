import test from "node:test";
import assert from "node:assert/strict";
import { calcularOperacion } from "./costosInversion.mjs";

const base = { acciones: "100", compra: "100", venta: "110", comisionCompra: "1",
  comisionVenta: "1", iva: "16", otrosCompra: "0", otrosVenta: "0", impuesto: "" };

test("desglosa compra, venta, IVA y resultado sin suponer impuestos", () => {
  const r = calcularOperacion(base);
  assert.equal(r.comCompra, 100);
  assert.equal(r.ivaCompra, 16);
  assert.equal(r.comVenta, 110);
  assert.equal(r.ivaVenta, 17.6);
  assert.equal(r.totalCompra, 10116);
  assert.equal(r.totalVenta, 10872.4);
  assert.ok(Math.abs(r.resultado - 756.4) < 1e-9);
  assert.equal(r.resultadoConImpuesto, null);
  const equilibrio = calcularOperacion({ ...base, venta: String(r.puntoEquilibrio) });
  assert.ok(Math.abs(equilibrio.resultado) < 1e-8);
});

test("incluye cargos y el impuesto aportado por el usuario, aun con pérdida", () => {
  const r = calcularOperacion({ ...base, venta: "90", otrosCompra: "5", otrosVenta: "10", impuesto: "20" });
  assert.ok(r.resultado < 0);
  assert.equal(r.resultadoConImpuesto, r.resultado - 20);
});

test("comisiones cero solo se aceptan si se capturan explícitamente", () => {
  assert.ok(calcularOperacion({ ...base, comisionCompra: "" }).error);
  const r = calcularOperacion({ ...base, comisionCompra: "0", comisionVenta: "0", iva: "0" });
  assert.equal(r.resultado, 1000);
  assert.equal(r.puntoEquilibrio, 100);
});

test("rechaza valores inválidos y división por cero", () => {
  for (const cambios of [{ acciones: "1.5" }, { compra: "0" }, { otrosVenta: "-1" },
    { iva: "101" }, { comisionVenta: "100", iva: "0" }, { impuesto: "-1" }]) {
    assert.ok(calcularOperacion({ ...base, ...cambios }).error);
  }
});
