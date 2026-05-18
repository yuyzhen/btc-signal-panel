from __future__ import annotations

from statistics import mean
from typing import Any


BIAS_VALUES = {"long", "short", "neutral"}
SIGNAL_KEYS = {
    "bias",
    "confidence",
    "entry_condition",
    "invalid_if",
    "stop_loss_reference",
    "take_profit_reference",
    "risk_notes",
    "plain_language_reason",
}


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = (value * alpha) + (result * (1 - alpha))
    return result


def rsi(values: list[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0
    gains: list[float] = []
    losses: list[float] = []
    for prev, cur in zip(values[-period - 1 : -1], values[-period:]):
        change = cur - prev
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))
    avg_gain = mean(gains) if gains else 0.0
    avg_loss = mean(losses) if losses else 0.0
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(klines: list[dict[str, float]], period: int = 14) -> float:
    if len(klines) <= 1:
        return 0.0
    trs: list[float] = []
    recent = klines[-period:]
    previous_close = klines[-period - 1]["close"] if len(klines) > period else klines[0]["close"]
    for candle in recent:
        high = candle["high"]
        low = candle["low"]
        tr = max(high - low, abs(high - previous_close), abs(low - previous_close))
        trs.append(tr)
        previous_close = candle["close"]
    return mean(trs) if trs else 0.0


def vwap(klines: list[dict[str, float]], period: int = 50) -> float:
    recent = klines[-period:]
    volume_sum = sum(c["volume"] for c in recent)
    if volume_sum == 0:
        return recent[-1]["close"] if recent else 0.0
    pv = sum(((c["high"] + c["low"] + c["close"]) / 3) * c["volume"] for c in recent)
    return pv / volume_sum


def macd(values: list[float]) -> dict[str, float]:
    if not values:
        return {"line": 0.0, "signal": 0.0, "histogram": 0.0}
    line_values: list[float] = []
    for index in range(1, len(values) + 1):
        prefix = values[:index]
        line_values.append(ema(prefix, 12) - ema(prefix, 26))
    line = line_values[-1]
    signal = ema(line_values, 9)
    return {"line": line, "signal": signal, "histogram": line - signal}


def parse_klines(raw_klines: list[list[Any]]) -> list[dict[str, float]]:
    candles: list[dict[str, float]] = []
    for item in raw_klines:
        candles.append(
            {
                "open_time": as_float(item[0]),
                "open": as_float(item[1]),
                "high": as_float(item[2]),
                "low": as_float(item[3]),
                "close": as_float(item[4]),
                "volume": as_float(item[5]),
                "close_time": as_float(item[6]),
            }
        )
    return candles


def trend_state(close: float, ema20: float, ema50: float, vw: float) -> str:
    if close > ema20 > ema50 and close > vw:
        return "bullish"
    if close < ema20 < ema50 and close < vw:
        return "bearish"
    return "mixed"


def depth_imbalance(depth: dict[str, Any]) -> dict[str, float]:
    bids = depth.get("bids", [])
    asks = depth.get("asks", [])
    bid_notional = sum(as_float(price) * as_float(qty) for price, qty in bids)
    ask_notional = sum(as_float(price) * as_float(qty) for price, qty in asks)
    total = bid_notional + ask_notional
    imbalance = ((bid_notional - ask_notional) / total) if total else 0.0
    best_bid = as_float(bids[0][0]) if bids else 0.0
    best_ask = as_float(asks[0][0]) if asks else 0.0
    spread = best_ask - best_bid if best_bid and best_ask else 0.0
    return {
        "bid_notional": bid_notional,
        "ask_notional": ask_notional,
        "imbalance": imbalance,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
    }


def trade_delta(agg_trades: list[dict[str, Any]]) -> dict[str, float]:
    buy_qty = 0.0
    sell_qty = 0.0
    for trade in agg_trades:
        qty = as_float(trade.get("q"))
        if trade.get("m"):
            sell_qty += qty
        else:
            buy_qty += qty
    total = buy_qty + sell_qty
    delta = ((buy_qty - sell_qty) / total) if total else 0.0
    return {"buy_qty": buy_qty, "sell_qty": sell_qty, "delta": delta, "total_qty": total}


