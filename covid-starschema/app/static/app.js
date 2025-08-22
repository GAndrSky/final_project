const $ = (id) => document.getElementById(id);

function setStatus(msg, type = "info") {
  const box = $("status");
  if (!box) return;
  box.hidden = !msg;
  box.textContent = msg || "";
  box.className = `status ${type}`;
}

function disable(el, on = true) {
  if (!el) return;
  el.disabled = on;
  el.classList.toggle("is-loading", on);
}

function splitTags(text) {
  return (text || "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, options);
  let text = "";
  try { text = await res.text(); } catch {}
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    const msg = data?.detail || data?.error || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function plotSeries(containerId, rows, yKey, maKey, title) {
  const x = rows.map(r => r.date);
  const y = rows.map(r => r[yKey] ?? 0);
  const ma = rows.map(r => r[maKey] ?? 0);

  const traces = [
    { x, y, type: "scatter", mode: "lines", name: "Daily" },
    { x, y: ma, type: "scatter", mode: "lines", name: "7-day MA" },
  ];
  const layout = {
    title,
    margin: { t: 36, r: 12, l: 48, b: 40 },
    xaxis: { title: "Date", type: "date" },
    yaxis: { title: "Count" },
  };
  Plotly.newPlot(containerId, traces, layout, { displayModeBar: false, responsive: true });
}

async function loadStateData() {
  const btn = $("loadStateBtn");
  const state = ($("stateInput")?.value || "").trim();
  if (!state) {
    setStatus("Please enter a state (e.g., New York).", "warn");
    return;
  }
  disable(btn, true);
  setStatus(`Loading ${state}…`, "info");
  try {
    const rows = await fetchJSON(`/cases?state=${encodeURIComponent(state)}`);
    if (!rows?.length) throw new Error("Empty result");
    plotSeries("casesChart", rows, "new_cases", "ma7_new_cases", `New Cases — ${state}`);
    plotSeries("deathsChart", rows, "new_deaths", "ma7_new_deaths", `New Deaths — ${state}`);
    setStatus(`Loaded: ${state}`, "success");
    setTimeout(() => setStatus("", "info"), 1200);
  } catch (e) {
    console.error(e);
    setStatus(`Failed to load ${state}: ${e.message}`, "error");
  } finally {
    disable(btn, false);
  }
}

async function loadUsData() {
  const btn = $("loadUsBtn");
  disable(btn, true);
  setStatus("Loading USA…", "info");
  try {
    const rows = await fetchJSON(`/cases/us`);
    if (!rows?.length) throw new Error("Empty result");
    plotSeries("casesChart", rows, "new_cases", "ma7_new_cases", "New Cases — USA");
    plotSeries("deathsChart", rows, "new_deaths", "ma7_new_deaths", "New Deaths — USA");
    setStatus("Loaded: USA", "success");
    setTimeout(() => setStatus("", "info"), 1200);
  } catch (e) {
    console.error(e);
    setStatus(`Failed to load USA: ${e.message}`, "error");
  } finally {
    disable(btn, false);
  }
}

async function onPostComment(ev) {
  ev.preventDefault();
  const form = $("commentForm");
  const submitBtn = form?.querySelector('button[type="submit"]');
  disable(submitBtn, true);
  setStatus("Posting comment…", "info");

  const payload = {
    name: $("userInput")?.value?.trim() || "Anonymous",
    comment: $("textInput")?.value?.trim() || "",
    state: ($("commentStateInput")?.value || "").trim() || null,
    tags: splitTags($("tagsInput")?.value || "")
  };
  if (!payload.comment) {
    setStatus("Comment text is required.", "warn");
    disable(submitBtn, false);
    return;
  }

  try {
    await fetchJSON("/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    $("textInput").value = "";
    $("tagsInput").value = "";
    setStatus("Comment posted.", "success");
    await loadComments();
    setTimeout(() => setStatus("", "info"), 1200);
  } catch (e) {
    console.error(e);
    setStatus(`Failed to post: ${e.message}`, "error");
  } finally {
    disable(submitBtn, false);
  }
}

async function loadComments() {
  const btn = $("refreshCommentsBtn");
  disable(btn, true);
  try {
    const st = ($("filterStateInput")?.value || "").trim();
    const url = st ? `/comments?state=${encodeURIComponent(st)}` : "/comments";
    const items = await fetchJSON(url);
    const ul = $("commentsList");
    ul.innerHTML = "";
    for (const it of items) {
      const li = document.createElement("li");
      li.innerHTML = `
        <div class="comment">
          <div class="comment-head">
            <strong>${it.name ?? "Anonymous"}</strong>
            <span class="muted">${it.state ?? "—"}</span>
            ${Array.isArray(it.tags) && it.tags.length ? `<span class="tags">${it.tags.join(", ")}</span>` : ""}
          </div>
          <div class="comment-body">${(it.comment ?? "").toString()}</div>
        </div>`;
      ul.appendChild(li);
    }
  } catch (e) {
    console.error(e);
    setStatus(`Failed to load comments: ${e.message}`, "error");
  } finally {
    disable(btn, false);
  }
}

async function runEda() {
  const btn = $("runEdaBtn");
  const state = ($("edaState")?.value || "").trim() || "California";
  disable(btn, true);
  setStatus("Running EDA… first run may take longer.", "info");
  try {
    const data = await fetchJSON("/eda", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state })
    });
    if (!data?.ok) throw new Error(data?.error || "EDA failed");

    const casesUrl  = data.urls?.daily_cases_html;
    const deathsUrl = data.urls?.daily_deaths_html;
    const csvUrl    = data.urls?.csv;

    if (casesUrl)  $("edaCasesFrame").src  = `${casesUrl}?t=${Date.now()}`;
    if (deathsUrl) $("edaDeathsFrame").src = `${deathsUrl}?t=${Date.now()}`;

    const openCasesBtn  = $("openCasesHtmlBtn");
    const openDeathsBtn = $("openDeathsHtmlBtn");
    const downloadCsvBtn = $("downloadCsvBtn");

    openCasesBtn.disabled  = !casesUrl;
    openDeathsBtn.disabled = !deathsUrl;
    downloadCsvBtn.disabled = !csvUrl;

    openCasesBtn.onclick  = () => casesUrl  && window.open(casesUrl, "_blank");
    openDeathsBtn.onclick = () => deathsUrl && window.open(deathsUrl, "_blank");
    downloadCsvBtn.onclick = () => csvUrl   && window.open(csvUrl, "_blank");

    setStatus("EDA ready.", "success");
    setTimeout(() => setStatus("", "info"), 1200);
  } catch (e) {
    console.error(e);
    setStatus(`EDA failed: ${e.message}`, "error");
  } finally {
    disable(btn, false);
  }
}

