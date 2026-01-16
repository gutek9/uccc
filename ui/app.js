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

const fromInput = document.getElementById("fromDate");
const toInput = document.getElementById("toDate");
const refreshBtn = document.getElementById("refreshBtn");
const searchInput = document.getElementById("searchInput");
const SERVICE_PAGE_SIZE = 10;
const ACCOUNT_PAGE_SIZE = 10;
let servicePageIndex = 0;
let accountPageIndex = 0;
let activeProvider = "aws";

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

async function fetchJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${path}`);
  }
  return response.json();
}

function renderList(container, rows, filterTerm = "") {
  container.innerHTML = "";
  if (!rows.length) {
    container.innerHTML = "<li>No data</li>";
    return;
  }
  const filtered = filterTerm
    ? rows.filter((row) => (row.key || row.provider || "").toLowerCase().includes(filterTerm))
    : rows;
  if (!filtered.length) {
    container.innerHTML = "<li>No matches</li>";
    return;
  }
  filtered.forEach((row) => {
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

function buildRangeQuery(baseQuery, params) {
  const joiner = baseQuery ? "&" : "?";
  return `${baseQuery}${joiner}${params}`;
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

function renderDeltaList(container, rows, currency = "USD", filterTerm = "") {
  container.innerHTML = "";
  if (!rows.length) {
    container.innerHTML = "<li>No data</li>";
    return;
  }
  const filtered = filterTerm
    ? rows.filter((row) => (row.key || "").toLowerCase().includes(filterTerm))
    : rows;
  if (!filtered.length) {
    container.innerHTML = "<li>No matches</li>";
    return;
  }
  filtered.forEach((row) => {
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
  const fromDate = fromInput.value;
  const toDate = toInput.value;
  const rangeQuery = fromDate && toDate ? `?from=${fromDate}&to=${toDate}` : "";

  const today = toISODate(new Date());
  const todayQuery = `?from=${today}&to=${today}`;
  const weekStart = new Date();
  weekStart.setDate(weekStart.getDate() - 6);
  const weekQuery = `?from=${toISODate(weekStart)}&to=${today}`;
  const monthStart = new Date();
  monthStart.setDate(1);
  const monthQuery = `?from=${toISODate(monthStart)}&to=${today}`;

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
      breakdowns,
      prevWeekByProvider,
      prevMonthByProvider,
      serviceDeltas,
      accountDeltas,
      anomalies,
      freshness,
    ] = await Promise.all([
      fetchJson(`/costs/total${todayQuery}`),
      fetchJson(`/costs/total${weekQuery}`),
      fetchJson(`/costs/total${monthQuery}`),
      fetchJson(`/costs/provider-totals${todayQuery}`),
      fetchJson(`/costs/provider-totals${weekQuery}`),
      fetchJson(`/costs/provider-totals${monthQuery}`),
      fetchJson(`/costs/provider-totals${rangeQuery}`),
      fetchJson(`/costs/by-service${rangeQuery}&limit=5&offset=0`),
      fetchJson(`/costs/by-account${rangeQuery}&limit=5&offset=0`),
      fetchJson(`/costs/deltas${rangeQuery}`),
      fetchJson(
        `/costs/breakdowns${buildRangeQuery(
          rangeQuery,
          `provider=${activeProvider}&limit=${SERVICE_PAGE_SIZE}&offset=${serviceOffset}&account_offset=${accountOffset}`
        )}`
      ),
      fetchJson(
        `/costs/provider-totals?from=${toISODate(new Date(Date.now() - 13 * 86400000))}&to=${toISODate(
          new Date(Date.now() - 7 * 86400000)
        )}`
      ),
      fetchJson(`/costs/provider-totals?from=${getPrevMonthStart()}&to=${getPrevMonthEnd()}`),
      fetchJson(
        `/costs/deltas/by-service?from=${toISODate(new Date(Date.now() - 6 * 86400000))}&to=${toISODate(
          new Date()
        )}&compare_from=${toISODate(new Date(Date.now() - 13 * 86400000))}&compare_to=${toISODate(
          new Date(Date.now() - 7 * 86400000)
        )}&provider=${activeProvider}&limit=5`
      ),
      fetchJson(
        `/costs/deltas/by-account?from=${toISODate(new Date(Date.now() - 6 * 86400000))}&to=${toISODate(
          new Date()
        )}&compare_from=${toISODate(new Date(Date.now() - 13 * 86400000))}&compare_to=${toISODate(
          new Date(Date.now() - 7 * 86400000)
        )}&provider=${activeProvider}&limit=5`
      ),
      fetchJson(`/costs/anomalies${rangeQuery}`),
      fetchJson(`/costs/freshness`),
    ]);

    todayTotalEl.textContent = formatCost(todayTotal.total_cost);
    weekTotalEl.textContent = formatCost(weekTotal.total_cost);
    monthTotalEl.textContent = formatCost(monthTotal.total_cost);
    renderSummarySplit(todaySplitEl, todayByProvider);
    renderSummarySplit(weekSplitEl, weekByProvider);
    renderSummarySplit(monthSplitEl, monthByProvider);

    const searchTerm = searchInput.value.trim().toLowerCase();
    renderSummarySplit(providerSummaryEl, providerTotalsRange, activeProvider);
    renderList(topServicesEl, topServices, searchTerm);
    renderList(topAccountsEl, topAccounts, searchTerm);
    const currencyMap = providerTotalsRange.reduce((acc, row) => {
      acc[row.provider] = row.currency || "USD";
      return acc;
    }, {});

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
    renderList(breakdownServicesEl, breakdown ? breakdown.services : [], searchTerm);
    renderList(breakdownAccountsEl, breakdown ? breakdown.accounts : [], searchTerm);
    updatePagerButtons(breakdown);
    const activeCurrency = currencyMap[activeProvider] || "USD";
    const activeWeekTotal = getProviderTotal(weekByProvider, activeProvider);
    const activeMonthTotal = getProviderTotal(monthByProvider, activeProvider);
    const activePrevWeekTotal = getProviderTotal(prevWeekByProvider, activeProvider);
    const activePrevMonthTotal = getProviderTotal(prevMonthByProvider, activeProvider);
    wowDeltaEl.textContent = formatDelta(activeWeekTotal, activePrevWeekTotal, activeCurrency);
    momDeltaEl.textContent = formatDelta(activeMonthTotal, activePrevMonthTotal, activeCurrency);
    renderDeltaList(topServiceDeltasEl, serviceDeltas, activeCurrency, searchTerm);
    renderDeltaList(topAccountDeltasEl, accountDeltas, activeCurrency, searchTerm);
    renderAnomalies(anomalies);
    renderFreshness(freshness);
    servicePageEl.textContent = `Page ${servicePageIndex + 1}`;
    accountPageEl.textContent = `Page ${accountPageIndex + 1}`;
  } catch (error) {
    console.error(error);
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
}

refreshBtn.addEventListener("click", refreshData);
searchInput.addEventListener("input", () => {
  refreshData();
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
    tabButtons.forEach((button) => button.classList.remove("is-active"));
    btn.classList.add("is-active");
    activeProvider = btn.dataset.provider;
    servicePageIndex = 0;
    accountPageIndex = 0;
    refreshData();
  });
});

initDateInputs();
refreshData();
