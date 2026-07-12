import unittest
from src.services.market_data import resolve_metric_consensus, validate_grounded_metric

class TestProviderConsensus(unittest.TestCase):

    def test_consensus_close_values_pass(self):
        raw_vals = {
            "yFinance": 15.42,
            "Finnhub": 15.39,
            "Screener": 15.45
        }
        health = {
            "yFinance": "HEALTHY",
            "Finnhub": "HEALTHY",
            "Screener": "HEALTHY"
        }
        
        # PE ratio has tolerance of 5% (0.05). Diff is (15.45 - 15.39)/15.45 = ~0.38%, so it should PASS.
        res = resolve_metric_consensus("pe_ratio", raw_vals, health)
        self.assertEqual(res["validation_status"], "PASS")
        self.assertEqual(res["confidence"], 1.0)
        self.assertEqual(res["selected_provider"], "Screener")  # Screener is preferred over yFinance/Finnhub in registry

    def test_consensus_mismatch_warning(self):
        raw_vals = {
            "yFinance": 10.0,
            "Finnhub": 20.0
        }
        health = {
            "yFinance": "HEALTHY",
            "Finnhub": "HEALTHY"
        }
        
        # Difference is 100% which exceeds 5% tolerance
        res = resolve_metric_consensus("pe_ratio", raw_vals, health)
        self.assertEqual(res["validation_status"], "WARNING")
        self.assertEqual(res["confidence"], 0.5)

    def test_consensus_unhealthy_provider_ignored(self):
        raw_vals = {
            "yFinance": 10.0,
            "Finnhub": 20.0
        }
        health = {
            "yFinance": "HEALTHY",
            "Finnhub": "RATE_LIMITED"
        }
        
        # Finnhub is ignored, leaving only yFinance -> SINGLE_SOURCE
        res = resolve_metric_consensus("pe_ratio", raw_vals, health)
        self.assertEqual(res["validation_status"], "SINGLE_SOURCE")
        # Starting confidence for SINGLE_SOURCE is 0.8.
        # Because Finnhub is unhealthy/ignored, confidence receives a penalty of -0.1 -> 0.7
        self.assertEqual(res["confidence"], 0.7)
        self.assertEqual(res["value"], 10.0)

    def test_consensus_all_providers_missing(self):
        raw_vals = {
            "yFinance": None,
            "Finnhub": None
        }
        health = {
            "yFinance": "UNAVAILABLE",
            "Finnhub": "TIMEOUT"
        }
        
        res = resolve_metric_consensus("pe_ratio", raw_vals, health)
        self.assertEqual(res["validation_status"], "MISSING")
        self.assertIsNone(res["value"])
        self.assertEqual(res["confidence"], 0.0)

    def test_validation_sanity_bounds(self):
        consensus_ok = {
            "value": 15.0,
            "source": "yFinance",
            "timestamp": "2026-07-09T00:00:00",
            "confidence": 1.0,
            "source_url": None,
            "raw_value": 15.0,
            "normalized_value": 15.0,
            "display_value": "15.00x",
            "validation_status": "PASS",
            "other_provider_values": {},
            "selected_provider": "yFinance",
            "validation_reason": "Ok"
        }
        
        res = validate_grounded_metric("pe_ratio", consensus_ok)
        self.assertEqual(res["validation_status"], "PASS")
        self.assertEqual(res["value"], 15.0)

        consensus_fail = consensus_ok.copy()
        consensus_fail["value"] = 1500.0  # Exceeds 1000.0 max
        consensus_fail["display_value"] = "1500.00x"
        
        res_fail = validate_grounded_metric("pe_ratio", consensus_fail)
        self.assertEqual(res_fail["validation_status"], "FAIL")
        self.assertIsNone(res_fail["value"])
        self.assertEqual(res_fail["display_value"], "Unavailable")

    def test_sector_aware_debt_to_equity(self):
        consensus_de = {
            "value": 4.5,
            "source": "yFinance",
            "timestamp": "2026-07-09T00:00:00",
            "confidence": 1.0,
            "source_url": None,
            "raw_value": 4.5,
            "normalized_value": 4.5,
            "display_value": "4.50x",
            "validation_status": "PASS",
            "other_provider_values": {},
            "selected_provider": "yFinance",
            "validation_reason": "Ok"
        }
        
        # For non-financial sector, 4.5 exceeds standard limit of 2.5
        res_non_fin = validate_grounded_metric("debt_to_equity", consensus_de, sector="Technology")
        self.assertEqual(res_non_fin["validation_status"], "FAIL")
        self.assertIsNone(res_non_fin["value"])

        # For financial sector, limit is expanded to 6.0, so 4.5 passes
        res_fin = validate_grounded_metric("debt_to_equity", consensus_de, sector="Financial Services")
        self.assertEqual(res_fin["validation_status"], "PASS")
        self.assertEqual(res_fin["value"], 4.5)

if __name__ == "__main__":
    unittest.main()
