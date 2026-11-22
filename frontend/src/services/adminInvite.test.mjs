import { test } from "node:test";
import assert from "node:assert/strict";
import { cuerpoAlta, mensajeAlta } from "./adminInvite.mjs";

test("Cognito no envía contraseñas desde la interfaz", () => {
  const datos = { nombre: "X", email: "x@example.org", password: "temporal", rol: "user", plan: "explorer" };
  assert.equal("password" in cuerpoAlta(datos, true), false);
  assert.equal(cuerpoAlta(datos, false).password, "temporal");
});

test("un envío incierto no se presenta como invitación entregada", () => {
  assert.match(mensajeAlta({ invitacion: "ENVIO_NO_CONFIRMADO" }), /no se confirmó/);
  assert.match(mensajeAlta({ invitacion: "ACEPTADA_POR_COGNITO" }), /entrega.*no están confirmadas/);
});
