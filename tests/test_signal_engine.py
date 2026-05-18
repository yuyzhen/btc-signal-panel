import unittest

from signal_engine import (
    atr,
    build_market_snapshot,
    build_rule_signal,
    depth_imbalance,
    ema,
    normalize_signal,
    rsi,
    vwap,
)


def make_kline(index: int, close: float) -> list:
    high = close + 10
    low = close - 10
    open_price = close - 2
    volume = 100 + index
    return [index, str(open_price), str(high), str(low), str(close), str(volume), index + 1]


def make_bundle(direction: float = 1.0) -> dict:
    closes = [60000 + direction * i * 12 for i in range(260)]
    klines = {interval: [make_kline(i, close) for i, close in enumerate(closes[-240:])] for interval in ["1m", "5m", "15m", "1h"]}
    return {
        "symbol": "BTCUSDT",
        "klines": klines,
        "depth": {
            "bids": [["63000", "5"], ["62990", "4"]],
            "asks": [["63010", "2"], ["63020", "2"]],
        },
        "agg_trades": [
            {"q": "1.5", "m": False},
            {"q": "1.2", "m": False},
            {"q": "0.4", "m": True},
        ],
        "premium_index": {"lastFundingRate": "0.0001", "markPrice": "63100"},
        "open_interest": {"openInterest": "12345"},
    }


class IndicatorTests(unittest.TestCase):
    def test_ema_tracks_latest_direction(self):
        values = [1, 2, 3, 4, 5]
        self.assertGreater(ema(values, 3), 3)

    def test_rsi_bounds(self):
        values = list(range(1, 40))
        self.assertGreaterEqual(rsi(values), 0)
        self.assertLessEqual(rsi(values), 100)

    def test_atr_and_vwap_positive(self):
        candles = [
            {"high": 110, "low": 90, "close": 100, "volume": 10},
            {"high": 115, "low": 95, "close": 105, "volume": 20},
        ]
        self.assertGreater(atr(candles, 2), 0)
        self.assertGreater(vwap(candles, 2), 0)

    def test_depth_imbalance(self):
        depth = {"bids": [["100", "2"]], "asks": [["101", "1"]]}
        result = depth_imbalance(depth)
        self.assertGreater(result["imbalance"], 0)


class SignalTests(unittest.TestCase):
    def test_snapshot_and_rule_signal_shape(self):
        snapshot = build_market_snapshot(make_bundle())
        signal = build_rule_signal(snapshot)
        self.assertIn(signal["bias"], {"long", "short", "neutral"})
        self.assertGreaterEqual(signal["confidence"], 0)
        self.assertLessEqual(signal["confidence"], 100)
        self.assertTrue(signal["entry_condition"])
        self.assertTrue(signal["risk_notes"])

    def test_normalize_signal_fills_missing_fields(self):
        signal = normalize_signal({"bias": "long", "confidence": 120})
        self.assertEqual(signal["bias"], "long")
        self.assertEqual(signal["confidence"], 100)
        self.assertTrue(signal["plain_language_reason"])

    def test_conflicting_flow_can_neutralize(self):
        bundle = make_bundle()
        bundle["depth"] = {"bids": [["63000", "1"]], "asks": [["63010", "10"]]}
        bundle["agg_trades"] = [{"q": "3", "m": False}]
        snapshot = build_market_snapshot(bundle)
        signal = build_rule_signal(snapshot)
        self.assertIn(signal["bias"], {"long", "short", "neutral"})


if __name__ == "__main__":
    unittest.main()
