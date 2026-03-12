// ─── Settings page JS ─────────────────────────────────────────────────────────
let appSettings = {language:"en", custom_folders:[], auto_scan_interval_hours:0};
const ALL_FILE_TYPES = ["pkg","iso","bin","img","pbp","chd","cue","apk"];

async function loadSettings() {
  try {
    appSettings = await fetch("/api/settings").then(r => r.json());
  } catch(e) { console.warn("Settings load error:", e); }
  renderSettings();
}

function renderSettings() {
  // Language
  const langSel = document.getElementById("settings-lang-select");
  if (langSel) langSel.value = langCode;
  // Auto-scan interval
  const scanInp = document.getElementById("auto-scan-hours");
  if (scanInp) scanInp.value = appSettings.auto_scan_interval_hours || 0;
  // Data paths
  const imgDir  = document.getElementById("setting-images-dir");
  const savDir  = document.getElementById("setting-saves-dir");
  const dlcDir  = document.getElementById("setting-dlc-dir");
  if (imgDir) imgDir.value = appSettings.images_dir || "";
  if (savDir) savDir.value = appSettings.saves_dir  || "";
  if (dlcDir) dlcDir.value = appSettings.dlc_dir    || "";
  // API Keys
  fetch("/api/config").then(r => r.json()).then(cfg => {
    const apiDiv = document.getElementById("api-keys-status");
    if (!apiDiv) return;
    apiDiv.innerHTML = [
      {name:"RAWG", on: cfg.has_rawg_key},
      {name:"IGDB (Twitch)", on: cfg.has_igdb_key},
      {name:"MobyGames", on: cfg.has_moby_key}
    ].map(k => `<div class="api-key-card">
      <span class="api-key-dot ${k.on?'on':'off'}"></span>
      <span>${k.name}</span>
      <span style="color:var(--textd);font-size:.7rem;margin-left:auto">${k.on?"✅ "+t("configured","Configured"):"❌ "+t("missing_key","Missing")}</span>
    </div>`).join('');
  });
  renderFolderMappings();
  // Prowlarr settings
  const prowlarr = appSettings.prowlarr || {};
  const pUrl = document.getElementById("prowlarr-url");
  const pKey = document.getElementById("prowlarr-api-key");
  if (pUrl) pUrl.value = prowlarr.url || "";
  if (pKey) pKey.value = prowlarr.api_key || "";
  // Download clients
  const dlc = appSettings.download_clients || {};
  const defClient = document.getElementById("dl-default-client");
  if (defClient) defClient.value = dlc.default_client || "qbittorrent";
  const qbt = dlc.qbittorrent || {};
  setVal("qbt-enabled", qbt.enabled, "checked");
  setVal("qbt-url", qbt.url);
  setVal("qbt-username", qbt.username || "admin");
  setVal("qbt-password", qbt.password);
  setVal("qbt-category", qbt.category || "ps-library");
  setVal("qbt-save-path", qbt.save_path || "/downloads");
  const tr = dlc.transmission || {};
  setVal("tr-enabled", tr.enabled, "checked");
  setVal("tr-url", tr.url);
  setVal("tr-username", tr.username);
  setVal("tr-password", tr.password);
  setVal("tr-save-path", tr.save_path || "/downloads");
  // Auto-monitor
  const am = appSettings.auto_monitor || {};
  setVal("auto-monitor-enabled", am.enabled, "checked");
  setVal("auto-monitor-interval", am.interval_minutes || 30);
}

function setVal(id, val, type) {
  const el = document.getElementById(id);
  if (!el) return;
  if (type === "checked") el.checked = !!val;
  else el.value = val || "";
}

