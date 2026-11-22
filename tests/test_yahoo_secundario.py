import json
import unittest
from datetime import datetime, timezone
from prisma.data.yahoo_secundario import interpretar_cierre


def payload(symbol="WALMEX.MX", currency="MXN", timestamps=None, prices=None):
    timestamps = timestamps if timestamps is not None else [int(datetime(2026, 11, 19, 20, tzinfo=timezone.utc).timestamp())]
    prices = prices if prices is not None else [42.5]
    return json.dumps({"chart": {"error": None, "result": [{"meta": {"symbol": symbol, "currency": currency},
                       "timestamp": timestamps, "indicators": {"quote": [{"close": prices}]}}]}}).encode()


class YahooSecundarioTest(unittest.TestCase):
    def test_cierre_observado_no_es_ppp(self):
        r = interpretar_cierre(payload(), "WALMEX.MX", "2026-11-19")
        self.assertEqual(r["valor"], 42.5)
        self.assertEqual(r["estado"], "NO_OFICIAL_NO_VALIDADO")
        self.assertNotIn("ppp_bmv_mxn", r)
        self.assertEqual(len(r["sha256_respuesta"]), 64)

    def test_no_infiere_simbolo_moneda_fecha_ni_cierre(self):
        for raw, fecha in [(payload(symbol="AMXB.MX"), "2026-11-19"),
                           (payload(currency="USD"), "2026-11-19"),
                           (payload(), "2026-11-18"),
                           (payload(prices=[None]), "2026-11-19"),
                           (payload(prices=[float("nan")]), "2026-11-19"),
                           (payload(prices=[True]), "2026-11-19")]:
            with self.subTest(fecha=fecha, raw=raw), self.assertRaises(ValueError):
                interpretar_cierre(raw, "WALMEX.MX", fecha)

    def test_falla_si_hay_duplicados_o_arreglos_incompletos(self):
        instante = int(datetime(2026, 11, 19, 20, tzinfo=timezone.utc).timestamp())
        for raw in [payload(timestamps=[instante, instante + 1], prices=[2, 3]),
                    payload(timestamps=[instante], prices=[])]:
            with self.assertRaises(ValueError):
                interpretar_cierre(raw, "WALMEX.MX", "2026-11-19")


if __name__ == "__main__":
    unittest.main()