def summarize_interval(candles: list[dict[str, float]]) -> dict[str, Any]:
    closes = [c["close"] for c in candles]
    latest = candles[-1]
    ema20 = ema(closes[-80:], 20)
    ema50 = ema(closes[-120:], 50)
    vw = vwap(candles, 50)
    current_atr = atr(candles, 14)
    current_rsi = rsi(closes, 14)
    current_macd = macd(closes[-120:])
    recent = candles[-30:]
    return {
        "close": latest["close"],
        "ema20": ema20,
        "ema50": ema50,
        "vwap": vw,
        "rsi14": current_rsi,
        "macd": current_macd,
        "atr14": current_atr,
        "atr_pct": (current_atr / latest["close"] * 100) if latest["close"] else 0.0,
        "swing_high_30": max(c["high"] for c in recent),
        "swing_low_30": min(c["low"] for c in recent),
        "volume_ratio": volume_ratio(candles),
        "trend": trend_state(latest["close"], ema20, ema50, vw),
    }


def volume_ratio(candles: list[dict[str, float]], lookback: int = 30) -> float:
    if len(candles) <= lookback:
        return 1.0
    recent_volume = candles[-1]["volume"]
    baseline = mean(c["volume"] for c in candles[-lookback - 1 : -1])
    return recent_volume / baseline if baseline else 1.0


def build_market_snapshot(raw: dict[str, Any]) -> dict[str, Any]:
    interval_summaries = {
        interval: summarize_interval(parse_klines(raw["klines"][interval]))
        for interval in ("1m", "5m", "15m", "1h")
    }
    current_price = interval_summaries["1m"]["close"]
    depth = depth_imbalance(raw.get("depth", {}))
    trades = trade_delta(raw.get("agg_trades", []))
    premium = raw.get("premium_index", {})
    open_interest = raw.get("open_interest", {})
    funding_rate = as_float(premium.get("lastFundingRate"))
    mark_price = as_float(premium.get("markPrice"), current_price)
    oi = as_float(open_interest.get("openInterest"))
    risks = detect_risks(interval_summaries, depth, trades, funding_rate)
    return {
        "timestamp": int(interval_summaries["1m"].get("close", 0)),
        "symbol": raw.get("symbol", "BTCUSDT"),
        "current_price": current_price,
        "mark_price": mark_price,
        "intervals": interval_summaries,
        "order_book": depth,
        "trade_flow": trades,
        "funding_rate": funding_rate,
        "open_interest": oi,
        "risks": risks,
    }


def detect_risks(
    intervals: dict[str, dict[str, Any]],
    depth: dict[str, float],
    trades: dict[str, float],
    funding_rate: float,
) -> list[str]:
    risks: list[str] = []
    one_min = intervals["1m"]
    five_min = intervals["5m"]
    if one_min["atr_pct"] > 0.45:
        risks.append("1m 波动明显偏高，追单容易被扫。")
    if five_min["atr_pct"] > 1.2:
        risks.append("5m 波动过高，建议降低信号权重。")
    if abs(funding_rate) > 0.0005:
        risks.append("资金费率偏离较大，留意拥挤方向反抽。")
    if abs(depth["imbalance"]) < 0.04 and abs(trades["delta"]) < 0.04:
        risks.append("盘口和成交流方向不明显。")
    if depth["spread"] / one_min["close"] > 0.0002:
        risks.append("盘口价差偏大，短线滑点风险上升。")
    return risks


def build_rule_signal(snapshot: dict[str, Any]) -> dict[str, Any]:
    intervals = snapshot["intervals"]
    price = snapshot["current_price"]
    one = intervals["1m"]
    five = intervals["5m"]
    fifteen = intervals["15m"]
    hour = intervals["1h"]
    order_flow = snapshot["order_book"]["imbalance"]
    trade_flow = snapshot["trade_flow"]["delta"]

    score = 0.0
    reasons: list[str] = []
    for name, data, weight in [
        ("1m", one, 0.75),
        ("5m", five, 1.2),
        ("15m", fifteen, 1.4),
        ("1h", hour, 1.0),
    ]:
        if data["trend"] == "bullish":
            score += weight
            reasons.append(f"{name} 趋势偏多")
        elif data["trend"] == "bearish":
            score -= weight
            reasons.append(f"{name} 趋势偏空")
        else:
            reasons.append(f"{name} 结构混合")

    if five["macd"]["histogram"] > 0 and fifteen["macd"]["histogram"] > 0:
        score += 0.8
        reasons.append("5m/15m MACD 动量同向偏多")
    elif five["macd"]["histogram"] < 0 and fifteen["macd"]["histogram"] < 0:
        score -= 0.8
        reasons.append("5m/15m MACD 动量同向偏空")

    if order_flow > 0.08:
        score += 0.7
        reasons.append("盘口买盘厚度占优")
    elif order_flow < -0.08:
        score -= 0.7
        reasons.append("盘口卖盘厚度占优")

    if trade_flow > 0.08:
        score += 0.7
        reasons.append("近期主动买入占优")
    elif trade_flow < -0.08:
        score -= 0.7
        reasons.append("近期主动卖出占优")

    if five["rsi14"] > 72:
        score -= 0.4
        reasons.append("5m RSI 偏热，不适合追多")
    elif five["rsi14"] < 28:
        score += 0.4
        reasons.append("5m RSI 偏冷，不适合追空")

    conflict = is_conflicted(five, fifteen, order_flow, trade_flow)
    risk_penalty = min(len(snapshot["risks"]) * 7, 21)
    abs_score = abs(score)
    confidence = int(max(25, min(88, 42 + abs_score * 9 - risk_penalty)))

    if conflict or abs_score < 1.8:
        bias = "neutral"
        confidence = min(confidence, 55)
    else:
        bias = "long" if score > 0 else "short"

    return normalize_signal(
        {
            "bias": bias,
            "confidence": confidence,
            "entry_condition": entry_condition(bias, price, five, fifteen),
            "invalid_if": invalid_condition(bias, five),
            "stop_loss_reference": stop_reference(bias, price, five),
            "take_profit_reference": take_profit_reference(bias, price, five),
            "risk_notes": snapshot["risks"] or ["未发现强制观望风险，但仍需等待条件触发。"],
            "plain_language_reason": "；".join(reasons[:8]),
        }
    )