function renderFolderMappings() {
  const container = document.getElementById("folders-list");
  if (!container) return;
  const folders = appSettings.custom_folders || [];
  if (!folders.length) {
    container.innerHTML = `<div style="color:var(--textd);font-size:.82rem;padding:.5rem 0">
      ${t("no_custom_folders","No custom folders configured. Only /games is scanned.")}<br>
      <span style="opacity:.6">/games (${t("all_platforms","All platforms")} — default)</span>
    </div>`;
    return;
  }
  container.innerHTML = folders.map((f, i) => `
    <div class="folder-card" id="fc-${i}">
      <div class="folder-card-header">
        <span class="folder-card-label">${f.label || f.path || "Folder " + (i+1)}</span>
        <button class="folder-card-remove" onclick="removeFolderMapping(${i})" title="${t("delete","Delete")}">✕</button>
      </div>
      <div class="folder-card-body">
        <div class="form-group">
          <label>${t("folder_path","Cale folder")}</label>
          <div style="display:flex;gap:.4rem">
            <input type="text" id="fp-${i}" value="${f.path||''}" onchange="updateFolder(${i},'path',this.value)" placeholder="/mnt/ps3pkg">
            <button class="btn-browse" onclick="openFolderBrowser(${i})" title="Browse">📂</button>
            <button class="btn btn-outline btn-sm" onclick="testFolderPath(${i})" style="flex-shrink:0">${t("folder_test","Test")}</button>
          </div>
          <div class="folder-test" id="ft-${i}"></div>
        </div>
        <div class="form-group">
          <label>${t("folder_platform","Platform")}</label>
          <select onchange="updateFolder(${i},'platform',this.value)">
            ${["PS5","PS4","PS3","PS2","PS1","PSP"].map(p => `<option ${f.platform===p?"selected":""}>${p}</option>`).join('')}
          </select>
        </div>
        <div class="form-group">
          <label>${t("folder_types","File types")}</label>
          <div class="file-types-picker" id="ftp-${i}">
            ${ALL_FILE_TYPES.map(ft => {
              const active = !f.file_types || !f.file_types.length || f.file_types.includes(ft);
              return `<button class="ft-chip ${active?'active':''}" onclick="toggleFileType(${i},'${ft}',this)">${ft.toUpperCase()}</button>`;
            }).join('')}
          </div>
        </div>
      </div>
      <div class="form-group" style="margin-top:.5rem;margin-bottom:0">
        <label>${t("folder_label","Label")}</label>
        <input type="text" value="${f.label||''}" onchange="updateFolder(${i},'label',this.value)" placeholder="ex: PS3 PKG-uri">
      </div>
    </div>
  `).join('');
}

function addFolderMapping() {
  if (!appSettings.custom_folders) appSettings.custom_folders = [];
  appSettings.custom_folders.push({
    id: "cf_" + Date.now(), path: "", platform: "PS3", file_types: [], label: ""
  });
  renderFolderMappings();
}

function removeFolderMapping(idx) {
  if (!confirm(t("delete_confirm","Delete?"))) return;
  appSettings.custom_folders.splice(idx, 1);
  renderFolderMappings();
}

function updateFolder(idx, key, value) {
  if (appSettings.custom_folders[idx]) {
    appSettings.custom_folders[idx][key] = value;
    if (key === 'label' || key === 'path') {
      const header = document.querySelector(`#fc-${idx} .folder-card-label`);
      if (header) header.textContent = appSettings.custom_folders[idx].label || appSettings.custom_folders[idx].path || "Folder " + (idx+1);
    }
  }
}

function toggleFileType(idx, ft, btn) {
  const f = appSettings.custom_folders[idx];
  if (!f) return;
  if (!f.file_types) f.file_types = [];
  const allActive = !f.file_types.length;
  if (allActive) {
    f.file_types = [ft];
    btn.parentElement.querySelectorAll('.ft-chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
  } else if (f.file_types.includes(ft)) {
    f.file_types = f.file_types.filter(x => x !== ft);
    btn.classList.remove('active');
    if (!f.file_types.length) btn.parentElement.querySelectorAll('.ft-chip').forEach(c => c.classList.add('active'));
  } else {
    f.file_types.push(ft);
    btn.classList.add('active');
  }
}

async function testFolderPath(idx) {
  const f = appSettings.custom_folders[idx];
  if (!f || !f.path) return;
  const el = document.getElementById("ft-" + idx);
  el.textContent = "⏳ ..."; el.className = "folder-test";
  try {
    const r = await fetch("/api/settings/test-path", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({path:f.path})});
    const d = await r.json();
    if (d.exists) {
      el.textContent = `✅ ${t("folder_accessible","Accessible")} — ${d.file_count} ${t("folder_files_found","files found")}`;
      el.className = "folder-test ok";
    } else {
      el.textContent = `❌ ${t("folder_not_found","Does not exist or not mounted")}`;
      el.className = "folder-test fail";
    }
  } catch {
    el.textContent = "❌ Eroare"; el.className = "folder-test fail";
  }
}