async function runForecast() {
  const btn = $("runFcBtn");
  const state = ($("fcState")?.value || "").trim() || "California";
  const days  = parseInt($("fcDays")?.value || "30", 10);
  disable(btn, true);
  setStatus("Building forecast…", "info");
  try {
    const data = await fetchJSON("/forecast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state, days })
    });
    if (!data?.ok) throw new Error(data?.error || "Forecast failed");

    const url = data.url;
    if (url) $("forecastFrame").src = `${url}?t=${Date.now()}`;

    const openBtn = $("openForecastBtn");
    openBtn.disabled = !url;
    openBtn.onclick = () => url && window.open(url, "_blank");

    setStatus("Forecast ready.", "success");
    setTimeout(() => setStatus("", "info"), 1200);
  } catch (e) {
    console.error(e);
    setStatus(`Forecast failed: ${e.message}`, "error");
  } finally {
    disable(btn, false);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  $("loadStateBtn")?.addEventListener("click", loadStateData);
  $("loadUsBtn")?.addEventListener("click", loadUsData);
  $("commentForm")?.addEventListener("submit", onPostComment);
  $("refreshCommentsBtn")?.addEventListener("click", loadComments);
  $("runEdaBtn")?.addEventListener("click", runEda);
  $("runFcBtn")?.addEventListener("click", runForecast);

  const defaultState = ($("stateInput")?.value || "").trim();
  if (defaultState) loadStateData(); else loadUsData();
  loadComments();
});
