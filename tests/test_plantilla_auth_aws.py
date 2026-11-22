import unittest
from pathlib import Path


class AuthAisladoTest(unittest.TestCase):
    def test_barreras_explicitas_sin_iam_publico(self):
        texto = (Path(__file__).resolve().parent.parent / "infra/auth_aws_aislado/template.yaml").read_text()
        for cadena in ("AllowAdminCreateUserOnly: !If [RegistroHabilitado, false, true]", "GenerateSecret: false",
                       "DeletionProtection: ACTIVE", "PAY_PER_REQUEST",
                       "WriteAttributes:\n        - name", "DeletionPolicy: Retain"):
            self.assertIn(cadena, texto)
        self.assertNotIn("AWS::IAM::Policy", texto)
        self.assertNotIn("AWS::Cognito::IdentityPool", texto)


if __name__ == "__main__":
    unittest.main()