async function saveSettings() {
  const st = document.getElementById("settings-status");
  st.textContent = "⏳ ...";
  appSettings.language = langCode;
  // Sync auto-scan hours
  const scanInp = document.getElementById("auto-scan-hours");
  if (scanInp) appSettings.auto_scan_interval_hours = parseInt(scanInp.value) || 0;
  // Sync data paths
  const imgDir = document.getElementById("setting-images-dir");
  const savDir = document.getElementById("setting-saves-dir");
  const dlcDir = document.getElementById("setting-dlc-dir");
  if (imgDir) appSettings.images_dir = imgDir.value.trim();
  if (savDir) appSettings.saves_dir  = savDir.value.trim();
  if (dlcDir) appSettings.dlc_dir    = dlcDir.value.trim();
  // Prowlarr
  appSettings.prowlarr = {
    url: (document.getElementById("prowlarr-url")?.value || "").trim(),
    api_key: (document.getElementById("prowlarr-api-key")?.value || "").trim()
  };
  // Download clients
  appSettings.download_clients = {
    default_client: document.getElementById("dl-default-client")?.value || "qbittorrent",
    qbittorrent: {
      enabled: !!document.getElementById("qbt-enabled")?.checked,
      url: (document.getElementById("qbt-url")?.value || "").trim(),
      username: (document.getElementById("qbt-username")?.value || "").trim(),
      password: document.getElementById("qbt-password")?.value || "",
      category: (document.getElementById("qbt-category")?.value || "ps-library").trim(),
      save_path: (document.getElementById("qbt-save-path")?.value || "/downloads").trim()
    },
    transmission: {
      enabled: !!document.getElementById("tr-enabled")?.checked,
      url: (document.getElementById("tr-url")?.value || "").trim(),
      username: (document.getElementById("tr-username")?.value || "").trim(),
      password: document.getElementById("tr-password")?.value || "",
      save_path: (document.getElementById("tr-save-path")?.value || "/downloads").trim()
    }
  };
  // Auto-monitor
  appSettings.auto_monitor = {
    enabled: !!document.getElementById("auto-monitor-enabled")?.checked,
    interval_minutes: parseInt(document.getElementById("auto-monitor-interval")?.value) || 30
  };
  // Save ps3netsrv config separately
  await ps3nsSaveConfig();
  try {
    const r = await fetch("/api/settings", {method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify(appSettings)});
    const d = await r.json();
    if (d.ok) {
      st.textContent = `✅ ${t("settings_saved","Settings saved!")}`;
      setTimeout(() => st.textContent = "", 3000);
    } else {
      st.textContent = `❌ ${d.error || t("settings_save_error","Eroare")}`;
    }
  } catch {
    st.textContent = `❌ ${t("settings_save_error","Eroare la salvare!")}`;
  }
}

function settingsChangeLang(code) {
  langCode = code;
  localStorage.setItem("ps-library-lang", code);
  const sel = document.getElementById("lang-select");
  if (sel) sel.value = code;
  applyLanguage(code);
}

// ─── Folder Browser ───────────────────────────────────────────────────────────
let fbCurrentPath = "/", fbTargetIdx = null, fbTargetInputId = null;

function openFolderBrowser(idx) {
  fbTargetIdx = idx;
  fbTargetInputId = null;
  const f = appSettings.custom_folders[idx];
  fbCurrentPath = f && f.path ? f.path : "/";
  document.getElementById("modal-browse-folder").classList.add("show");
  navigateFolder(fbCurrentPath);
}

