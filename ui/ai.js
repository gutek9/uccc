const dropZone = document.getElementById("aiDropZone");
const fileInput = document.getElementById("aiCsvInput");
const errorEl = document.getElementById("aiError");
const resultsEl = document.getElementById("aiResults");
const fileMetaEl = document.getElementById("aiFileMeta");
const summaryMetaEl = document.getElementById("aiSummaryMeta");
const totalSpendEl = document.getElementById("aiTotalSpend");
const unknownToolsEl = document.getElementById("aiUnknownTools");
const totalValueEl = document.getElementById("aiTotalValue");
const netImpactEl = document.getElementById("aiNetImpact");
const hoursSavedEl = document.getElementById("aiHoursSaved");
const surveySizeEl = document.getElementById("aiSurveySize");
const costByToolEl = document.getElementById("aiCostByTool");
const hoursByFrequencyEl = document.getElementById("aiHoursByFrequency");
const topRoiEl = document.getElementById("aiTopRoi");
const assumptionsEl = document.getElementById("aiAssumptions");
const outputEl = document.getElementById("aiOutput");
const weeksPerMonthInput = document.getElementById("aiWeeksPerMonth");
const costPerHourInput = document.getElementById("aiCostPerHour");
const toolCostsListEl = document.getElementById("aiToolCosts");
const timeSavedListEl = document.getElementById("aiTimeSavedMap");
const addToolBtn = document.getElementById("aiAddTool");
const addTimeBtn = document.getElementById("aiAddTimeMap");

const MAX_ROWS = 50000;
const DEFAULT_CONFIG = {
  weeksPerMonth: 4.33,
  avgEngineerCostPerHour: 80,
  toolCosts: [
    { name: "Cursor", monthly_cost_usd: 20 },
    { name: "Claude Code (Anthropic)", monthly_cost_usd: 30 },
    { name: "GitHub Copilot", monthly_cost_usd: 19 },
    { name: "ChatGPT Plus", monthly_cost_usd: 20 },
    { name: "Antigravity", monthly_cost_usd: 0 },
  ],
  timeSavedMap: [
    { label: "Less than 1 hour", hours: 0.5 },
    { label: "0 - 1 hour", hours: 0.5 },
    { label: "1 - 3 hours", hours: 2 },
    { label: "3 - 5 hours", hours: 4 },
    { label: "More than 5 hours", hours: 6 },
    { label: "I do not feel they save me time", hours: 0 },
  ],
};

let lastParsedData = null;
let lastFilename = "";

function formatCost(value, currency = "USD") {
  const formatter = new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    notation: value >= 10000 ? "compact" : "standard",
    maximumFractionDigits: value >= 10000 ? 1 : 2,
  });
  return formatter.format(value);
}

function parseCSV(text) {
  const rows = [];
  let current = "";
  let row = [];
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];
    if (char === '"') {
      if (inQuotes && next === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === "," && !inQuotes) {
      row.push(current);
      current = "";
      continue;
    }
    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") {
        i += 1;
      }
      row.push(current);
      if (row.length > 1 || row[0].trim() !== "") {
        rows.push(row);
      }
      row = [];
      current = "";
      continue;
    }
    current += char;
  }
  if (current.length || row.length) {
    row.push(current);
    rows.push(row);
  }
  return rows;
}

