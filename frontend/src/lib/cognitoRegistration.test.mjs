import { test } from "node:test";
import assert from "node:assert/strict";
import { registrar, confirmarRegistro, reenviarRegistro } from "./cognitoRegistration.mjs";

test("registro manda solo email/nombre y espera confirmación", async () => {
  class Attribute { constructor(value) { Object.assign(this, value); } }
  const pool = { signUp(email, password, attrs, validation, cb) {
    assert.deepEqual(attrs.map(x => x.Name), ["email", "name"]);
    cb(null, { userConfirmed: false });
  } };
  assert.equal((await registrar(pool, Attribute, { email: "a@example.org", password: "unused", nombre: "Ana" })).confirmacionRequerida, true);
});
test("confirmación no fuerza migración de alias y propaga error", async () => {
  const error = new Error("Código vencido");
  const user = { confirmRegistration(code, force, cb) { assert.equal(force, false); cb(error); } };
  assert.equal((await confirmarRegistro(user, "123456")).error, error);
  assert.ok((await confirmarRegistro({}, "invalido")).error);
});
test("reenvío propaga error de servicio", async () => {
  const error = new Error("Límite");
  assert.equal((await reenviarRegistro({ resendConfirmationCode(cb) { cb(error); } })).error, error);
});