// ─── Browse pentru căile de date (images_dir, saves_dir, dlc_dir) ─────────────
function openDataPathBrowser(inputId) {
  fbTargetInputId = inputId;
  fbTargetIdx = null;
  const inp = document.getElementById(inputId);
  fbCurrentPath = (inp && inp.value.trim()) ? inp.value.trim() : "/";
  document.getElementById("modal-browse-folder").classList.add("show");
  navigateFolder(fbCurrentPath);
}

async function testDataPath(inputId, resultId) {
  const inp = document.getElementById(inputId);
  const el  = document.getElementById(resultId);
  if (!inp || !el) return;
  const path = inp.value.trim();
  if (!path) { el.textContent = ""; el.className = "folder-test"; return; }
  el.textContent = "⏳ ..."; el.className = "folder-test";
  try {
    const r = await fetch("/api/settings/test-path", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({path})
    });
    const d = await r.json();
    if (d.exists) {
      el.textContent = `✅ ${t("path_accessible","Accesibil")}`;
      el.className = "folder-test ok";
    } else {
      el.textContent = `❌ ${t("path_not_found","Does not exist or not mounted")}`;
      el.className = "folder-test fail";
    }
  } catch {
    el.textContent = "❌ Eroare"; el.className = "folder-test fail";
  }
}

function closeFolderBrowser() {
  document.getElementById("modal-browse-folder").classList.remove("show");
}

async function navigateFolder(path) {
  fbCurrentPath = path;
  document.getElementById("fb-path-bar").textContent = path;
  document.getElementById("fb-list").innerHTML = '<div style="padding:1rem;text-align:center"><span class="spinner"></span></div>';
  document.getElementById("fb-info").textContent = "";
  try {
    const r = await fetch("/api/settings/browse-dirs", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({path})
    });
    const d = await r.json();
    if (d.error && !d.dirs.length) {
      document.getElementById("fb-list").innerHTML = `<div style="padding:1rem;text-align:center;color:var(--danger);font-size:.84rem">${d.error}</div>`;
      return;
    }
    let html = "";
    if (d.parent !== null && d.parent !== undefined) {
      html += `<div class="fb-item fb-parent" data-path="${esc(d.parent)}">
        <span class="fb-item-icon">⬆️</span><span class="fb-item-name">..</span>
      </div>`;
    }
    if (d.dirs.length) {
      d.dirs.forEach(dir => {
        const badge = dir.game_files > 0 ? `<span class="fb-item-badge has-files">🎮 ${dir.game_files}</span>` : '';
        html += `<div class="fb-item" data-path="${esc(dir.path)}">
          <span class="fb-item-icon">📁</span>
          <span class="fb-item-name">${esc(dir.name)}</span>
          ${badge}
        </div>`;
      });
    } else if (!d.parent) {
      html += `<div style="padding:1rem;text-align:center;color:var(--textd);font-size:.82rem">${t("no_subdirectories","No subdirectories")}</div>`;
    }
    document.getElementById("fb-list").innerHTML = html || `<div style="padding:1rem;text-align:center;color:var(--textd);font-size:.82rem">${t("empty_folder","Empty folder")}</div>`;
    if (d.game_files_here > 0) {
      document.getElementById("fb-info").innerHTML = `<span style="color:var(--played)">🎮 ${d.game_files_here} ${t("folder_files_found","files found")} in this folder</span>`;
    }
  } catch(e) {
    document.getElementById("fb-list").innerHTML = `<div style="padding:1rem;text-align:center;color:var(--danger)">${t("connection_error","Connection error")}</div>`;
  }
}

