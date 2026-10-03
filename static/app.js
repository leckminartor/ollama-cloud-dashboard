/* Ollama Cloud Dashboard - frontend logic */
"use strict";

const state = {
  models: [],
  sortKey: "output",
  sortDir: "asc",
  rate: "peak", // "peak" | "offpeak"
};

const $ = (id) => document.getElementById(id);

function fmtPrice(v) {
  if (v === null || v === undefined) return "–";
  return "$" + Number(v).toFixed(v < 0.1 ? 3 : 2).replace(/0+$/, "").replace(/\.$/, "");
}

function pctColor(pct) {
  if (pct >= 90) return "bad";
  if (pct >= 70) return "warn";
  return "";
}

function formatRelative(iso) {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const diffMs = t - Date.now();
  const abs = Math.abs(diffMs);
  const h = Math.floor(abs / 3600000);
  const m = Math.round((abs % 3600000) / 60000);
  let txt = h > 0 ? `${h} Std ${m} Min` : `${m} Min`;
  return diffMs >= 0 ? `Reset in ${txt}` : `Reset vor ${txt}`;
}

/* ---------------- models table ---------------- */

function priceFor(row, key) {
  if (state.rate === "offpeak") {
    return row["offpeak_" + key] !== undefined ? row["offpeak_" + key] : row[key];
  }
  return row[key];
}

function sortValue(row, key) {
  if (key === "name") return row.name.toLowerCase();
  if (key === "tags") return row.tags ? row.tags.join(",") : "";
  const v = priceFor(row, key);
  if (v !== null && v !== undefined) return v;
  // family row without own prices (e.g. gpt-oss): sort by its cheapest variant
  const vals = (row.variants || [])
    .map((vr) => priceFor(vr, key))
    .filter((x) => x !== null && x !== undefined)
    .map(Number);
  return vals.length ? Math.min(...vals) : Infinity;
}

function compareRows(a, b) {
  const dir = state.sortDir === "asc" ? 1 : -1;
  const va = sortValue(a, state.sortKey);
  const vb = sortValue(b, state.sortKey);
  if (va < vb) return -1 * dir;
  if (va > vb) return 1 * dir;
  return a.name.localeCompare(b.name) * dir;
}

function renderTable() {
  const body = $("models-body");
  body.textContent = "";
  if (!state.models.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 5;
    td.className = "muted";
    td.textContent = "Keine Modelle geladen.";
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }

  const rows = [...state.models].sort(compareRows);

  // header arrows
  document.querySelectorAll("#models-table th.sortable").forEach((th) => {
    const arrow = th.querySelector(".arrow");
    if (arrow) arrow.remove();
    if (th.dataset.key === state.sortKey) {
      const span = document.createElement("span");
      span.className = "arrow";
      span.textContent = state.sortDir === "asc" ? "▲" : "▼";
      th.appendChild(span);
    }
  });

  for (const row of rows) {
    body.appendChild(buildRow(row, false));
    const variants = [...(row.variants || [])].sort(compareRows);
    for (const v of variants) {
      body.appendChild(buildRow(v, true, row.name));
    }
  }
}

function buildRow(row, isVariant, parentName) {
  const tr = document.createElement("tr");
  if (isVariant) tr.className = "variants-block";

  const nameTd = document.createElement("td");
  nameTd.className = "model-name";
  nameTd.textContent = isVariant ? `↳ ${row.name}` : row.name;
  tr.appendChild(nameTd);

  const tagsTd = document.createElement("td");
  const tags = isVariant ? [] : row.tags || [];
  for (const t of tags) {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    chip.textContent = t;
    tagsTd.appendChild(chip);
  }
  tr.appendChild(tagsTd);

  for (const key of ["input", "cached", "output"]) {
    const td = document.createElement("td");
    td.className = "num";
    td.textContent = fmtPrice(priceFor(row, key));
    tr.appendChild(td);
  }
  return tr;
}

async function loadModels(force) {
  try {
    const url = "/api/models" + (force ? "?refresh=1" : "");
    const resp = await fetch(url);
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    state.models = data.models || [];
    $("models-error").classList.add("hidden");
    renderTable();
    $("last-update").textContent =
      "Modelle aktualisiert: " + new Date((data.fetched_at || Date.now() / 1000) * 1000).toLocaleTimeString("de-DE");
  } catch (err) {
    const box = $("models-error");
    box.textContent = "Fehler beim Laden der Modelle: " + err.message;
    box.classList.remove("hidden");
  }
}

/* ---------------- usage panel ---------------- */

function renderUsageCard(kind, data) {
  const bar = $("bar-" + kind);
  const pctEl = $("pct-" + kind);
  const resetEl = $("reset-" + kind);
  if (!data || data.pct === null || data.pct === undefined) {
    bar.style.width = "0%";
    bar.className = "bar";
    pctEl.textContent = "–";
    resetEl.textContent = "";
    return;
  }
  const pct = Math.round(data.pct * 10) / 10;
  bar.style.width = Math.min(pct, 100) + "%";
  bar.className = "bar " + pctColor(pct);
  pctEl.textContent = pct.toLocaleString("de-DE") + " %";

  // reset line: relative ("in 4 Std 12 Min") plus absolute local time when known
  let resetTxt;
  if (data.resets_at) {
    resetTxt = formatRelative(data.resets_at);
    const absTxt = new Intl.DateTimeFormat("de-DE", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(data.resets_at));
    resetTxt = resetTxt ? resetTxt + ` · um ${absTxt} Uhr` : `Reset um ${absTxt} Uhr`;
  } else {
    // /api/usage exposes no reset timestamps: the windows are sliding
    resetTxt = "kein fester Reset (Sliding-Window)";
  }
  resetEl.textContent = resetTxt;
}

