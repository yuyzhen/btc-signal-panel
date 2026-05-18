from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from ai_advisor import AIAdvisor
from binance_client import BinanceClient, BinanceClientError
from signal_engine import build_market_snapshot, build_rule_signal, normalize_signal


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
SYMBOL = "BTCUSDT"


class SignalService:
    def __init__(self) -> None:
        self.client = BinanceClient()
        self.advisor = AIAdvisor()
        self.last_good_payload: dict | None = None

    def get_signal(self) -> dict:
        try:
            raw = self.client.fetch_market_bundle(SYMBOL)
            snapshot = build_market_snapshot(raw)
            rule_signal = build_rule_signal(snapshot)
            ai_signal = self.advisor.advise(snapshot, rule_signal)
            final_signal = normalize_signal(ai_signal or rule_signal)
            payload = {
                "ok": True,
                "symbol": SYMBOL,
                "ai_configured": self.advisor.configured,
                "ai_error": self.advisor.last_error,
                "snapshot": snapshot,
                "rule_signal": rule_signal,
                "signal": final_signal,
                "source": "ai" if ai_signal else "rules",
            }
            self.last_good_payload = payload
            return payload
        except BinanceClientError as exc:
            return self._error_payload(f"Binance data error: {exc}")
        except Exception as exc:  # Keep the panel alive during unexpected failures.
            return self._error_payload(f"Unexpected error: {exc}")

    def _error_payload(self, message: str) -> dict:
        return {
            "ok": False,
            "error": message,
            "symbol": SYMBOL,
            "last_good_payload": self.last_good_payload,
        }


service = SignalService()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/signal":
            self._send_json(service.get_signal())
            return
        if parsed.path == "/health":
            self._send_json({"ok": True, "symbol": SYMBOL})
            return
        super().do_GET()

    def log_message(self, format: str, *args) -> None:
        print(f"[btc-signal-panel] {self.address_string()} - {format % args}")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    port = int(os.getenv("PORT", "8765"))
    server = ReusableThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"BTC signal panel running at http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
