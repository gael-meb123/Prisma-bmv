import { test } from "node:test";
import assert from "node:assert/strict";
import { solicitarRecuperacion, confirmarRecuperacion } from "./cognitoRecovery.mjs";

test("solicitar código no implica contraseña cambiada", async () => {
  const result = await solicitarRecuperacion({ forgotPassword(cb) { cb.inputVerificationCode(); } });
  assert.equal(result.error, null);
});
test("código vencido o incorrecto no confirma recuperación", async () => {
  const error = new Error("ExpiredCodeException");
  assert.equal((await confirmarRecuperacion({ confirmPassword(c, p, cb) { cb.onFailure(error); } }, "123456", "unused")).error, error);
  assert.ok((await confirmarRecuperacion({}, "", "unused")).error);
});
test("Cognito confirma cambio y propaga límites", async () => {
  assert.equal((await confirmarRecuperacion({ confirmPassword(c, p, cb) { cb.onSuccess(); } }, "123456", "unused")).error, null);
  const error = new Error("LimitExceededException");
  assert.equal((await solicitarRecuperacion({ forgotPassword(cb) { cb.onFailure(error); } })).error, error);
});
