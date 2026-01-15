const API_BASE = "http://localhost:8000";

const todayTotalEl = document.getElementById("todayTotal");
const weekTotalEl = document.getElementById("weekTotal");
const monthTotalEl = document.getElementById("monthTotal");

const byProviderEl = document.getElementById("byProvider");
const byServiceAwsEl = document.getElementById("byServiceAws");
const byServiceAzureEl = document.getElementById("byServiceAzure");
const byServiceGcpEl = document.getElementById("byServiceGcp");
const byAccountAwsEl = document.getElementById("byAccountAws");
const byAccountAzureEl = document.getElementById("byAccountAzure");
const byAccountGcpEl = document.getElementById("byAccountGcp");
const servicePageEl = document.getElementById("servicePage");
const pagerButtons = document.querySelectorAll(".pager-btn");
const anomaliesEl = document.getElementById("anomalies");
const tagCoverageEl = document.getElementById("tagCoverage");
const freshnessEl = document.getElementById("freshnessList");
const barFully = document.getElementById("barFully");
const barPartial = document.getElementById("barPartial");
const barUntagged = document.getElementById("barUntagged");
const untaggedTable = document.getElementById("untaggedTable");

const fromInput = document.getElementById("fromDate");
const toInput = document.getElementById("toDate");
const refreshBtn = document.getElementById("refreshBtn");
const SERVICE_PAGE_SIZE = 10;
let servicePageIndex = 0;

function formatCost(value) {
  return `$${value.toFixed(2)}`;
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

function renderList(container, rows) {
  container.innerHTML = "";
  if (!rows.length) {
    container.innerHTML = "<li>No data</li>";
    return;
  }
  rows.forEach((row) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${row.key}</span><strong>${formatCost(row.total_cost)}</strong>`;
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

function renderTagCoverage(coverage) {
  const total = coverage.total_cost || 0;
  const fully = coverage.fully_tagged_cost || 0;
  const partial = coverage.partially_tagged_cost || 0;
  const untagged = coverage.untagged_cost || 0;

  tagCoverageEl.querySelector(".metric").textContent = formatCost(fully);

  const fullyPct = total ? (fully / total) * 100 : 0;
  const partialPct = total ? (partial / total) * 100 : 0;
  const untaggedPct = total ? (untagged / total) * 100 : 0;

  barFully.style.width = `${fullyPct.toFixed(1)}%`;
  barPartial.style.width = `${partialPct.toFixed(1)}%`;
  barUntagged.style.width = `${untaggedPct.toFixed(1)}%`;
}

function renderUntagged(entries) {
  untaggedTable.innerHTML = "";
  const rows = entries.slice(0, 12);
  if (!rows.length) {
    untaggedTable.innerHTML = `<tr><td colspan="6">No untagged costs</td></tr>`;
    return;
  }
  rows.forEach((entry) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${entry.date}</td>
      <td>${entry.provider}</td>
      <td>${entry.account_id}</td>
      <td>${entry.service}</td>
      <td>${formatCost(entry.cost)}</td>
      <td>${entry.missing_tags.join(", ") || "—"}</td>
    `;
    untaggedTable.appendChild(tr);
  });
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
    const offset = servicePageIndex * SERVICE_PAGE_SIZE;
    const [
      todayTotal,
      weekTotal,
      monthTotal,
      byProvider,
      byServiceAws,
      byServiceAzure,
      byServiceGcp,
      byAccountAws,
      byAccountAzure,
      byAccountGcp,
      tagHygiene,
      anomalies,
      freshness,
    ] = await Promise.all([
      fetchJson(`/costs/total${todayQuery}`),
      fetchJson(`/costs/total${weekQuery}`),
      fetchJson(`/costs/total${monthQuery}`),
      fetchJson(`/costs/by-provider${rangeQuery}`),
      fetchJson(`/costs/by-service${rangeQuery}&provider=aws&limit=${SERVICE_PAGE_SIZE}&offset=${offset}`),
      fetchJson(`/costs/by-service${rangeQuery}&provider=azure&limit=${SERVICE_PAGE_SIZE}&offset=${offset}`),
      fetchJson(`/costs/by-service${rangeQuery}&provider=gcp&limit=${SERVICE_PAGE_SIZE}&offset=${offset}`),
      fetchJson(`/costs/by-account${rangeQuery}&provider=aws`),
      fetchJson(`/costs/by-account${rangeQuery}&provider=azure`),
      fetchJson(`/costs/by-account${rangeQuery}&provider=gcp`),
      fetchJson(`/costs/tag-hygiene${rangeQuery}`),
      fetchJson(`/costs/anomalies${rangeQuery}`),
      fetchJson(`/costs/freshness`),
    ]);

    todayTotalEl.textContent = formatCost(todayTotal.total_cost);
    weekTotalEl.textContent = formatCost(weekTotal.total_cost);
    monthTotalEl.textContent = formatCost(monthTotal.total_cost);

    renderList(byProviderEl, byProvider);
    renderList(byServiceAwsEl, byServiceAws);
    renderList(byServiceAzureEl, byServiceAzure);
    renderList(byServiceGcpEl, byServiceGcp);
    renderList(byAccountAwsEl, byAccountAws);
    renderList(byAccountAzureEl, byAccountAzure);
    renderList(byAccountGcpEl, byAccountGcp);
    renderTagCoverage(tagHygiene.coverage);
    renderUntagged(tagHygiene.untagged_entries);
    renderAnomalies(anomalies);
    renderFreshness(freshness);
    servicePageEl.textContent = `Page ${servicePageIndex + 1}`;
  } catch (error) {
    console.error(error);
  }
}

function initDateInputs() {
  const today = new Date();
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(today.getDate() - 30);
  fromInput.value = toISODate(thirtyDaysAgo);
  toInput.value = toISODate(today);
}

refreshBtn.addEventListener("click", refreshData);
pagerButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.svc === "prev") {
      servicePageIndex = Math.max(0, servicePageIndex - 1);
    } else {
      servicePageIndex += 1;
    }
    refreshData();
  });
});

initDateInputs();
refreshData();
