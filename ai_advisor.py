from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from signal_engine import normalize_signal


class AIAdvisor:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.configured = bool(self.api_key)
        self.last_error: str | None = None

    def advise(self, snapshot: dict[str, Any], rule_signal: dict[str, Any]) -> dict[str, Any] | None:
        self.last_error = None
        if not self.configured:
            return None
        prompt = {
            "task": "你是 BTCUSDT 永续合约日内短线风控型交易辅助。只基于结构化快照输出条件式计划，不要承诺必涨必跌，不要给仓位建议，不要自动下单。",
            "required_schema": {
                "bias": "long | short | neutral",
                "confidence": "0-100 integer",
                "entry_condition": "string",
                "invalid_if": "string",
                "stop_loss_reference": "string",
                "take_profit_reference": "string",
                "risk_notes": ["string"],
                "plain_language_reason": "string",
            },
            "market_snapshot": compact_snapshot(snapshot),
            "rule_signal": rule_signal,
        }
        try:
            response = self._call_openai(prompt)
            return normalize_signal(response)
        except Exception as exc:
            self.last_error = str(exc)
            return None

    def _call_openai(self, prompt: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(prompt, ensure_ascii=False),
                        }
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "btc_signal",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "bias": {"type": "string", "enum": ["long", "short", "neutral"]},
                            "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                            "entry_condition": {"type": "string"},
                            "invalid_if": {"type": "string"},
                            "stop_loss_reference": {"type": "string"},
                            "take_profit_reference": {"type": "string"},
                            "risk_notes": {"type": "array", "items": {"type": "string"}},
                            "plain_language_reason": {"type": "string"},
                        },
                        "required": [
                            "bias",
                            "confidence",
                            "entry_condition",
                            "invalid_if",
                            "stop_loss_reference",
                            "take_profit_reference",
                            "risk_notes",
                            "plain_language_reason",
                        ],
                    },
                }
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = Request(
            "https://api.openai.com/v1/responses",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "btc-signal-panel/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {details}") from exc
        except URLError as exc:
            raise RuntimeError(f"OpenAI network failure: {exc.reason}") from exc

        text = extract_output_text(data)
        if not text:
            raise RuntimeError("OpenAI response did not include output text")
        return json.loads(text)


def extract_output_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "".join(chunks)


def compact_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": snapshot["symbol"],
        "current_price": round(snapshot["current_price"], 2),
        "mark_price": round(snapshot["mark_price"], 2),
        "funding_rate": snapshot["funding_rate"],
        "open_interest": snapshot["open_interest"],
        "intervals": {
            name: {
                "trend": data["trend"],
                "close": round(data["close"], 2),
                "ema20": round(data["ema20"], 2),
                "ema50": round(data["ema50"], 2),
                "vwap": round(data["vwap"], 2),
                "rsi14": round(data["rsi14"], 2),
                "macd_histogram": round(data["macd"]["histogram"], 2),
                "atr_pct": round(data["atr_pct"], 4),
                "swing_high_30": round(data["swing_high_30"], 2),
                "swing_low_30": round(data["swing_low_30"], 2),
                "volume_ratio": round(data["volume_ratio"], 2),
            }
            for name, data in snapshot["intervals"].items()
        },
        "order_book": {
            "imbalance": round(snapshot["order_book"]["imbalance"], 4),
            "spread": round(snapshot["order_book"]["spread"], 2),
        },
        "trade_flow": {
            "delta": round(snapshot["trade_flow"]["delta"], 4),
            "total_qty": round(snapshot["trade_flow"]["total_qty"], 3),
        },
        "risks": snapshot["risks"],
    }
