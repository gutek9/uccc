const API_BASE = "http://localhost:8000";

const todayTotalEl = document.getElementById("todayTotal");
const weekTotalEl = document.getElementById("weekTotal");
const monthTotalEl = document.getElementById("monthTotal");
const todaySplitEl = document.getElementById("todaySplit");
const weekSplitEl = document.getElementById("weekSplit");
const monthSplitEl = document.getElementById("monthSplit");

const providerSummaryEl = document.getElementById("providerSummary");
const breakdownServicesEl = document.getElementById("breakdownServices");
const breakdownAccountsEl = document.getElementById("breakdownAccounts");
const servicePageEl = document.getElementById("servicePage");
const accountPageEl = document.getElementById("accountPage");
const pagerButtons = document.querySelectorAll(".pager-btn");
const tabButtons = document.querySelectorAll(".tab-btn");
const anomaliesEl = document.getElementById("anomalies");
const freshnessEl = document.getElementById("freshnessList");
const sparklineEl = document.getElementById("costSparkline");
const topServicesEl = document.getElementById("topServices");
const topAccountsEl = document.getElementById("topAccounts");
const wowDeltaEl = document.getElementById("wowDelta");
const momDeltaEl = document.getElementById("momDelta");
const topServiceDeltasEl = document.getElementById("topServiceDeltas");
const topAccountDeltasEl = document.getElementById("topAccountDeltas");
const signalsListEl = document.getElementById("signalsList");
const errorBannerEl = document.getElementById("errorBanner");
const timelineHeatmapEl = document.getElementById("timelineHeatmap");
const timelineMetaEl = document.getElementById("timelineMeta");

const fromInput = document.getElementById("fromDate");
const toInput = document.getElementById("toDate");
const refreshBtn = document.getElementById("refreshBtn");
const searchInput = document.getElementById("searchInput");
const SERVICE_PAGE_SIZE = 10;
const ACCOUNT_PAGE_SIZE = 10;
let servicePageIndex = 0;
let accountPageIndex = 0;
const filterState = {
  provider: "aws",
  from: "",
  to: "",
  search: "",
};
const TIMELINE_DAYS = 14;
const ANOMALY_RATIO_THRESHOLD = 0.3;
const ANOMALY_IMPACT_THRESHOLD = 200;

function formatCost(value, currency = "USD") {
  const formatter = new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    notation: value >= 10000 ? "compact" : "standard",
    maximumFractionDigits: value >= 10000 ? 1 : 2,
  });
  return formatter.format(value);
}

function toISODate(value) {
  return value.toISOString().slice(0, 10);
}