function selectFolder() {
  if (fbTargetInputId) {
    // Câmp cale date (images_dir / saves_dir / dlc_dir)
    const inp = document.getElementById(fbTargetInputId);
    if (inp) inp.value = fbCurrentPath;
    fbTargetInputId = null;
  } else if (fbTargetIdx !== null && appSettings.custom_folders[fbTargetIdx]) {
    appSettings.custom_folders[fbTargetIdx].path = fbCurrentPath;
    const inp = document.getElementById("fp-" + fbTargetIdx);
    if (inp) inp.value = fbCurrentPath;
    const f = appSettings.custom_folders[fbTargetIdx];
    const header = document.querySelector(`#fc-${fbTargetIdx} .folder-card-label`);
    if (header) header.textContent = f.label || f.path || "Folder " + (fbTargetIdx + 1);
  }
  closeFolderBrowser();
}

document.getElementById("modal-browse-folder").addEventListener("click", e => {
  if (e.target === document.getElementById("modal-browse-folder")) closeFolderBrowser();
});

// Event delegation for folder browser items (avoid inline onclick XSS)
document.getElementById("fb-list").addEventListener("click", e => {
  const item = e.target.closest("[data-path]");
  if (item) navigateFolder(item.dataset.path);
});

// ─── Redump.org ───────────────────────────────────────────────────────────────

async function loadRedumpDats() {
  const container = document.getElementById("redump-dats-list");
  if (!container) return;
  try {
    const dats = await fetch("/api/redump/dats").then(r => r.json());
    if (!dats.length) {
      container.innerHTML = `<p style="color:var(--textd);font-size:.82rem;margin:.3rem 0">
        ${t("no_dats","No DATs imported. Download from redump.org and import with the button above.")}</p>`;
      return;
    }
    container.innerHTML = dats.map(d => `
      <div style="display:flex;align-items:center;gap:.6rem;padding:.45rem 0;border-bottom:1px solid var(--border)">
        <span style="font-size:.78rem;flex:1">
          <strong>${d.platform}</strong>
          <span style="color:var(--textd);margin-left:.4rem">${d.filename}</span>
        </span>
        <span class="type-badge type-ISO" style="font-size:.68rem">${d.game_count.toLocaleString()} ${t("games_count","games")}</span>
        <span style="color:var(--textd);font-size:.68rem">${d.imported_at ? d.imported_at.slice(0,10) : ''}</span>
        <button class="btn btn-danger btn-sm" style="padding:2px 7px;font-size:.72rem"
                data-dat-id="${d.id}" data-dat-name="${esc(d.filename)}" onclick="deleteRedumpDat(+this.dataset.datId,this.dataset.datName)">🗑️</button>
      </div>`).join('');
  } catch(e) {
    container.innerHTML = `<p style="color:var(--danger);font-size:.82rem">${t("dat_load_error","Error loading DATs")}</p>`;
  }
}

async function importRedumpDat(input) {
  const file = input.files[0];
  if (!file) return;
  const st = document.getElementById("settings-status");
  st.textContent = `⏳ ${t("importing","Importing")} ${file.name}…`;
  const fd = new FormData();
  fd.append("file", file);
  try {
    const r = await fetch("/api/redump/import-dat", {method:"POST", body: fd});
    const d = await r.json();
    if (d.error) {
      st.textContent = `❌ ${d.error}`;
    } else {
      st.textContent = `✅ ${d.platform} — ${d.game_count.toLocaleString()} ${t("entries_imported","entries imported")}`;
      setTimeout(() => st.textContent = "", 4000);
      loadRedumpDats();
    }
  } catch {
    st.textContent = "❌ " + t("import_error","Import error");
  }
  input.value = "";
}

async function deleteRedumpDat(id, filename) {
  if (!confirm(`${t("delete_dat_confirm","Delete DAT")} "${filename}"?`)) return;
  await fetch(`/api/redump/dats/${id}`, {method:"DELETE"});
  loadRedumpDats();
}

// ─── ps3netsrv ────────────────────────────────────────────────────────────────

async function ps3nsLoadStatus() {
  try {
    const st = await fetch("/api/ps3netsrv/status").then(r => r.json());
    ps3nsUpdateUI(st);
  } catch(e) { console.warn("ps3netsrv status error:", e); }
}