function normalizeHeader(value) {
  return String(value || "")
    .replace(/^\uFEFF/, "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeTimeSaved(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[–—]/g, "-")
    .replace(/\s*-\s*/g, "-")
    .replace(/hours?/g, "hour")
    .replace(/hrs?/g, "hour")
    .replace(/[^a-z0-9+\-> ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function findColumn(headers, candidates) {
  const lowered = headers.map(normalizeHeader);
  for (const candidate of candidates) {
    const target = normalizeHeader(candidate);
    const index = lowered.findIndex((header) => header.includes(target));
    if (index !== -1) {
      return index;
    }
  }
  return -1;
}

function normalizeToolKey(value) {
  return normalizeHeader(value);
}

function normalizeToolName(value) {
  return String(value || "").trim();
}

function normalizeFrequency(value) {
  return String(value || "").trim();
}

function mapTimeSaved(value, timeSavedMap) {
  if (!value) {
    return { hours: 0, mapped: false };
  }
  const normalized = normalizeTimeSaved(value);
  if (timeSavedMap.has(normalized)) {
    return { hours: timeSavedMap.get(normalized), mapped: true };
  }
  return { hours: 0, mapped: false };
}

function normalizeToolAlias(tool) {
  const trimmed = normalizeToolName(tool);
  const aliasMap = {
    "ChatGPT (OpenAI)": "ChatGPT Plus",
    "Cursor CLI": "Cursor",
    "Codex CLI": "Codex (OpenAI)",
    "Gemini (https://gemini.google.com/)": "Gemini",
    "VSCode": "VS Code",
    "VSCode, Gemini AI": "Gemini AI",
  };
  return aliasMap[trimmed] || trimmed;
}

function renderBarList(container, rows, currency) {
  container.innerHTML = "";
  if (!rows.length) {
    container.innerHTML = '<div class="caption">No data</div>';
    return;
  }
  const maxValue = Math.max(...rows.map((row) => row.total), 1);
  const list = document.createElement("div");
  list.className = "bar-list";
  rows.forEach((row) => {
    const pct = Math.min(100, (row.total / maxValue) * 100);
    const item = document.createElement("div");
    item.className = "bar-row";
    item.innerHTML = `
      <div class="bar-meta"><span>${row.label}</span><strong>${formatCost(row.total, currency)}</strong></div>
      <div class="mini-bar-track"><div class="mini-bar-fill" style="width: ${pct.toFixed(1)}%"></div></div>
    `;
    list.appendChild(item);
  });
  container.appendChild(list);
}

function renderBarListNumeric(container, rows) {
  container.innerHTML = "";
  if (!rows.length) {
    container.innerHTML = '<div class="caption">No data</div>';
    return;
  }
  const maxValue = Math.max(...rows.map((row) => row.total), 1);
  const list = document.createElement("div");
  list.className = "bar-list";
  rows.forEach((row) => {
    const pct = Math.min(100, (row.total / maxValue) * 100);
    const item = document.createElement("div");
    item.className = "bar-row";
    item.innerHTML = `
      <div class="bar-meta"><span>${row.label}</span><strong>${row.total.toFixed(1)} hrs</strong></div>
      <div class="mini-bar-track"><div class="mini-bar-fill" style="width: ${pct.toFixed(1)}%"></div></div>
    `;
    list.appendChild(item);
  });
  container.appendChild(list);
}

function renderAssumptions(container, data) {
  container.innerHTML = "";
  const list = document.createElement("ul");
  list.className = "list-items";
  data.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  });
  container.appendChild(list);
}

function createConfigRow({ labelValue = "", numberValue = "", numberStep = "1", onChange }) {
  const row = document.createElement("div");
  row.className = "ai-config-row";

  const labelInput = document.createElement("input");
  labelInput.type = "text";
  labelInput.value = labelValue;
  labelInput.placeholder = "Label";

  const numberInput = document.createElement("input");
  numberInput.type = "number";
  numberInput.min = "0";
  numberInput.step = numberStep;
  numberInput.value = numberValue;
  numberInput.placeholder = "Value";

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "ai-remove-btn";
  removeBtn.textContent = "Remove";

  const handleInput = () => {
    if (typeof onChange === "function") {
      onChange();
    }
  };

  labelInput.addEventListener("input", handleInput);
  numberInput.addEventListener("input", handleInput);
  removeBtn.addEventListener("click", () => {
    row.remove();
    handleInput();
  });

  row.appendChild(labelInput);
  row.appendChild(numberInput);
  row.appendChild(removeBtn);
  return row;
}

function getConfigFromUI() {
  const weeksPerMonth = parseFloat(weeksPerMonthInput.value) || DEFAULT_CONFIG.weeksPerMonth;
  const avgEngineerCostPerHour =
    parseFloat(costPerHourInput.value) || DEFAULT_CONFIG.avgEngineerCostPerHour;

  const toolCosts = Array.from(toolCostsListEl.querySelectorAll(".ai-config-row")).map((row) => {
    const inputs = row.querySelectorAll("input");
    return {
      name: inputs[0].value.trim(),
      monthly_cost_usd: parseFloat(inputs[1].value) || 0,
    };
  });

  const timeSavedMap = Array.from(timeSavedListEl.querySelectorAll(".ai-config-row")).map(
    (row) => {
      const inputs = row.querySelectorAll("input");
      return {
        label: inputs[0].value.trim(),
        hours: parseFloat(inputs[1].value) || 0,
      };
    }
  );

  return {
    weeksPerMonth,
    avgEngineerCostPerHour,
    toolCosts: toolCosts.filter((entry) => entry.name),
    timeSavedMap: timeSavedMap.filter((entry) => entry.label),
  };
}

function applyDefaultConfig() {
  weeksPerMonthInput.value = DEFAULT_CONFIG.weeksPerMonth;
  costPerHourInput.value = DEFAULT_CONFIG.avgEngineerCostPerHour;
  toolCostsListEl.innerHTML = "";
  timeSavedListEl.innerHTML = "";

  DEFAULT_CONFIG.toolCosts.forEach((tool) => {
    toolCostsListEl.appendChild(
      createConfigRow({
        labelValue: tool.name,
        numberValue: tool.monthly_cost_usd,
        numberStep: "1",
        onChange: handleConfigChange,
      })
    );
  });

  DEFAULT_CONFIG.timeSavedMap.forEach((entry) => {
    timeSavedListEl.appendChild(
      createConfigRow({
        labelValue: entry.label,
        numberValue: entry.hours,
        numberStep: "0.1",
        onChange: handleConfigChange,
      })
    );
  });
}

function handleConfigChange() {
  if (lastParsedData) {
    summarizeSurvey(lastParsedData, lastFilename, getConfigFromUI());
  }
}

function updateError(message) {
  if (!message) {
    errorEl.classList.add("is-hidden");
    errorEl.textContent = "";
    return;
  }
  errorEl.textContent = message;
  errorEl.classList.remove("is-hidden");
}

function summarizeSurvey(data, filename, config) {
  const resolvedConfig = config || getConfigFromUI();
  const weeksPerMonth = resolvedConfig.weeksPerMonth;
  const avgEngineerCostPerHour = resolvedConfig.avgEngineerCostPerHour;
  const toolCostMap = new Map();
  const timeSavedLookup = new Map();

  resolvedConfig.toolCosts.forEach((tool) => {
    if (!tool.name) {
      return;
    }
    toolCostMap.set(normalizeToolKey(tool.name), tool.monthly_cost_usd || 0);
  });

  resolvedConfig.timeSavedMap.forEach((entry) => {
    if (!entry.label) {
      return;
    }
    timeSavedLookup.set(normalizeTimeSaved(entry.label), entry.hours || 0);
  });

  const headers = data[0] || [];
  const rows = data.slice(1, MAX_ROWS + 1);

  const toolsIndex = findColumn(headers, [
    "ai tools",
    "ai tools ides",
    "tools used",
    "tools",
    "ai tools used",
    "tool",
  ]);
  const frequencyIndex = findColumn(headers, [
    "frequency",
    "usage frequency",
    "how often",
    "usage",
    "frequently",
    "how frequently",
  ]);
  const timeSavedIndex = findColumn(headers, [
    "time saved",
    "time saved per week",
    "hours saved",
    "weekly time saved",
    "how much time",
    "save you per week",
  ]);
  const productivityIndex = findColumn(headers, ["productivity", "rating", "self reported", "likert"]);

  if (toolsIndex === -1 || frequencyIndex === -1 || timeSavedIndex === -1) {
    updateError(
      "Missing required columns. Include tools used, usage frequency, and time saved per week headers."
    );
    return;
  }

  const totalsByToolCost = new Map();
  const totalsByToolValue = new Map();
  const totalsByFrequency = new Map();
  const unknownTools = new Set();
  let totalCost = 0;
  let totalHoursWeekly = 0;
  let respondentCount = 0;
  let toolsCounted = 0;
  let missingTimeSaved = 0;
  let missingFrequency = 0;
  let unmappedTimeSaved = 0;

  rows.forEach((row) => {
    if (!row.length) {
      return;
    }
    const toolsCell = row[toolsIndex] || "";
    const frequency = normalizeFrequency(row[frequencyIndex]);
    const timeSavedRaw = row[timeSavedIndex];
    const timeSavedResult = mapTimeSaved(timeSavedRaw, timeSavedLookup);
    const weeklySaved = timeSavedResult.hours;
    if (!timeSavedRaw) {
      missingTimeSaved += 1;
    } else if (!timeSavedResult.mapped) {
      unmappedTimeSaved += 1;
    }
    const tools = toolsCell
      .split(";")
      .flatMap((entry) => entry.split(","))
      .map((tool) => normalizeToolName(tool))
      .filter((tool) => tool.length);

    respondentCount += 1;
    totalHoursWeekly += weeklySaved;

    if (frequency) {
      totalsByFrequency.set(
        frequency,
        (totalsByFrequency.get(frequency) || 0) + weeklySaved
      );
    } else {
      missingFrequency += 1;
    }

    const uniqueTools = new Set(tools);
    const toolList = Array.from(uniqueTools);
    if (!toolList.length) {
      return;
    }

    toolsCounted += toolList.length;

    toolList.forEach((tool) => {
      const normalizedTool = normalizeToolKey(tool);
      const aliasedTool = normalizeToolKey(normalizeToolAlias(tool));
      const hasCost = toolCostMap.has(normalizedTool) || toolCostMap.has(aliasedTool);
      const monthlyCost = toolCostMap.get(normalizedTool) || toolCostMap.get(aliasedTool) || 0;
      if (!hasCost) {
        unknownTools.add(tool);
      }
      totalsByToolCost.set(tool, (totalsByToolCost.get(tool) || 0) + monthlyCost);
      totalCost += monthlyCost;
    });

    if (weeklySaved > 0) {
      const monthlyValue = weeklySaved * weeksPerMonth * avgEngineerCostPerHour;
      const perToolValue = toolList.length ? monthlyValue / toolList.length : 0;
      toolList.forEach((tool) => {
        totalsByToolValue.set(tool, (totalsByToolValue.get(tool) || 0) + perToolValue);
      });
    }
  });

  const monthlyHoursSaved = totalHoursWeekly * weeksPerMonth;
  const totalValue = monthlyHoursSaved * avgEngineerCostPerHour;
  const netImpact = totalValue - totalCost;

  const toolCostRows = Array.from(totalsByToolCost.entries())
    .map(([label, total]) => ({ label, total }))
    .sort((a, b) => b.total - a.total);

  const frequencyRows = Array.from(totalsByFrequency.entries())
    .map(([label, total]) => ({ label, total: total * WEEKS_PER_MONTH }))
    .sort((a, b) => b.total - a.total);

  const roiRows = toolCostRows
    .map((row) => {
      const value = totalsByToolValue.get(row.label) || 0;
      const roi = row.total > 0 ? (value - row.total) / row.total : null;
      return {
        label: row.label,
        total: value - row.total,
        value,
        cost: row.total,
        roi,
      };
    })
    .sort((a, b) => b.total - a.total)
    .slice(0, 6);

  updateError("");
  resultsEl.classList.remove("is-hidden");
  fileMetaEl.textContent = `${filename} - ${respondentCount} respondents`;
  summaryMetaEl.textContent = `Parsed ${respondentCount} responses${rows.length === MAX_ROWS ? " (showing first 50k)" : ""}.`;
  totalSpendEl.textContent = formatCost(totalCost, "USD");
  unknownToolsEl.textContent = `Unknown tools: ${unknownTools.size}`;
  totalValueEl.textContent = formatCost(totalValue, "USD");
  netImpactEl.textContent = `Net impact: ${formatCost(netImpact, "USD")}`;
  hoursSavedEl.textContent = monthlyHoursSaved.toFixed(1);
  surveySizeEl.textContent = `${respondentCount} respondents`;

  renderBarList(costByToolEl, toolCostRows, "USD");
  renderBarListNumeric(hoursByFrequencyEl, frequencyRows);

  topRoiEl.innerHTML = "";
  if (!roiRows.length) {
    topRoiEl.innerHTML = '<div class="caption">No ROI data</div>';
  } else {
    const list = document.createElement("div");
    list.className = "bar-list";
    const maxValue = Math.max(...roiRows.map((row) => Math.abs(row.total)), 1);
    roiRows.forEach((row) => {
      const pct = Math.min(100, (Math.abs(row.total) / maxValue) * 100);
      const item = document.createElement("div");
      item.className = "bar-row";
      const roiLabel = row.roi === null ? "N/A" : `${(row.roi * 100).toFixed(1)}%`;
      item.innerHTML = `
        <div class="bar-meta"><span>${row.label}</span><strong>${formatCost(row.total, "USD")} (${roiLabel})</strong></div>
        <div class="mini-bar-track"><div class="mini-bar-fill ${row.total < 0 ? "is-negative" : ""}" style="width: ${pct.toFixed(1)}%"></div></div>
      `;
      list.appendChild(item);
    });
    topRoiEl.appendChild(list);
  }

  const assumptionLines = [
    `Weeks per month: ${weeksPerMonth}`,
    `Average engineer cost per hour: ${formatCost(avgEngineerCostPerHour, "USD")}`,
    `Tool costs: ${resolvedConfig.toolCosts.length} configured`,
    `Unknown tool costs treated as USD 0`,
    `Weekly time saved uses configured midpoints`,
    `Monthly value allocated equally across tools used by each engineer`,
    `Results are directional estimates, not accounting-grade`,
  ];

  if (unknownTools.size) {
    assumptionLines.push(`Unknown tools detected: ${Array.from(unknownTools).join(", ")}`);
  }

  if (missingTimeSaved) {
    assumptionLines.push(`Missing time saved responses assumed 0: ${missingTimeSaved}`);
  }

  if (missingFrequency) {
    assumptionLines.push(`Missing usage frequency responses: ${missingFrequency}`);
  }

  if (unmappedTimeSaved) {
    assumptionLines.push(`Unmapped time saved responses assumed 0: ${unmappedTimeSaved}`);
  }

  renderAssumptions(assumptionsEl, assumptionLines);

  const output = {
    totals: {
      monthly_ai_spend_usd: Number(totalCost.toFixed(2)),
      monthly_hours_saved: Number(monthlyHoursSaved.toFixed(2)),
      monthly_value_saved_usd: Number(totalValue.toFixed(2)),
      net_impact_usd: Number(netImpact.toFixed(2)),
    },
    breakdowns: {
      cost_by_tool: toolCostRows.map((row) => ({
        tool: row.label,
        monthly_cost_usd: Number(row.total.toFixed(2)),
      })),
      hours_saved_by_frequency: frequencyRows.map((row) => ({
        frequency: row.label,
        monthly_hours_saved: Number(row.total.toFixed(2)),
      })),
      value_by_tool: toolCostRows.map((row) => ({
        tool: row.label,
        monthly_value_usd: Number(((totalsByToolValue.get(row.label) || 0)).toFixed(2)),
      })),
      top_tools_by_roi: roiRows.map((row) => ({
        tool: row.label,
        monthly_net_value_usd: Number(row.total.toFixed(2)),
        roi: row.roi === null ? null : Number(row.roi.toFixed(3)),
      })),
    },
    assumptions: {
      weeks_per_month: weeksPerMonth,
      average_engineer_cost_per_hour_usd: avgEngineerCostPerHour,
      time_saved_mapping_hours_per_week: resolvedConfig.timeSavedMap,
      tool_costs_usd: resolvedConfig.toolCosts,
      unknown_tools: Array.from(unknownTools),
      notes: [
        "Unknown tools default to USD 0 monthly cost.",
        "Time saved uses conservative midpoints.",
        "Monthly value allocated equally across tools used per engineer.",
        "Estimates are directional, not accounting-grade.",
      ],
    },
  };

  outputEl.textContent = JSON.stringify(output, null, 2);
}

function handleFile(file) {
  if (!file) {
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const text = reader.result;
    if (typeof text !== "string") {
      updateError("Unable to read file contents.");
      return;
    }
    const parsed = parseCSV(text);
    if (!parsed.length) {
      updateError("CSV appears to be empty.");
      return;
    }
    lastParsedData = parsed;
    lastFilename = file.name;
    summarizeSurvey(parsed, file.name, getConfigFromUI());
  };
  reader.onerror = () => {
    updateError("Failed to read file. Please try again.");
  };
  reader.readAsText(file);
}

if (dropZone) {
  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("is-dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("is-dragover");
  });

  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragover");
    const file = event.dataTransfer.files[0];
    handleFile(file);
  });
}

if (fileInput) {
  fileInput.addEventListener("change", (event) => {
    const file = event.target.files[0];
    handleFile(file);
    event.target.value = "";
  });
}

function initConfigPanel() {
  if (!weeksPerMonthInput || !costPerHourInput) {
    return;
  }
  applyDefaultConfig();

  weeksPerMonthInput.addEventListener("input", handleConfigChange);
  costPerHourInput.addEventListener("input", handleConfigChange);

  if (addToolBtn) {
    addToolBtn.addEventListener("click", () => {
      toolCostsListEl.appendChild(
        createConfigRow({
          labelValue: "",
          numberValue: "",
          numberStep: "1",
          onChange: handleConfigChange,
        })
      );
    });
  }

  if (addTimeBtn) {
    addTimeBtn.addEventListener("click", () => {
      timeSavedListEl.appendChild(
        createConfigRow({
          labelValue: "",
          numberValue: "",
          numberStep: "0.1",
          onChange: handleConfigChange,
        })
      );
    });
  }
}

initConfigPanel();