async function loadUsage(force) {
  const srcEl = $("usage-source");
  const errEl = $("usage-error");
  const planBadge = $("plan-badge");
  try {
    const url = "/api/usage" + (force ? "?refresh=1" : "");
    const resp = await fetch(url);
    const data = await resp.json();
    renderUsageCard("session", data.session);
    renderUsageCard("weekly", data.weekly);

    if (data.plan) {
      planBadge.textContent = "Plan: " + data.plan;
      planBadge.classList.remove("hidden");
    } else {
      planBadge.classList.add("hidden");
    }

    if (data.source === "none") {
      srcEl.textContent = "keine Quelle verfügbar";
      errEl.textContent = data.error || "";
      errEl.classList.remove("hidden");
    } else {
      srcEl.textContent =
        "Quelle: " + (data.source === "api" ? "Ollama API" : "Settings-Cookie") +
        (data.error ? " (Fallback-Hinweis: " + data.error + ")" : "");
      errEl.classList.add("hidden");
    }
  } catch (err) {
    srcEl.textContent = "Fehler";
    errEl.textContent = "Usage konnte nicht geladen werden: " + err.message;
    errEl.classList.remove("hidden");
  }
}

/* ---------------- rate window (peak/off-peak) ---------------- */

/* Peak pricing applies 12:00–18:00 UTC on weekdays (Mon–Fri) — outside that
   window and on weekends it is off-peak. */
function nextPeakStart(now) {
  /* Next 12:00 UTC that falls on a weekday (skips weekend boundaries, where
     the phase does not actually change). */
  for (let i = 0; i < 8; i++) {
    const candidate = new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + i, 12, 0, 0)
    );
    if (candidate.getTime() > now.getTime()) {
      const wd = candidate.getUTCDay();
      if (wd !== 0 && wd !== 6) return candidate;
    }
  }
  return null; // unreachable within 8 days
}

function rateWindowAt(now) {
  const weekday = now.getUTCDay(); // 0 = Sunday
  const hour = now.getUTCHours();
  const isWeekend = weekday === 0 || weekday === 6;
  const isPeak = !isWeekend && hour >= 12 && hour < 18;

  const boundary = isPeak
    ? new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 18, 0, 0))
    : nextPeakStart(now);

  return {
    isPeak,
    untilText: boundary ? untilBoundaryText(now, boundary, isPeak) : "",
  };
}

function untilBoundaryText(now, boundary, isPeak) {
  const diff = Math.max(0, boundary.getTime() - now.getTime());
  const totalMin = Math.round(diff / 60000);
  const d = Math.floor(totalMin / 1440);
  const h = Math.floor((totalMin % 1440) / 60);
  const m = totalMin % 60;
  if (totalMin === 0) return "wenige Sekunden";
  const parts = [];
  if (d > 0) parts.push(d === 1 ? "1 Tag" : `${d} Tage`);
  if (h > 0) parts.push(`${h} Std`);
  if (d === 0 && m > 0) parts.push(`${m} Min`);
  const txt = parts.join(" ");
  return isPeak ? `Peak endet in ${txt}` : `Off-Peak endet in ${txt}`;
}

function renderRateWindow() {
  const badge = $("rate-window");
  const sub = $("rate-window-sub");
  const hint = $("rate-window-hint");
  const now = new Date();
  const { isPeak, untilText } = rateWindowAt(now);
  badge.textContent = isPeak ? "PEAK" : "OFF-PEAK";
  badge.className = "badge " + (isPeak ? "peak" : "offpeak");
  const localTime = now.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  sub.textContent = `Ortszeit ${localTime} · ${untilText}`;

  /* Static hint with the peak window in local time. Computed from today's
     date so it follows DST changes (CET vs CEST in Europe/Berlin). */
  const fmt = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
  const toLocal = (utcHour) => {
    const d = new Date();
    d.setUTCHours(utcHour, 0, 0, 0);
    return fmt.format(d);
  };
  const start = toLocal(12);
  const end = toLocal(18);
  hint.textContent = `Peak gilt an Wochentagen ${start}–${end} Ortszeit (12:00–18:00 UTC) außerhalb von Wochenenden. Preise pro 1 Mio. Tokens.`;
}

setInterval(renderRateWindow, 30000);

/* ---------------- wiring ---------------- */

document.querySelectorAll("#models-table th.sortable").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.key;
    if (state.sortKey === key) {
      state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
    } else {
      state.sortKey = key;
      state.sortDir = th.dataset.num ? "asc" : "asc";
    }
    renderTable();
  });
});

$("rate-peak").addEventListener("click", () => {
  state.rate = "peak";
  $("rate-peak").classList.add("active");
  $("rate-offpeak").classList.remove("active");
  renderTable();
});
$("rate-offpeak").addEventListener("click", () => {
  state.rate = "offpeak";
  $("rate-offpeak").classList.add("active");
  $("rate-peak").classList.remove("active");
  renderTable();
});

$("refresh-btn").addEventListener("click", () => {
  loadModels(true);
  loadUsage(true);
});

loadModels(false);
loadUsage(false);
renderRateWindow();
setInterval(() => loadUsage(false), 60000);
setInterval(() => loadModels(false), 600000);