function ps3nsUpdateUI(st) {
  const dot   = document.getElementById("ps3ns-status-dot");
  const text  = document.getElementById("ps3ns-status-text");
  const start = document.getElementById("ps3ns-btn-start");
  const stop  = document.getElementById("ps3ns-btn-stop");
  const restart = document.getElementById("ps3ns-btn-restart");
  if (!dot) return;

  if (st.running) {
    dot.className = "api-key-dot on";
    text.textContent = `${t("running_pid","Running")} (PID ${st.pid || '?'})`;
    start.style.display = "none";
    stop.style.display = "";
    restart.style.display = "";
  } else {
    dot.className = "api-key-dot off";
    text.textContent = t("stopped","Stopped");
    start.style.display = "";
    stop.style.display = "none";
    restart.style.display = "none";
  }

  // Fill config fields if not yet set by user
  const dirInp  = document.getElementById("ps3ns-games-dir");
  const portInp = document.getElementById("ps3ns-port");
  const enChk   = document.getElementById("ps3ns-enabled");
  if (dirInp && !dirInp.dataset.loaded) {
    dirInp.value = st.games_dir || "/games";
    dirInp.dataset.loaded = "1";
  }
  if (portInp && !portInp.dataset.loaded) {
    portInp.value = st.port || 38008;
    portInp.dataset.loaded = "1";
  }
  if (enChk && !enChk.dataset.loaded) {
    enChk.checked = !!st.enabled;
    enChk.dataset.loaded = "1";
  }
}

async function ps3nsSaveConfig() {
  const dirInp  = document.getElementById("ps3ns-games-dir");
  const portInp = document.getElementById("ps3ns-port");
  const enChk   = document.getElementById("ps3ns-enabled");
  const cfg = {
    games_dir: dirInp ? dirInp.value.trim() : "/games",
    port: portInp ? parseInt(portInp.value) || 38008 : 38008,
    enabled: enChk ? enChk.checked : false,
  };
  await fetch("/api/ps3netsrv/config", {
    method: "PUT",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(cfg),
  });
}

async function ps3nsStart() {
  const msg = document.getElementById("ps3ns-message");
  msg.textContent = "⏳ " + t("starting","Starting...");
  await ps3nsSaveConfig();
  try {
    const r = await fetch("/api/ps3netsrv/start", {method:"POST"}).then(r => r.json());
    msg.textContent = r.ok ? `✅ ${r.message}` : `❌ ${r.message}`;
    ps3nsUpdateUI(r.status);
    setTimeout(() => msg.textContent = "", 4000);
  } catch {
    msg.textContent = "❌ " + t("start_error","Error starting");
  }
}

async function ps3nsStop() {
  const msg = document.getElementById("ps3ns-message");
  msg.textContent = "⏳ " + t("stopping","Stopping...");
  try {
    const r = await fetch("/api/ps3netsrv/stop", {method:"POST"}).then(r => r.json());
    msg.textContent = r.ok ? `✅ ${r.message}` : `❌ ${r.message}`;
    ps3nsUpdateUI(r.status);
    setTimeout(() => msg.textContent = "", 4000);
  } catch {
    msg.textContent = "❌ " + t("stop_error","Error stopping");
  }
}

async function ps3nsRestart() {
  const msg = document.getElementById("ps3ns-message");
  msg.textContent = "⏳ Restart...";
  await ps3nsSaveConfig();
  try {
    const r = await fetch("/api/ps3netsrv/restart", {method:"POST"}).then(r => r.json());
    msg.textContent = r.ok ? `✅ ${r.message}` : `❌ ${r.message}`;
    ps3nsUpdateUI(r.status);
    setTimeout(() => msg.textContent = "", 4000);
  } catch {
    msg.textContent = "❌ " + t("restart_error","Error restarting");
  }
}

