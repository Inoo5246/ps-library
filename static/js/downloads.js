// ─── Downloads page JS ──────────────────────────────────────────────────────
let searchResults = [];
let activeDownloads = [];
let downloadHistory = [];
let dlPollTimer = null;
let currentSearchGameId = null;
let psOnlyFilter = true; // default: only PS console results

// ─── Search ─────────────────────────────────────────────────────────────────

async function searchProwlarr() {
  const query = document.getElementById("dl-search").value.trim();
  const platform = document.getElementById("dl-platform").value;
  const statusEl = document.getElementById("dl-search-status");

  if (!query) { statusEl.textContent = t("dl_enter_query","Enter a search term"); return; }

  statusEl.innerHTML = '<span class="spinner" style="width:14px;height:14px"></span> ' + t("dl_searching","Searching...");
  document.getElementById("dl-results-section").style.display = "block";
  document.getElementById("dl-results-list").innerHTML =
    '<div style="padding:1rem;text-align:center"><span class="spinner"></span></div>';

  try {
    const body = { query, game_id: currentSearchGameId || undefined, ps_only: psOnlyFilter };
    if (platform) body.platform = platform;
    const r = await fetch("/api/downloads/search", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify(body)
    });
    searchResults = await r.json();
    if (searchResults.error) {
      statusEl.textContent = searchResults.error;
      document.getElementById("dl-results-list").innerHTML = '';
      return;
    }
    statusEl.textContent = `${searchResults.length} ${t("results","results")}`;
    renderSearchResults();
  } catch(e) {
    statusEl.textContent = t("connection_error","Connection error");
    console.error(e);
  }
}

function renderSearchResults() {
  const container = document.getElementById("dl-results-list");
  if (!searchResults.length) {
    container.innerHTML = '<div style="padding:1rem;text-align:center;color:var(--textd)">' + t("no_results","No results") + '</div>';
    return;
  }
  container.innerHTML = `
    <div class="dl-result-header">
      <span class="dl-r-title">${t("dl_title","Title")}</span>
      <span class="dl-r-cat">${t("dl_category","Category")}</span>
      <span class="dl-r-size">${t("dl_size","Size")}</span>
      <span class="dl-r-seeds">${t("dl_seeds","Seeds")}</span>
      <span class="dl-r-indexer">${t("dl_indexer","Indexer")}</span>
      <span class="dl-r-action"></span>
    </div>
    ${searchResults.map((r, i) => {
      const cat = (r.categories || []).join(", ") || "—";
      return `
      <div class="dl-result-row">
        <span class="dl-r-title" title="${esc(r.title)}">${esc(r.title)}</span>
        <span class="dl-r-cat" title="${esc(cat)}">${esc(cat)}</span>
        <span class="dl-r-size">${formatSize(r.size)}</span>
        <span class="dl-r-seeds ${r.seeders > 0 ? 'has-seeds' : ''}">${r.seeders}</span>
        <span class="dl-r-indexer">${esc(r.indexer)}</span>
        <span class="dl-r-action">
          <button class="btn btn-primary btn-sm" onclick="grabRelease(${i})">⬇️</button>
        </span>
      </div>`;
    }).join('')}`;
}

function togglePsOnly() {
  const cb = document.getElementById("dl-ps-only");
  psOnlyFilter = cb ? cb.checked : true;
}

function clearResults() {
  searchResults = [];
  currentSearchGameId = null;
  document.getElementById("dl-results-section").style.display = "none";
  document.getElementById("dl-search-status").textContent = "";
}

// ─── Grab ───────────────────────────────────────────────────────────────────

async function grabRelease(idx) {
  const r = searchResults[idx];
  if (!r) return;
  const btn = document.querySelectorAll(".dl-result-row")[idx]?.querySelector("button");
  if (btn) { btn.disabled = true; btn.textContent = "⏳"; }

  try {
    const resp = await fetch("/api/downloads/grab", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        download_url: r.download_url,
        title: r.title,
        indexer: r.indexer,
        size: r.size,
        seeders: r.seeders,
        leechers: r.leechers,
        game_id: currentSearchGameId || null
      })
    }).then(r => r.json());

    if (resp.ok) {
      showToast(t("dl_added","Download added!"));
      if (btn) { btn.textContent = "✅"; btn.classList.remove("btn-primary"); }
      loadDownloads();
    } else {
      showToast(t("error","Error") + ": " + (resp.error || t("unknown","unknown")));
      if (btn) { btn.disabled = false; btn.textContent = "⬇️"; }
    }
  } catch(e) {
    showToast(t("connection_error","Connection error"));
    if (btn) { btn.disabled = false; btn.textContent = "⬇️"; }
  }
}

// ─── Downloads list ─────────────────────────────────────────────────────────

async function loadDownloads() {
  try {
    const all = await fetch("/api/downloads").then(r => r.json());
    activeDownloads = all.filter(d => ["pending","downloading","paused"].includes(d.status));
    downloadHistory = all.filter(d => ["completed","failed","imported"].includes(d.status));
    renderActiveDownloads();
    renderHistory();
  } catch(e) {
    console.error("Load downloads error:", e);
  }
}

