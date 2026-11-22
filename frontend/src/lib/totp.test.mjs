import { test } from "node:test";
import assert from "node:assert/strict";
import { asociarTotp, activarTotp } from "./totp.mjs";

test("asocia y activa MFA solo después de verificar el código", async () => {
  const llamadas = [];
  const user = {
    associateSoftwareToken: (cb) => cb.associateSecretCode("clave-temporal"),
    verifySoftwareToken: (code, name, cb) => { llamadas.push(["verify", code, name]); cb.onSuccess({ Status: "SUCCESS" }); },
    setUserMfaPreference: (sms, totp, cb) => { llamadas.push(["preferencia", sms, totp]); cb(null); },
  };
  assert.equal(await asociarTotp(user), "clave-temporal");
  await activarTotp(user, "123456");
  assert.deepEqual(llamadas, [["verify", "123456", "Prisma BMV"], ["preferencia", null, { Enabled: true, PreferredMfa: true }]]);
});

test("no activa MFA si falla la verificación", async () => {
  let llamado = false;
  const user = {
    verifySoftwareToken: (_code, _name, cb) => cb.onSuccess({ Status: "ERROR" }),
    setUserMfaPreference: () => { llamado = true; },
  };
  await assert.rejects(activarTotp(user, "000000"), /no confirmó/);
  assert.equal(llamado, false);
});

test("informa explícitamente si falla la preferencia después de verificar", async () => {
  const user = {
    verifySoftwareToken: (_code, _name, cb) => cb.onSuccess({ Status: "SUCCESS" }),
    setUserMfaPreference: (_sms, _totp, cb) => cb(new Error("fallo")),
  };
  await assert.rejects(activarTotp(user, "123456"), /verificado, pero no se pudo activar/);
});