function toDateOnly(value) {
  const date = new Date(value);
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function buildCompareRange(fromDate, toDate) {
  if (!fromDate || !toDate) {
    return null;
  }
  const start = toDateOnly(fromDate);
  const end = toDateOnly(toDate);
  const diffDays = Math.max(0, Math.round((end - start) / 86400000));
  const compareEnd = new Date(start.getTime() - 86400000);
  const compareStart = new Date(compareEnd.getTime() - diffDays * 86400000);
  return {
    compare_from: toISODate(compareStart),
    compare_to: toISODate(compareEnd),
  };
}

async function fetchJson(path) {
  const apiKey = localStorage.getItem("uccc_api_key");
  const response = await fetch(`${API_BASE}${path}`, {
    headers: apiKey ? { "X-API-Key": apiKey } : {},
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch ${path}`);
  }
  return response.json();
}

function renderList(container, rows, emptyLabel = "No data") {
  container.innerHTML = "";
  if (!Array.isArray(rows)) {
    container.innerHTML = `<li>${emptyLabel}</li>`;
    return;
  }
  if (!rows.length) {
    container.innerHTML = `<li>${emptyLabel}</li>`;
    return;
  }
  rows.forEach((row) => {
    const li = document.createElement("li");
    const label = row.key ?? row.provider ?? "—";
    const currency = row.currency || "USD";
    li.innerHTML = `<span>${label}</span><strong>${formatCost(row.total_cost, currency)}</strong>`;
    container.appendChild(li);
  });
}

function renderFreshness(rows) {
  freshnessEl.innerHTML = "";
  if (!rows.length) {
    freshnessEl.innerHTML = "<div class=\"freshness-item\"><strong>—</strong><span>No data yet</span></div>";
    return;
  }
  rows.forEach((row) => {
    const card = document.createElement("div");
    card.className = "freshness-item";
    const date = row.last_entry_date ? formatShortDate(row.last_entry_date) : "—";
    const ingested = row.last_ingested_at ? formatDateTime(row.last_ingested_at) : "—";
    const lookback = row.lookback_days ? `Rolling window: ${row.lookback_days} days` : "Rolling window: unknown";
    card.innerHTML = `<strong>${row.provider}</strong><span>Latest cost day: ${date}</span><span>Last ingested: ${ingested}</span><em>${lookback}</em>`;
    freshnessEl.appendChild(card);
  });
}

function formatShortDate(value) {
  const date = new Date(value);
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatDateTime(value) {
  const date = new Date(value);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDayLabel(value) {
  const date = new Date(value);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function buildDayLabels(startDate, count) {
  const days = [];
  for (let idx = 0; idx < count; idx += 1) {
    const day = new Date(startDate.getTime() + idx * 86400000);
    days.push(toISODate(day));
  }
  return days;
}

function median(values) {
  if (!values.length) {
    return 0;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) {
    return (sorted[mid - 1] + sorted[mid]) / 2;
  }
  return sorted[mid];
}

function renderTimeline(rows, provider, currency = "USD") {
  if (!timelineHeatmapEl || !timelineMetaEl) {
    return;
  }
  timelineHeatmapEl.innerHTML = "";
  const today = toDateOnly(new Date());
  const start = new Date(today.getTime() - (TIMELINE_DAYS - 1) * 86400000);
  const days = buildDayLabels(start, TIMELINE_DAYS);
  const providerRows = rows.filter((row) => row.provider === provider);
  const byDate = providerRows.reduce((acc, row) => {
    acc[row.date] = row;
    return acc;
  }, {});
  const totals = providerRows.map((row) => row.total_cost || 0);
  const baseline = median(totals);
  days.forEach((day) => {
    const item = byDate[day];
    const cell = document.createElement("button");
    cell.className = "timeline-cell";
    cell.type = "button";
    if (!item) {
      cell.classList.add("is-muted");
      cell.textContent = formatDayLabel(day);
      timelineHeatmapEl.appendChild(cell);
      return;
    }
    const impact = item.previous_day_cost === null || item.previous_day_cost === undefined ? 0 : item.total_cost - item.previous_day_cost;
    const ratio = item.delta_ratio || 0;
    if (ratio >= ANOMALY_RATIO_THRESHOLD && impact >= ANOMALY_IMPACT_THRESHOLD) {
      cell.classList.add(ratio >= ANOMALY_RATIO_THRESHOLD * 2 ? "is-high" : "is-medium");
    } else if (ratio >= ANOMALY_RATIO_THRESHOLD) {
      cell.classList.add("is-low");
    }
    cell.textContent = formatDayLabel(day);
    const pct = ratio ? `${(ratio * 100).toFixed(1)}%` : "—";
    cell.title = `${day} · ${formatCost(item.total_cost || 0, currency)} · Δ ${formatCost(impact, currency)} (${pct})`;
    cell.addEventListener("click", () => {
      filterState.from = day;
      filterState.to = day;
      fromInput.value = day;
      toInput.value = day;
      servicePageIndex = 0;
      accountPageIndex = 0;
      refreshData();
    });
    timelineHeatmapEl.appendChild(cell);
  });
  const baselineLabel = baseline ? `${formatCost(baseline, currency)} median` : "—";
  timelineMetaEl.textContent = `Baseline: ${baselineLabel} · Highlight: ≥${Math.round(
    ANOMALY_RATIO_THRESHOLD * 100
  )}% & ≥${formatCost(ANOMALY_IMPACT_THRESHOLD, currency)}`;
}

function renderAnomalies(rows) {
  anomaliesEl.innerHTML = "";
  if (!rows.length) {
    anomaliesEl.innerHTML = "<li>No anomalies detected</li>";
    return;
  }
  rows.forEach((row) => {
    const li = document.createElement("li");
    const pct = row.delta_ratio ? `${(row.delta_ratio * 100).toFixed(1)}%` : "—";
    li.innerHTML = `<span>${row.provider} · ${row.date}</span><strong>${formatCost(row.total_cost)} (${pct})</strong>`;
    anomaliesEl.appendChild(li);
  });
}

function renderSummarySplit(container, rows, highlightKey = null) {
  container.innerHTML = "";
  if (!rows.length) {
    container.innerHTML = "<div class=\"summary-chip\"><strong>—</strong><span>No data</span></div>";
    return;
  }
  rows.forEach((row) => {
    const chip = document.createElement("div");
    chip.className = "summary-chip";
    const label = row.key ?? row.provider ?? "—";
    const currency = row.currency || "USD";
    chip.innerHTML = `<strong>${label}</strong><span>${formatCost(row.total_cost, currency)}</span>`;
    if (highlightKey && label === highlightKey) {
      chip.classList.add("is-active");
    }
    container.appendChild(chip);
  });
}

function buildQuery(params) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    const trimmed = typeof value === "string" ? value.trim() : value;
    if (trimmed === "") {
      return;
    }
    searchParams.set(key, trimmed);
  });
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

function setActiveProvider(provider) {
  filterState.provider = provider;
  tabButtons.forEach((button) => button.classList.remove("is-active"));
  const match = Array.from(tabButtons).find((btn) => btn.dataset.provider === provider);
  if (match) {
    match.classList.add("is-active");
  }
}

function renderSparkline(points) {
  sparklineEl.innerHTML = "";
  if (!points.length) {
    return;
  }
  const width = 300;
  const height = 120;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const step = width / (points.length - 1 || 1);
  const path = points
    .map((value, idx) => {
      const x = idx * step;
      const y = height - ((value - min) / range) * (height - 10) - 5;
      return `${idx === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
  line.setAttribute("d", path);
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", "#e35137");
  line.setAttribute("stroke-width", "2");
  sparklineEl.appendChild(line);
}

function renderSignals(rows, currencyMap, freshnessMap) {
  signalsListEl.innerHTML = "";
  if (!rows || !rows.length) {
    signalsListEl.innerHTML = "<div class=\"signal-card\"><div class=\"meta\">No critical signals</div></div>";
    return;
  }
  const filtered = rows.filter((signal) => signal && signal.provider && signal.entity_id);
  if (!filtered.length) {
    signalsListEl.innerHTML = "<div class=\"signal-card\"><div class=\"meta\">No critical signals</div></div>";
    return;
  }
  filtered.forEach((signal) => {
    const card = document.createElement("div");
    const currency = currencyMap[signal.provider] || "USD";
    card.className = `signal-card ${signal.severity === "high" ? "is-high" : ""}`;
    const pct = signal.impact_pct ? `${(signal.impact_pct * 100).toFixed(1)}%` : "—";
    const impact = Number.isFinite(signal.impact_cost) ? signal.impact_cost : 0;
    const range =
      signal.timeframe && signal.timeframe.start && signal.timeframe.end
        ? `${formatShortDate(signal.timeframe.start)} → ${formatShortDate(signal.timeframe.end)}`
        : "—";
    const freshnessDate = freshnessMap && freshnessMap[signal.provider] ? formatShortDate(freshnessMap[signal.provider]) : null;
    const freshnessNote = freshnessDate ? `Data through ${freshnessDate}` : null;
    const label = `${signal.provider} · ${signal.entity_type}: ${signal.entity_id}`;
    card.innerHTML = `
      <strong>${label}</strong>
      <div class="impact">${formatCost(impact, currency)} (${pct})</div>
      <div class="meta">${range}</div>
      ${freshnessNote ? `<div class="meta">${freshnessNote}</div>` : ""}
      ${signal.root_cause_hint ? `<div class="meta">${signal.root_cause_hint}</div>` : ""}
    `;
    card.addEventListener("click", () => {
      setActiveProvider(signal.provider);
      if (signal.timeframe && signal.timeframe.start && signal.timeframe.end) {
        filterState.from = signal.timeframe.start;
        filterState.to = signal.timeframe.end;
        fromInput.value = signal.timeframe.start;
        toInput.value = signal.timeframe.end;
      }
      if (signal.entity_id) {
        filterState.search = signal.entity_id;
        searchInput.value = signal.entity_id;
      }
      servicePageIndex = 0;
      accountPageIndex = 0;
      refreshData();
    });
    signalsListEl.appendChild(card);
  });
}
function renderDeltaList(container, rows, currency = "USD", emptyLabel = "No data") {
  container.innerHTML = "";
  if (!Array.isArray(rows)) {
    container.innerHTML = `<li>${emptyLabel}</li>`;
    return;
  }
  if (!rows.length) {
    container.innerHTML = `<li>${emptyLabel}</li>`;
    return;
  }
  rows.forEach((row) => {
    const li = document.createElement("li");
    const pct = row.delta_ratio === null ? "—" : `${(row.delta_ratio * 100).toFixed(1)}%`;
    const sign = row.delta >= 0 ? "+" : "";
    li.innerHTML = `<span>${row.key}</span><strong>${sign}${formatCost(row.delta, currency)} (${pct})</strong>`;
    container.appendChild(li);
  });
}

function formatDelta(current, previous, currency = "USD") {
  const delta = current - previous;
  const ratio = previous === 0 ? null : delta / previous;
  const sign = delta >= 0 ? "+" : "";
  const pct = ratio === null ? "—" : `${(ratio * 100).toFixed(1)}%`;
  return `${sign}${formatCost(delta, currency)} (${pct})`;
}

function syncFilterStateFromInputs() {
  filterState.from = fromInput.value;
  filterState.to = toInput.value;
  filterState.search = searchInput.value.trim();
}

function getPrevMonthStart() {
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
  return toISODate(start);
}

function getPrevMonthEnd() {
  const today = new Date();
  const end = new Date(today.getFullYear(), today.getMonth(), 0);
  return toISODate(end);
}

function getProviderTotal(rows, provider) {
  const match = rows.find((row) => row.provider === provider);
  return match ? match.total_cost : 0;
}

async function refreshData() {
  syncFilterStateFromInputs();
  const fromDate = filterState.from;
  const toDate = filterState.to;
  const rangeQuery = buildQuery({ from: fromDate, to: toDate });
  if (errorBannerEl) {
    errorBannerEl.classList.add("is-hidden");
    errorBannerEl.textContent = "";
  }

  const today = toISODate(new Date());
  const todayQuery = `?from=${today}&to=${today}`;
  const weekStart = new Date();
  weekStart.setDate(weekStart.getDate() - 6);
  const weekQuery = `?from=${toISODate(weekStart)}&to=${today}`;
  const monthStart = new Date();
  monthStart.setDate(1);
  const monthQuery = `?from=${toISODate(monthStart)}&to=${today}`;
  const compareRange = buildCompareRange(fromDate, toDate);
  const timelineStart = toISODate(new Date(Date.now() - (TIMELINE_DAYS - 1) * 86400000));
  const timelineQuery = `?from=${timelineStart}&to=${today}`;

  try {
    const serviceOffset = servicePageIndex * SERVICE_PAGE_SIZE;
    const accountOffset = accountPageIndex * ACCOUNT_PAGE_SIZE;
    const [
      todayTotal,
      weekTotal,
      monthTotal,
      todayByProvider,
      weekByProvider,
      monthByProvider,
      providerTotalsRange,
      topServices,
      topAccounts,
      trendRows,
      signals,
      breakdowns,
      prevWeekByProvider,
      prevMonthByProvider,
      serviceDeltas,
      accountDeltas,
      anomalies,
      timelineRows,
      freshness,
    ] = await Promise.all([
      fetchJson(`/costs/total${todayQuery}`),
      fetchJson(`/costs/total${weekQuery}`),
      fetchJson(`/costs/total${monthQuery}`),
      fetchJson(`/costs/provider-totals${todayQuery}`),
      fetchJson(`/costs/provider-totals${weekQuery}`),
      fetchJson(`/costs/provider-totals${monthQuery}`),
      fetchJson(`/costs/provider-totals${rangeQuery}`),
      fetchJson(
        `/costs/by-service${buildQuery({
          from: fromDate,
          to: toDate,
          provider: filterState.provider,
          search: filterState.search,
          limit: 5,
          offset: 0,
        })}`
      ),
      fetchJson(
        `/costs/by-account${buildQuery({
          from: fromDate,
          to: toDate,
          provider: filterState.provider,
          search: filterState.search,
          limit: 5,
          offset: 0,
        })}`
      ),
      fetchJson(`/costs/deltas${rangeQuery}`),
      fetchJson(`/signals${buildQuery({ from: fromDate, to: toDate, provider: filterState.provider })}`),
      fetchJson(
        `/costs/breakdowns${buildQuery({
          from: fromDate,
          to: toDate,
          provider: filterState.provider,
          search: filterState.search,
          limit: SERVICE_PAGE_SIZE,
          offset: serviceOffset,
          account_offset: accountOffset,
        })}`
      ),
      fetchJson(
        `/costs/provider-totals?from=${toISODate(new Date(Date.now() - 13 * 86400000))}&to=${toISODate(
          new Date(Date.now() - 7 * 86400000)
        )}`
      ),
      fetchJson(`/costs/provider-totals?from=${getPrevMonthStart()}&to=${getPrevMonthEnd()}`),
      fetchJson(
        `/costs/deltas/by-service${buildQuery({
          from: fromDate,
          to: toDate,
          compare_from: compareRange ? compareRange.compare_from : undefined,
          compare_to: compareRange ? compareRange.compare_to : undefined,
          provider: filterState.provider,
          search: filterState.search,
          limit: 5,
        })}`
      ),
      fetchJson(
        `/costs/deltas/by-account${buildQuery({
          from: fromDate,
          to: toDate,
          compare_from: compareRange ? compareRange.compare_from : undefined,
          compare_to: compareRange ? compareRange.compare_to : undefined,
          provider: filterState.provider,
          search: filterState.search,
          limit: 5,
        })}`
      ),
      fetchJson(`/costs/anomalies${buildQuery({ from: fromDate, to: toDate, provider: filterState.provider })}`),
      fetchJson(`/costs/deltas${timelineQuery}`),
      fetchJson(`/costs/freshness`),
    ]);

    todayTotalEl.textContent = formatCost(todayTotal.total_cost);
    weekTotalEl.textContent = formatCost(weekTotal.total_cost);
    monthTotalEl.textContent = formatCost(monthTotal.total_cost);
    renderSummarySplit(todaySplitEl, todayByProvider);
    renderSummarySplit(weekSplitEl, weekByProvider);
    renderSummarySplit(monthSplitEl, monthByProvider);

    const emptyLabel = filterState.search ? "No results" : "No data";
    renderSummarySplit(providerSummaryEl, providerTotalsRange, filterState.provider);
    renderList(topServicesEl, topServices, emptyLabel);
    renderList(topAccountsEl, topAccounts, emptyLabel);
    const currencyMap = providerTotalsRange.reduce((acc, row) => {
      acc[row.provider] = row.currency || "USD";
      return acc;
    }, {});
    const freshnessMap = freshness.reduce((acc, row) => {
      if (row.provider && row.last_entry_date) {
        acc[row.provider] = row.last_entry_date;
      }
      return acc;
    }, {});
    renderSignals(signals, currencyMap, freshnessMap);

    const trendTotals = {};
    trendRows.forEach((row) => {
      const key = row.date;
      trendTotals[key] = (trendTotals[key] || 0) + (row.total_cost || 0);
    });
    const trendPoints = Object.keys(trendTotals)
      .sort()
      .map((key) => trendTotals[key]);
    renderSparkline(trendPoints);

    const breakdown = breakdowns[0];
    renderList(breakdownServicesEl, breakdown ? breakdown.services : [], emptyLabel);
    renderList(breakdownAccountsEl, breakdown ? breakdown.accounts : [], emptyLabel);
    updatePagerButtons(breakdown);
    const activeCurrency = currencyMap[filterState.provider] || "USD";
    const activeWeekTotal = getProviderTotal(weekByProvider, filterState.provider);
    const activeMonthTotal = getProviderTotal(monthByProvider, filterState.provider);
    const activePrevWeekTotal = getProviderTotal(prevWeekByProvider, filterState.provider);
    const activePrevMonthTotal = getProviderTotal(prevMonthByProvider, filterState.provider);
    wowDeltaEl.textContent = formatDelta(activeWeekTotal, activePrevWeekTotal, activeCurrency);
    momDeltaEl.textContent = formatDelta(activeMonthTotal, activePrevMonthTotal, activeCurrency);
    renderDeltaList(topServiceDeltasEl, serviceDeltas, activeCurrency, emptyLabel);
    renderDeltaList(topAccountDeltasEl, accountDeltas, activeCurrency, emptyLabel);
    renderAnomalies(anomalies);
    renderTimeline(timelineRows, filterState.provider, activeCurrency);
    renderFreshness(freshness);
    servicePageEl.textContent = `Page ${servicePageIndex + 1}`;
    accountPageEl.textContent = `Page ${accountPageIndex + 1}`;
  } catch (error) {
    console.error(error);
    if (errorBannerEl) {
      errorBannerEl.textContent =
        "Data load failed. Check API availability and API key, then refresh. See console for details.";
      errorBannerEl.classList.remove("is-hidden");
    }
  }
}

function updatePagerButtons(breakdown) {
  const svcPrev = document.querySelector('.pager-btn[data-svc="prev"]');
  const svcNext = document.querySelector('.pager-btn[data-svc="next"]');
  const acctPrev = document.querySelector('.pager-btn[data-acct="prev"]');
  const acctNext = document.querySelector('.pager-btn[data-acct="next"]');
  const servicesCount = breakdown ? breakdown.services.length : 0;
  const accountsCount = breakdown ? breakdown.accounts.length : 0;

  svcPrev.disabled = servicePageIndex === 0;
  acctPrev.disabled = accountPageIndex === 0;
  svcNext.disabled = servicesCount < SERVICE_PAGE_SIZE;
  acctNext.disabled = accountsCount < ACCOUNT_PAGE_SIZE;
}

function initDateInputs() {
  const today = new Date();
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(today.getDate() - 30);
  fromInput.value = toISODate(thirtyDaysAgo);
  toInput.value = toISODate(today);
  filterState.from = fromInput.value;
  filterState.to = toInput.value;
}

refreshBtn.addEventListener("click", refreshData);
let searchDebounce = null;
searchInput.addEventListener("input", () => {
  if (searchDebounce) {
    clearTimeout(searchDebounce);
  }
  searchDebounce = setTimeout(() => {
    servicePageIndex = 0;
    accountPageIndex = 0;
    refreshData();
  }, 250);
});
pagerButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.svc === "prev") {
      servicePageIndex = Math.max(0, servicePageIndex - 1);
    } else if (btn.dataset.svc === "next") {
      servicePageIndex += 1;
    }
    if (btn.dataset.acct === "prev") {
      accountPageIndex = Math.max(0, accountPageIndex - 1);
    } else if (btn.dataset.acct === "next") {
      accountPageIndex += 1;
    }
    refreshData();
  });
});

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    setActiveProvider(btn.dataset.provider);
    servicePageIndex = 0;
    accountPageIndex = 0;
    refreshData();
  });
});

initDateInputs();
refreshData();
