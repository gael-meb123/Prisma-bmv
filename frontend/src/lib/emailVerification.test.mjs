import { test } from "node:test";
import assert from "node:assert/strict";
import { solicitarCodigoEmail, verificarCodigoEmail } from "./emailVerification.mjs";

test("solicita y verifica el atributo email", async () => {
  const calls = [];
  const user = {
    getAttributeVerificationCode(name, cb) { calls.push(name); cb.inputVerificationCode(); },
    verifyAttribute(name, code, cb) { calls.push([name, code]); cb.onSuccess(); },
  };
  await solicitarCodigoEmail(user);
  await verificarCodigoEmail(user, "123456");
  assert.deepEqual(calls, ["email", ["email", "123456"]]);
});

test("hidrata sesión de Cognito antes de solicitar o verificar y recorta espacios", async () => {
  const calls = [];
  let sesionCargada = false;
  const user = {
    getSession(cb) {
      calls.push("getSession");
      sesionCargada = true;
      cb(null, { isValid: () => true });
    },
    getAttributeVerificationCode(name, cb) {
      if (!sesionCargada) return cb.onFailure(new Error("User is not authenticated"));
      calls.push(["solicitar", name]);
      cb.inputVerificationCode();
    },
    verifyAttribute(name, code, cb) {
      if (!sesionCargada) return cb.onFailure(new Error("User is not authenticated"));
      calls.push(["verificar", name, code]);
      cb.onSuccess();
    },
  };
  await solicitarCodigoEmail(user);
  sesionCargada = false;
  await verificarCodigoEmail(user, " 123456 ");
  assert.deepEqual(calls, [
    "getSession",
    ["solicitar", "email"],
    "getSession",
    ["verificar", "email", "123456"],
  ]);
});

test("rechaza si la sesión no es válida sin invocar verifyAttribute", async () => {
  let invocado = false;
  const user = {
    getSession(cb) { cb(null, { isValid: () => false }); },
    verifyAttribute() { invocado = true; },
  };
  await assert.rejects(verificarCodigoEmail(user, "123456"), /Sesión inválida/);
  assert.equal(invocado, false);
});

test("no oculta errores del proveedor", async () => {
  const user = { verifyAttribute(_name, _code, cb) { cb.onFailure(new Error("código inválido")); } };
  await assert.rejects(verificarCodigoEmail(user, "0"), /código inválido/);
});
