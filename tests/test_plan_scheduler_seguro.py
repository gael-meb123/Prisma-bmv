import unittest
from copy import deepcopy
from scripts.planificar_scheduler_seguro import planificar, FUNCION
from tests.test_recolector_seguro import S3, HTML, BUCKET, recolector


class SchedulerTest(unittest.TestCase):
    def test_preparar_activar_y_revertir_sin_reactivar_legado(self):
        actual = {"Name": "DisparadorDiarioBMV", "GroupName": "default", "State": "DISABLED",
                  "ScheduleExpression": "cron(45 16 ? * MON-FRI *)",
                  "ScheduleExpressionTimezone": "America/Mexico_City", "FlexibleTimeWindow": {"Mode": "OFF"},
                  "Target": {"Arn": "anterior", "RoleArn": "rol"}, "Arn": "solo-lectura"}
        copia = deepcopy(actual)
        preparado = planificar(actual, "preparar")
        self.assertEqual(actual, copia)
        self.assertEqual(preparado["State"], "DISABLED")
        self.assertEqual(preparado["Target"]["Arn"], FUNCION)
        self.assertNotIn("Arn", preparado)
        activo = planificar(preparado, "activar")
        self.assertEqual(activo["State"], "ENABLED")
        self.assertEqual(activo["ScheduleExpressionTimezone"], actual["ScheduleExpressionTimezone"])
        self.assertEqual(planificar(actual, "restaurar")["State"], "DISABLED")
        with self.assertRaises(ValueError):
            planificar(actual, "activar")
        with self.assertRaises(ValueError):
            planificar(activo, "preparar")

    def test_reintento_conserva_fecha_programada_aunque_cambie_dia(self):
        resultado = recolector.ejecutar({"instante_programado": "2026-11-20T01:00:00Z"},
                                        S3(), lambda _: HTML, BUCKET)
        self.assertEqual(resultado["fecha"], "2026-11-19")
        with self.assertRaises(ValueError):
            recolector.ejecutar({"instante_programado": "2026-11-20T01:00:00"}, S3(), lambda _: HTML, BUCKET)