def is_conflicted(five: dict[str, Any], fifteen: dict[str, Any], order_flow: float, trade_flow: float) -> bool:
    trend_conflict = {five["trend"], fifteen["trend"]} == {"bullish", "bearish"}
    flow_conflict = (order_flow > 0.08 and trade_flow < -0.08) or (order_flow < -0.08 and trade_flow > 0.08)
    return trend_conflict or flow_conflict


def entry_condition(bias: str, price: float, five: dict[str, Any], fifteen: dict[str, Any]) -> str:
    if bias == "long":
        return f"价格守住 5m VWAP {five['vwap']:.2f}，并放量突破 15m 关键高点 {fifteen['swing_high_30']:.2f} 后再考虑多单。"
    if bias == "short":
        return f"价格跌破 5m VWAP {five['vwap']:.2f}，并放量失守 15m 关键低点 {fifteen['swing_low_30']:.2f} 后再考虑空单。"
    return "等待 5m/15m 趋势和订单流同向后再评估，当前不追单。"


def invalid_condition(bias: str, five: dict[str, Any]) -> str:
    if bias == "long":
        return f"5m 收盘跌回 EMA50 {five['ema50']:.2f} 下方，或主动卖出持续占优。"
    if bias == "short":
        return f"5m 收盘站回 EMA50 {five['ema50']:.2f} 上方，或主动买入持续占优。"
    return "若出现放量突破/跌破并且盘口与成交流同步，再重新生成计划。"


def stop_reference(bias: str, price: float, five: dict[str, Any]) -> str:
    atr_value = five["atr14"]
    if bias == "long":
        return f"{max(five['swing_low_30'], price - 1.2 * atr_value):.2f} 附近，需结合实际入场价微调。"
    if bias == "short":
        return f"{min(five['swing_high_30'], price + 1.2 * atr_value):.2f} 附近，需结合实际入场价微调。"
    return "观望状态不设置止损；若入场，先定义失效价再下单。"


def take_profit_reference(bias: str, price: float, five: dict[str, Any]) -> str:
    atr_value = five["atr14"]
    if bias == "long":
        return f"第一目标 {price + 1.4 * atr_value:.2f}，第二目标参考 5m 前高 {five['swing_high_30']:.2f}。"
    if bias == "short":
        return f"第一目标 {price - 1.4 * atr_value:.2f}，第二目标参考 5m 前低 {five['swing_low_30']:.2f}。"
    return "观望状态不设置止盈；等待方向确认后再给目标位。"


def normalize_signal(signal: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: signal.get(key) for key in SIGNAL_KEYS}
    normalized["bias"] = normalized["bias"] if normalized["bias"] in BIAS_VALUES else "neutral"
    normalized["confidence"] = int(max(0, min(100, as_float(normalized["confidence"], 0))))
    for key in SIGNAL_KEYS - {"bias", "confidence", "risk_notes"}:
        if not normalized[key]:
            normalized[key] = "暂无。"
    risk_notes = normalized["risk_notes"]
    if isinstance(risk_notes, str):
        normalized["risk_notes"] = [risk_notes]
    elif not isinstance(risk_notes, list) or not risk_notes:
        normalized["risk_notes"] = ["暂无特殊风险提示。"]
    else:
        normalized["risk_notes"] = [str(item) for item in risk_notes]
    return normalized