function renderActiveDownloads() {
  const container = document.getElementById("dl-active-list");
  const badge = document.getElementById("dl-active-count");
  if (badge) {
    badge.textContent = activeDownloads.length;
    badge.style.display = activeDownloads.length ? "" : "none";
  }
  if (!activeDownloads.length) {
    container.innerHTML = '<div style="color:var(--textd);font-size:.84rem;padding:.5rem 0">' + t("dl_no_active","No active downloads") + '</div>';
    return;
  }
  container.innerHTML = activeDownloads.map(d => {
    const pct = d.progress || 0;
    const speed = d.download_speed ? formatSpeed(d.download_speed) : "";
    const statusClass = d.status === "paused" ? "paused" : "downloading";
    const statusText = d.status === "paused" ? "⏸️ " + t("dl_pause","Pause") :
                       d.status === "pending" ? "⏳ " + t("dl_waiting","Waiting") : `⬇️ ${pct.toFixed(1)}%`;
    return `
      <div class="dl-card">
        <div class="dl-card-header">
          <div class="dl-card-title" title="${esc(d.title)}">${esc(d.title)}</div>
          <div class="dl-card-meta">
            ${d.game_title ? `<span class="dl-game-tag">🎮 ${esc(d.game_title)}</span>` : ''}
            <span>${formatSize(d.size)}</span>
            ${speed ? `<span class="dl-speed">${speed}</span>` : ''}
            ${d.seeders ? `<span title="Seederi">🌱 ${d.seeders}</span>` : ''}
          </div>
        </div>
        <div class="dl-progress">
          <div class="dl-progress-bar ${statusClass}" style="width:${pct}%"></div>
        </div>
        <div class="dl-card-footer">
          <span class="dl-status-text">${statusText}</span>
          <div class="dl-card-actions">
            ${d.status === "paused"
              ? `<button class="btn btn-outline btn-sm" onclick="resumeDl(${d.id})">▶️ ${t("dl_resume","Resume")}</button>`
              : `<button class="btn btn-outline btn-sm" onclick="pauseDl(${d.id})">⏸️ ${t("dl_pause","Pause")}</button>`
            }
            <button class="btn btn-danger btn-sm" onclick="removeDl(${d.id})">🗑️</button>
          </div>
        </div>
      </div>`;
  }).join('');
}

function renderHistory() {
  const container = document.getElementById("dl-history-list");
  if (!downloadHistory.length) {
    container.innerHTML = '<div style="color:var(--textd);font-size:.84rem;padding:.5rem 0">' + t("dl_no_history","No history") + '</div>';
    return;
  }
  container.innerHTML = downloadHistory.slice(0, 50).map(d => {
    const statusIcon = d.status === "imported" ? "✅" : d.status === "completed" ? "📦" : "❌";
    const statusText = d.status === "imported" ? t("dl_imported","Imported") : d.status === "completed" ? t("dl_completed","Completed") : t("dl_failed","Failed");
    return `
      <div class="dl-history-row">
        <span class="dl-h-status">${statusIcon} ${statusText}</span>
        <span class="dl-h-title" title="${esc(d.title)}">${esc(d.title)}</span>
        <span class="dl-h-size">${formatSize(d.size)}</span>
        <span class="dl-h-date">${d.completed_at ? d.completed_at.slice(0,16).replace('T',' ') : d.added_at?.slice(0,16).replace('T',' ') || ''}</span>
        <span class="dl-h-actions">
          ${d.status === "failed" ? `<button class="btn btn-outline btn-sm" onclick="retryDl(${d.id})">🔄</button>` : ''}
          <button class="btn btn-danger btn-sm" style="padding:2px 6px" onclick="removeDl(${d.id})">🗑️</button>
        </span>
      </div>`;
  }).join('');
}

// ─── Actions ────────────────────────────────────────────────────────────────

async function pauseDl(id) {
  await fetch(`/api/downloads/${id}/pause`, {method:"POST"});
  loadDownloads();
}

async function resumeDl(id) {
  await fetch(`/api/downloads/${id}/resume`, {method:"POST"});
  loadDownloads();
}

async function retryDl(id) {
  await fetch(`/api/downloads/${id}/retry`, {method:"POST"});
  loadDownloads();
}

async function removeDl(id) {
  if (!confirm(t("dl_delete_confirm","Delete download?"))) return;
  await fetch(`/api/downloads/${id}?delete_files=false`, {method:"DELETE"});
  loadDownloads();
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatSpeed(bytesPerSec) {
  if (bytesPerSec < 1024) return bytesPerSec + " B/s";
  if (bytesPerSec < 1024*1024) return (bytesPerSec/1024).toFixed(1) + " KB/s";
  return (bytesPerSec/(1024*1024)).toFixed(1) + " MB/s";
}

// ─── Polling ────────────────────────────────────────────────────────────────

function startPolling() {
  if (dlPollTimer) clearInterval(dlPollTimer);
  dlPollTimer = setInterval(() => {
    if (activeDownloads.length > 0) loadDownloads();
  }, 5000);
}

// ─── URL params (for game_id pre-fill from library) ─────────────────────────

function checkUrlParams() {
  const params = new URLSearchParams(window.location.search);
  const gameId = params.get("game_id");
  const searchQ = params.get("search");
  if (gameId) currentSearchGameId = parseInt(gameId);
  if (searchQ) {
    document.getElementById("dl-search").value = searchQ;
    searchProwlarr();
  }
}

// ─── Init ───────────────────────────────────────────────────────────────────

async function init() {
  await loadLanguages();
  await loadDownloads();
  startPolling();
  checkUrlParams();
  updateStats();
}

init();
