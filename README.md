# BTC Signal Panel

本地 BTCUSDT 永续合约 AI 辅助信号面板。第一版只读取 Binance USD-M Futures 公开行情数据，不接账户、不保存私钥、不自动下单。

## 功能

- 固定标的：`BTCUSDT`
- 固定刷新：前端每 60 秒请求一次 `/api/signal`
- 数据源：K 线、深度盘口、近期聚合成交、资金费率、持仓量
- 指标：EMA20/EMA50、VWAP、RSI14、MACD、ATR14、关键高低点、盘口 imbalance、成交 delta
- 输出：多 / 空 / 观望、置信度、入场条件、失效条件、止损参考、止盈参考、风险提示
- AI：设置 `OPENAI_API_KEY` 后启用；未设置时使用规则层输出并显示“AI 未配置”

## 启动

```powershell
python app.py
```

然后打开：

```text
http://127.0.0.1:8765
```

可选环境变量：

```powershell
$env:OPENAI_API_KEY="sk-..."
$env:OPENAI_MODEL="gpt-4o-mini"
$env:PORT="8765"
python app.py
```

## 测试

```powershell
python -m unittest discover -s tests
```

## 风险说明

本项目只做交易辅助，不构成投资建议。AI 输出不是“必涨/必跌”判断，不提供固定仓位建议，不自动下单。任何开单、加仓、止损、止盈都需要人工确认。
