from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class BinanceClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class BinanceClient:
    base_url: str = "https://fapi.binance.com"
    timeout: float = 10.0

    def fetch_market_bundle(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "klines": {
                "1m": self.klines(symbol, "1m", 240),
                "5m": self.klines(symbol, "5m", 240),
                "15m": self.klines(symbol, "15m", 240),
                "1h": self.klines(symbol, "1h", 240),
            },
            "depth": self.depth(symbol, 100),
            "agg_trades": self.agg_trades(symbol, 500),
            "premium_index": self.premium_index(symbol),
            "open_interest": self.open_interest(symbol),
        }

    def klines(self, symbol: str, interval: str, limit: int) -> list[list[Any]]:
        return self._get("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})

    def depth(self, symbol: str, limit: int) -> dict[str, Any]:
        return self._get("/fapi/v1/depth", {"symbol": symbol, "limit": limit})

    def agg_trades(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        return self._get("/fapi/v1/aggTrades", {"symbol": symbol, "limit": limit})

    def premium_index(self, symbol: str) -> dict[str, Any]:
        return self._get("/fapi/v1/premiumIndex", {"symbol": symbol})

    def open_interest(self, symbol: str) -> dict[str, Any]:
        return self._get("/fapi/v1/openInterest", {"symbol": symbol})

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.base_url}{path}?{urlencode(params)}"
        req = Request(url, headers={"User-Agent": "btc-signal-panel/1.0"})
        try:
            with urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise BinanceClientError(f"{path} returned HTTP {exc.code}: {details}") from exc
        except URLError as exc:
            raise BinanceClientError(f"{path} network failure: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise BinanceClientError(f"{path} returned invalid JSON") from exc