let ps3nsLogVisible = false;
async function ps3nsToggleLogs() {
  const box = document.getElementById("ps3ns-log-box");
  ps3nsLogVisible = !ps3nsLogVisible;
  box.style.display = ps3nsLogVisible ? "" : "none";
  if (ps3nsLogVisible) {
    try {
      const r = await fetch("/api/ps3netsrv/logs").then(r => r.json());
      box.textContent = r.lines.length ? r.lines.join("\n") : t("no_logs","(no logs)");
      box.scrollTop = box.scrollHeight;
    } catch {
      box.textContent = t("logs_load_error","(error loading logs)");
    }
  }
}

// ─── Prowlarr + Download Clients ──────────────────────────────────────────────

async function testProwlarr() {
  const msg = document.getElementById("prowlarr-message");
  const dot = document.getElementById("prowlarr-status-dot");
  const txt = document.getElementById("prowlarr-status-text");
  msg.textContent = "⏳ " + t("testing","Testing...");
  // Save first so backend picks up new values
  appSettings.prowlarr = {
    url: (document.getElementById("prowlarr-url")?.value || "").trim(),
    api_key: (document.getElementById("prowlarr-api-key")?.value || "").trim()
  };
  await fetch("/api/settings", {method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify(appSettings)});
  try {
    const r = await fetch("/api/prowlarr/status").then(r => r.json());
    if (r.ok) {
      dot.className = "api-key-dot on";
      txt.textContent = t("connected","Connected");
      msg.innerHTML = `✅ ${r.message} — <strong>${r.indexers.length}</strong> ${t("active_indexers","active indexers")}`;
      if (r.indexers.length) {
        document.getElementById("prowlarr-indexers").innerHTML = r.indexers.map(idx =>
          `<span class="type-badge type-ISO" style="font-size:.7rem;margin:.1rem">${esc(idx.name)}</span>`
        ).join('');
      }
    } else {
      dot.className = "api-key-dot off";
      txt.textContent = t("error","Error");
      msg.textContent = `❌ ${r.message}`;
    }
  } catch(e) {
    dot.className = "api-key-dot off";
    txt.textContent = t("error","Error");
    msg.textContent = `❌ ${t("connection_error","Connection error")}`;
  }
}

async function testDlClient(name) {
  const prefix = name === "qbittorrent" ? "qbt" : "tr";
  const dot = document.getElementById(prefix + "-status-dot");
  const txt = document.getElementById(prefix + "-status-text");
  txt.textContent = "⏳ " + t("testing","Testing...");
  // Save first
  await saveSettings();
  try {
    const r = await fetch("/api/downloads/clients/test", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({client: name})
    }).then(r => r.json());
    if (r.ok) {
      dot.className = "api-key-dot on";
      txt.textContent = r.message;
    } else {
      dot.className = "api-key-dot off";
      txt.textContent = r.message;
    }
  } catch {
    dot.className = "api-key-dot off";
    txt.textContent = t("connection_error","Connection error");
  }
}

async function prowlarrLoadStatus() {
  try {
    const r = await fetch("/api/prowlarr/status").then(r => r.json());
    const dot = document.getElementById("prowlarr-status-dot");
    const txt = document.getElementById("prowlarr-status-text");
    if (dot) dot.className = r.ok ? "api-key-dot on" : "api-key-dot off";
    if (txt) txt.textContent = r.ok ? `${t("connected","Connected")} (${r.indexers.length} indexers)` : t("not_connected","Not connected");
  } catch {}
}

async function dlClientsLoadStatus() {
  try {
    const r = await fetch("/api/downloads/clients/status").then(r => r.json());
    for (const name of ["qbittorrent", "transmission"]) {
      const prefix = name === "qbittorrent" ? "qbt" : "tr";
      const dot = document.getElementById(prefix + "-status-dot");
      const txt = document.getElementById(prefix + "-status-text");
      const c = r[name] || {};
      if (dot) dot.className = c.ok ? "api-key-dot on" : "api-key-dot off";
      if (txt) txt.textContent = c.ok ? c.message : (c.enabled ? c.message : "");
    }
  } catch {}
}

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  await loadLanguages();
  await loadSettings();
  loadRedumpDats();
  ps3nsLoadStatus();
  prowlarrLoadStatus();
  dlClientsLoadStatus();
  updateStats();
}

init();
