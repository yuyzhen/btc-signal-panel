const DEFAULT_REFRESH_SECONDS = 60;
const MIN_REFRESH_SECONDS = 1;
const MAX_REFRESH_SECONDS = 60;
const logItems = [];
let refreshSeconds = DEFAULT_REFRESH_SECONDS;
let secondsLeft = refreshSeconds;
let isFetching = false;

const $ = (id) => document.getElementById(id);

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatPct(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

function biasText(bias) {
  return { long: "偏多", short: "偏空", neutral: "观望" }[bias] || "观望";
}

function trendText(trend) {
  return { bullish: "多头", bearish: "空头", mixed: "混合" }[trend] || "未知";
}

function clampRefreshSeconds(value) {
  const numericValue = Number.parseInt(value, 10);
  if (Number.isNaN(numericValue)) return DEFAULT_REFRESH_SECONDS;
  return Math.max(MIN_REFRESH_SECONDS, Math.min(MAX_REFRESH_SECONDS, numericValue));
}

function updateRefreshDisplay() {
  $("refreshSecondsLabel").textContent = `${refreshSeconds} 秒`;
  $("countdown").textContent = `${secondsLeft}s`;
}

function setupRefreshSlider() {
  const slider = $("refreshSlider");
  slider.value = `${refreshSeconds}`;
  slider.addEventListener("input", () => {
    refreshSeconds = clampRefreshSeconds(slider.value);
    secondsLeft = Math.min(secondsLeft, refreshSeconds);
    if (secondsLeft < 1) secondsLeft = refreshSeconds;
    updateRefreshDisplay();
  });
  updateRefreshDisplay();
}

async function fetchSignal() {
  if (isFetching) return;
  isFetching = true;
  $("refreshStatus").textContent = "刷新中";
  try {
    const response = await fetch("/api/signal", { cache: "no-store" });
    const payload = await response.json();
    if (!payload.ok) {
      showError(payload.error || "数据刷新失败");
      if (payload.last_good_payload) renderPayload(payload.last_good_payload, true);
      return;
    }
    hideError();
    renderPayload(payload, false);
  } catch (error) {
    showError(`请求失败：${error.message}`);
  } finally {
    secondsLeft = refreshSeconds;
    updateRefreshDisplay();
    $("refreshStatus").textContent = `上次刷新 ${new Date().toLocaleTimeString()}`;
    isFetching = false;
  }
}

function renderPayload(payload, stale) {
  const { snapshot, signal } = payload;
  $("aiStatus").textContent = payload.ai_configured
    ? payload.ai_error
      ? "AI 调用失败，已回退规则层"
      : payload.source === "ai"
        ? "AI 已启用"
        : "AI 回退规则层"
    : "AI 未配置，规则层运行";
  $("currentPrice").textContent = `$${formatNumber(snapshot.current_price, 2)}`;
  $("fundingRate").textContent = formatPct(snapshot.funding_rate, 4);
  $("openInterest").textContent = formatNumber(snapshot.open_interest, 0);

  const pill = $("biasPill");
  pill.textContent = biasText(signal.bias);
  pill.className = `pill ${signal.bias}`;
  $("confidence").textContent = `${signal.confidence}`;
  $("reason").textContent = signal.plain_language_reason;
  $("entryCondition").textContent = signal.entry_condition;
  $("invalidIf").textContent = signal.invalid_if;
  $("stopLoss").textContent = signal.stop_loss_reference;
  $("takeProfit").textContent = signal.take_profit_reference;

  $("bookImbalance").textContent = `${(snapshot.order_book.imbalance * 100).toFixed(2)}%`;
  $("tradeDelta").textContent = `${(snapshot.trade_flow.delta * 100).toFixed(2)}%`;
  $("bestBidAsk").textContent = `${formatNumber(snapshot.order_book.best_bid, 2)} / ${formatNumber(snapshot.order_book.best_ask, 2)}`;

  renderRisks(signal.risk_notes);
  renderIntervals(snapshot.intervals);
  pushLog(signal, snapshot.current_price, stale);
}

function renderRisks(risks) {
  $("riskList").innerHTML = "";
  risks.forEach((risk) => {
    const li = document.createElement("li");
    li.textContent = risk;
    $("riskList").appendChild(li);
  });
}

function renderIntervals(intervals) {
  const grid = $("intervalGrid");
  grid.innerHTML = "";
  Object.entries(intervals).forEach(([name, data]) => {
    const card = document.createElement("article");
    card.className = "interval-card";
    card.innerHTML = `
      <strong>${name} · ${trendText(data.trend)}</strong>
      <dl>
        <div><span>EMA20/50</span><b>${formatNumber(data.ema20, 1)} / ${formatNumber(data.ema50, 1)}</b></div>
        <div><span>VWAP</span><b>${formatNumber(data.vwap, 1)}</b></div>
        <div><span>RSI14</span><b>${formatNumber(data.rsi14, 1)}</b></div>
        <div><span>ATR%</span><b>${formatNumber(data.atr_pct, 3)}%</b></div>
        <div><span>量比</span><b>${formatNumber(data.volume_ratio, 2)}</b></div>
      </dl>
    `;
    grid.appendChild(card);
  });
}

function pushLog(signal, price, stale) {
  logItems.unshift({
    time: new Date().toLocaleTimeString(),
    bias: biasText(signal.bias),
    confidence: signal.confidence,
    price,
    reason: stale ? "使用最近一次有效数据" : signal.plain_language_reason,
  });
  logItems.splice(12);
  const log = $("signalLog");
  log.innerHTML = "";
  logItems.forEach((item) => {
    const row = document.createElement("div");
    row.className = "log-item";
    row.innerHTML = `
      <span>${item.time}</span>
      <strong>${item.bias} ${item.confidence}</strong>
      <span>$${formatNumber(item.price, 2)} · ${item.reason}</span>
    `;
    log.appendChild(row);
  });
}

function showError(message) {
  const box = $("errorBox");
  box.textContent = message;
  box.classList.remove("hidden");
}

function hideError() {
  $("errorBox").classList.add("hidden");
}

setupRefreshSlider();

setInterval(() => {
  if (isFetching) return;
  secondsLeft = Math.max(0, secondsLeft - 1);
  updateRefreshDisplay();
  if (secondsLeft === 0) fetchSignal();
}, 1000);

fetchSignal();
