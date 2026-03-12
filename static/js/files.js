// ─── File Manager page JS ─────────────────────────────────────────────────────

async function loadFiles() {
  try {
    const p = new URLSearchParams();
    if (currentPlatform) p.set("platform", currentPlatform);
    if (currentFileType) p.set("type", currentFileType);
    allFiles = await fetch(`/api/files?${p}`).then(r => r.json());
    renderFiles();
    updatePlatformCounts();
  } catch(e) {
    console.error("loadFiles error:", e);
    const el = document.getElementById("file-list");
    if (el) el.innerHTML = `<div class="loading-row">⚠️ ${t("network_error","Network error")}</div>`;
  }
}

async function loadLicenses() {
  try {
    allLicenses = await fetch("/api/licenses").then(r => r.json());
    renderLicenses();
  } catch(e) {
    console.error("loadLicenses error:", e);
  }
}

async function loadGamesForAssoc() {
  allGames = await fetch("/api/games").then(r => r.json());
}

function updatePlatformCounts() {
  const pc = {};
  allFiles.forEach(f => { pc[f.platform] = (pc[f.platform] || 0) + 1; });
  let tot = 0;
  ["PS5","PS4","PS3","PS2","PS1","PSP"].forEach(p => {
    const el = document.getElementById("pc-" + p);
    if (el) el.textContent = pc[p] || 0;
    tot += (pc[p] || 0);
  });
  const allEl = document.getElementById("pc-all");
  if (allEl) allEl.textContent = tot;
  // Storage sidebar
  const pm = {};
  allFiles.forEach(f => {
    if (!pm[f.platform]) pm[f.platform] = {cnt:0, sz:0};
    pm[f.platform].cnt++;
    pm[f.platform].sz += f.file_size || 0;
  });
  const mini = document.getElementById("storage-mini");
  if (mini) mini.innerHTML = Object.entries(pm).map(([p,d]) =>
    `<div><strong>${p||'?'}</strong> — ${formatSize(d.sz)}</div>`).join('') ||
    `<span>${t("no_files_exist","No files exist")}</span>`;
  const cards = document.getElementById("storage-cards");
  if (cards) cards.innerHTML = Object.entries(pm).map(([p,d]) =>
    `<div class="storage-card"><div class="sc-platform">${p||'?'}</div><div class="sc-count">${d.cnt}</div><div class="sc-size">${formatSize(d.sz)}</div></div>`).join('');
}

function buildGameOptions(currentGameId) {
  return `<option value="">${t("unassigned","— Unassigned —")}</option>` +
    allGames.map(g => `<option value="${g.id}" ${g.id == currentGameId ? "selected" : ""}>${g.title} [${g.platform}]</option>`).join('');
}

function renderFiles() {
  const el = document.getElementById("files-list");
  if (!el) return;
  if (!allFiles.length) {
    el.innerHTML = `<div class="loading-row">${t("no_files","No files. Press Scan Folders or upload.")}</div>`;
    return;
  }
  const REDUMP_TYPES = new Set(["BIN","ISO","IMG"]);

  // ── Grupare BIN + CUE cu același stem și folder ───────────────────────────
  const binCueMap = {};
  allFiles.forEach(f => {
    if (f.file_type === 'BIN' || f.file_type === 'CUE') {
      const stem = f.filename.replace(/\.(bin|cue)$/i, '');
      const dir  = f.filepath.slice(0, f.filepath.length - f.filename.length - 1);
      const key  = dir + '§' + stem;
      if (!binCueMap[key]) binCueMap[key] = {};
      if (f.file_type === 'BIN') binCueMap[key].bin = f;
      else                       binCueMap[key].cue = f;
    }
  });
  // CUE-urile care au BIN pereche → ascunse
  const skipIds = new Set();
  const binHasCue = new Set();
  Object.values(binCueMap).forEach(g => {
    if (g.bin && g.cue) { skipIds.add(g.cue.id); binHasCue.add(g.bin.id); }
  });

  el.innerHTML = allFiles.filter(f => !skipIds.has(f.id)).map(f => {
    const canVerify = REDUMP_TYPES.has(f.file_type);
    const hasCue    = binHasCue.has(f.id);
    const verifyBtn = canVerify
      ? `<button class="btn btn-outline btn-sm" id="rdv-${f.id}" onclick="verifyRedump(${f.id})"
               title="Verify with Redump.org" style="font-size:.72rem;padding:2px 6px">🔍</button>`
      : '';
    const hashInfo = f.md5_hash
      ? `<span title="MD5: ${f.md5_hash}" style="color:var(--played);font-size:.7rem;cursor:default">✅</span>`
      : '';

    // Badge tip — BIN cu CUE asociat primește +CUE
    const typeBadge = hasCue
      ? `<span class="type-badge type-BIN">BIN</span><span class="type-badge" style="background:var(--textd)22;color:var(--textd);font-size:.6rem;padding:1px 4px;margin-left:2px">+CUE</span>`
      : `<span class="type-badge type-${f.file_type}">${f.file_type}</span>`;

    // Titlu detectat (salvat din Redump sau scanner) — afișat inline dacă diferă de stem
    const stem = f.filename.replace(/\.[^.]+$/, '');
    const detTitle = (f.detected_title && f.detected_title !== stem && f.detected_title !== f.filename)
      ? `<span class="rdump-title" style="color:var(--cyan);font-size:.72rem;margin-left:.5rem">${esc(f.detected_title)}</span>`
      : '';

    return `
    <div class="file-row ${!f.game_id ? 'unassigned' : ''}" id="frow-${f.id}">
      <div class="file-name" title="${f.filepath}">${f.is_uploaded ? '⬆️' : '💾'} ${f.filename}${detTitle}</div>
      <div>${typeBadge}</div>
      <div>${f.platform ? `<span class="platform-tag">${f.platform}</span>` : '<span style="color:var(--textd)">?</span>'}</div>
      <div><span class="content-id" title="${f.content_id||''}">${f.content_id||'—'}</span></div>
      <div class="inline-assoc">
        <select id="fassoc-${f.id}" onchange="quickAssoc(${f.id},'file',this.value)">${buildGameOptions(f.game_id)}</select>
      </div>
      <div class="file-actions">
        ${hashInfo}${verifyBtn}
        ${f.game_id
          ? `<button class="btn btn-edit btn-sm" onclick="openEditGameFromFile(${f.game_id})" title="${t("edit_game","Edit associated game")}">✏️</button>`
          : `<button class="btn btn-edit btn-sm" onclick="openAddGameFromFile(${f.id},'${esc(f.detected_title||f.filename)}','${f.platform||''}')" title="${t("add_game_from_file","Add game and associate")}">➕</button>`}
        <a class="btn btn-outline btn-sm" href="/api/files/${f.id}/download" title="Download">⬇️</a>
        <button class="btn btn-danger btn-sm" onclick="delFile(${f.id})">🗑️</button>
      </div>
    </div>`;
  }).join('');
}

function renderLicenses() {
  const el = document.getElementById("licenses-list");
  if (!el) return;
  if (!allLicenses.length) {
    el.innerHTML = `<div class="loading-row">${t("no_licenses","No licenses. Scan or upload .rap/.rif/.edat")}</div>`;
    return;
  }
  el.innerHTML = allLicenses.map(l => `
    <div class="file-row" style="grid-template-columns:2fr .8fr 1.3fr 1.4fr 100px" id="lrow-${l.id}">
      <div class="file-name">${l.is_uploaded ? '⬆️' : '🔑'} ${l.filename}</div>
      <div><span class="type-badge type-${l.license_type}">${l.license_type}</span></div>
      <div><span class="content-id">${l.content_id||'—'}</span></div>
      <div class="inline-assoc">
        <select id="lassoc-${l.id}" onchange="quickAssoc(${l.id},'license',this.value)">${buildGameOptions(l.game_id)}</select>
      </div>
      <div class="file-actions">
        <a class="btn btn-outline btn-sm" href="/api/licenses/${l.id}/download">⬇️</a>
        <button class="btn btn-danger btn-sm" onclick="delLic(${l.id})">🗑️</button>
      </div>
    </div>`).join('');
}

// ─── Platform / type filters ──────────────────────────────────────────────────
function filterPlatform(el, p) {
  document.querySelectorAll("#plat-nav .plat-btn").forEach(b => b.classList.remove("active"));
  el.classList.add("active");
  currentPlatform = p;
  loadFiles();
  const mob = document.getElementById("mobile-plat-filter");
  if (mob) mob.value = p;
}

function filterType(el, ft) {
  document.querySelectorAll(".type-filter-btn").forEach(b => b.classList.remove("active"));
  el.classList.add("active");
  currentFileType = ft;
  loadFiles();
  const mob = document.getElementById("mobile-type-filter");
  if (mob) mob.value = ft;
}

function mobileFilterPlatform(p) {
  currentPlatform = p; loadFiles();
  document.querySelectorAll("#plat-nav .plat-btn").forEach(b => {
    b.classList.toggle("active", b.textContent.trim().startsWith(p) || (!p && b.textContent.includes("Toate")));
  });
}

function mobileFilterType(ft) { currentFileType = ft; loadFiles(); }

// ─── Scan ─────────────────────────────────────────────────────────────────────
async function scanFiles() {
  ["scan-status","scan-status-lic"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = `<span class="spinner"></span> ${t("scanning","Scanning...")}`;
  });
  try {
    const d = await fetch("/api/files/scan", {method: "POST"}).then(r => r.json());
    const msg = `✅ ${d.scanned_files} ${t("files","files")} + ${d.scanned_licenses} ${t("licenses","licenses")}`;
    ["scan-status","scan-status-lic"].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = msg; });
    await Promise.all([loadFiles(), loadLicenses()]);
    updateStats();
  } catch {
    ["scan-status","scan-status-lic"].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = `❌ ${t("scan_error","Error")}`; });
  }
}

// ─── Delete ───────────────────────────────────────────────────────────────────
async function delFile(id) {
  if (!confirm(t("delete_confirm","Delete?"))) return;
  await fetch(`/api/files/${id}`, {method: "DELETE"});
  loadFiles(); updateStats();
}
async function delLic(id) {
  if (!confirm(t("delete_license_confirm","Delete license?"))) return;
  await fetch(`/api/licenses/${id}`, {method: "DELETE"});
  loadLicenses(); updateStats();
}

// ─── Add Game from file (navighează la Library cu parametri) ──────────────────
function openAddGameFromFile(fileId, title, platform) {
  const params = new URLSearchParams({
    add_for_file: fileId,
    ftitle: title || "",
    platform: platform || "PS3"
  });
  window.location.href = "/?" + params.toString();
}

// ─── Edit associated game (navighează la Library în modul editare) ────────────
function openEditGameFromFile(gameId) {
  window.location.href = "/?edit_game=" + gameId;
}

// ─── Associate ────────────────────────────────────────────────────────────────
function editFileAssoc(fileId, gameId) {
  const f = allFiles.find(x => x.id === fileId);
  if (f) openAssoc(fileId, 'file', f.filename, gameId);
}

function openAssoc(id, type, fname, currentGameId) {
  document.getElementById("assoc-id").value = id;
  document.getElementById("assoc-type").value = type;
  document.getElementById("assoc-filename").textContent = "📁 " + fname;
  const sel = document.getElementById("assoc-game-select");
  sel.innerHTML = `<option value="">${t("unassigned","— Unassigned —")}</option>`;
  allGames.forEach(g => sel.innerHTML += `<option value="${g.id}" ${g.id === currentGameId ? "selected" : ""}>${g.title} [${g.platform}]</option>`);
  document.getElementById("modal-assoc").classList.add("show");
}

async function doAssociate() {
  const id = document.getElementById("assoc-id").value;
  const type = document.getElementById("assoc-type").value;
  const gameId = document.getElementById("assoc-game-select").value || null;
  await fetch(`/api/${type==="file"?"files":"licenses"}/${id}/associate`,
    {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({game_id: gameId})});
  document.getElementById("modal-assoc").classList.remove("show");
  await Promise.all([loadFiles(), loadLicenses()]);
  updateStats();
}

async function quickAssoc(id, type, gameId) {
  gameId = gameId || null;
  const endpoint = type === "file" ? `/api/files/${id}/associate` : `/api/licenses/${id}/associate`;
  const res = await fetch(endpoint, {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({game_id: gameId})});
  if (res.ok) {
    const rowId = type === "file" ? `frow-${id}` : `lrow-${id}`;
    const row = document.getElementById(rowId);
    if (row) {
      row.classList.toggle("unassigned", !gameId);
      row.style.transition = "background .3s";
      row.style.background = "var(--played)22";
      setTimeout(() => row.style.background = "", 800);
    }
    if (type === "file") {
      const f = allFiles.find(x => x.id === id);
      if (f) { f.game_id = gameId ? parseInt(gameId) : null; }
    } else {
      const l = allLicenses.find(x => x.id === id);
      if (l) { l.game_id = gameId ? parseInt(gameId) : null; }
    }
    updateStats();
  }
}

// ─── Upload ───────────────────────────────────────────────────────────────────
function setupUpload() {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-upload-input");
  if (!dropZone || !fileInput) return;
  dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("dragover"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", e => { e.preventDefault(); dropZone.classList.remove("dragover"); handleUpload(e.dataTransfer.files); });
  fileInput.addEventListener("change", () => handleUpload(fileInput.files));
}

function uploadWithProgress(url, fd, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.upload.addEventListener('progress', e => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded, e.total);
    });
    xhr.addEventListener('load', () => {
      try {
        const data = JSON.parse(xhr.responseText);
        resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, data });
      } catch { resolve({ ok: false, status: xhr.status, data: { error: 'Invalid JSON' } }); }
    });
    xhr.addEventListener('error', () => reject(new Error('Network error')));
    xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));
    xhr.send(fd);
  });
}

async function handleUpload(files) {
  const q = document.getElementById("upload-queue");
  const filesArray = Array.from(files);

  // ── Detectare perechi BIN+CUE cu același stem ─────────────────────────────
  const pairMap = {}; // stem.lower → { bin: File, cue: File }
  filesArray.forEach(f => {
    const ext = f.name.split('.').pop().toLowerCase();
    if (ext === 'bin' || ext === 'cue') {
      const stem = f.name.replace(/\.(bin|cue)$/i, '').toLowerCase();
      if (!pairMap[stem]) pairMap[stem] = {};
      pairMap[stem][ext] = f;
    }
  });
  const cueHasPair = new Set();
  const binToCue   = {};
  Object.values(pairMap).forEach(p => {
    if (p.bin && p.cue) { cueHasPair.add(p.cue.name); binToCue[p.bin.name] = p.cue; }
  });

  let fileIdx = 0;
  for (const f of filesArray) {
    if (cueHasPair.has(f.name)) continue;

    const cueFile = binToCue[f.name] || null;
    const totalSize = f.size + (cueFile ? cueFile.size : 0);
    const idx = fileIdx++;
    const d = document.createElement("div");
    d.style.cssText = "background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:.65rem 1rem;margin-bottom:.4rem;font-size:.82rem;";
    const label = cueFile
      ? `<strong>${f.name}</strong> <span style="opacity:.6;font-size:.78rem">+ ${cueFile.name}</span>`
      : `<strong>${f.name}</strong>`;
    d.innerHTML = `<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem">
      <span class="spinner"></span>
      <span style="flex:1">${t("uploading","Uploading")} ${label} (${formatSize(totalSize)})</span>
      <span class="upload-percent" id="up-pct-${idx}">0%</span>
    </div>
    <div class="upload-bar-wrap"><div class="upload-bar" id="up-bar-${idx}"></div></div>`;
    q.prepend(d);

    const fd = new FormData(); fd.append("file", f);
    try {
      const result = await uploadWithProgress("/api/files/upload", fd, (loaded, total) => {
        const pct = Math.round(loaded / total * 100);
        const bar = document.getElementById("up-bar-" + idx);
        const txt = document.getElementById("up-pct-" + idx);
        if (bar) bar.style.width = pct + "%";
        if (txt) txt.textContent = pct + "%";
      });
      if (result.ok) {
        const r = result.data;
        let msg = `<span style="color:var(--played)">✅</span> ${label} — `
          + (r.type === "license" ? t("license_added","License added") : t("game_file_added","Game file added"))
          + (r.record.content_id ? " · " + r.record.content_id : "");

        if (cueFile) {
          const fdCue = new FormData();
          fdCue.append("file", cueFile);
          if (r.record && r.record.game_id) fdCue.append("game_id", r.record.game_id);
          try {
            const resCue = await uploadWithProgress("/api/files/upload", fdCue, null);
            msg += resCue.ok
              ? ` <span style="font-size:.72rem;color:var(--played)">+CUE ✅</span>`
              : ` <span style="font-size:.72rem;color:var(--unfin)">+CUE ⚠️</span>`;
          } catch {
            msg += ` <span style="font-size:.72rem;color:var(--danger)">+CUE ❌</span>`;
          }
        }

        d.innerHTML = msg;
      } else {
        d.innerHTML = `<span style="color:var(--danger)">❌</span> ${f.name} — ${result.data.error}`;
        d.style.borderColor = "var(--danger)44";
      }
    } catch {
      d.innerHTML = `<span style="color:var(--danger)">❌</span> ${f.name} — ${t("network_error","Network error")}`;
    }
  }
  await Promise.all([loadFiles(), loadLicenses()]);
  updateStats();
}

// ─── Image Gallery ────────────────────────────────────────────────────────────
async function loadImageGallery() {
  const g = document.getElementById("img-gallery");
  if (!g) return;
  g.innerHTML = '<div class="loading-row"><span class="spinner"></span></div>';
  const imgs = await fetch("/api/images").then(r => r.json());
  const status = document.getElementById("img-gallery-status");
  if (!imgs.length) {
    g.innerHTML = `<div class="loading-row" style="grid-column:1/-1">${t("no_images","No images uploaded yet.")}</div>`;
    if (status) status.textContent = "";
    return;
  }
  if (status) status.textContent = imgs.length + " " + t("images","images");
  g.innerHTML = imgs.map(img => `
    <div class="img-card">
      <img src="${img.url}" alt="${img.filename}" loading="lazy" onerror="this.src='';this.style.background='var(--bg)'">
      <div class="img-card-info">
        <div class="img-card-type">${img.type} · ${img.size}</div>
        <div class="img-card-name" title="${img.filename}">${img.filename}</div>
      </div>
      <div class="img-card-actions">
        <button class="img-copy-btn" onclick="copyImgUrl('${img.url}')" title="Copy URL">📋 ${img.url}</button>
        <button class="img-del-btn" onclick="deleteImg('${img.type}','${img.filename}',this)" title="Delete">🗑️</button>
      </div>
    </div>`).join('');
}

function copyImgUrl(url) {
  navigator.clipboard.writeText(window.location.origin + url).then(() => {
    const toast = document.createElement("div");
    toast.style.cssText = "position:fixed;bottom:1.5rem;right:1.5rem;background:var(--bg2);border:1px solid var(--cyan);color:var(--cyan);padding:.6rem 1.2rem;border-radius:8px;font-size:.83rem;z-index:9999;animation:modalIn .2s ease";
    toast.textContent = "✅ " + t("url_copied","URL copied!");
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
  });
}

async function deleteImg(type, filename, btn) {
  if (!confirm(t("delete_image_confirm","Delete image?"))) return;
  await fetch(`/api/images/${type}/${filename}`, {method: "DELETE"});
  btn.closest(".img-card").remove();
}

// ─── Folder Tree ──────────────────────────────────────────────────────────────
async function loadFolderTree() {
  const container = document.getElementById("folder-tree");
  if (!container) return;
  container.innerHTML = `<div class="loading-row"><span class="spinner"></span> ${t("reading_structure","Reading structure...")}</div>`;
  const tree = await fetch("/api/files/tree").then(r => r.json());
  const platforms = Object.keys(tree);
  if (!platforms.length) {
    container.innerHTML = `<div class="loading-row">
      ${t("no_structure","No organized structure found.")}<br>
      <small>${t("create_folders_hint","Create folders: /games/PS5/Game Title/ and place files there.")}</small>
    </div>`;
    return;
  }
  container.innerHTML = platforms.map(plat => {
    const games = tree[plat];
    const gameKeys = Object.keys(games);
    if (!gameKeys.length) return '';
    return `<div class="tree-platform">
      <div class="tree-plat-header" onclick="toggleTreePlat(this)">
        <span>▼</span> ${plat}
        <span style="font-size:.7rem;color:var(--textd);font-weight:400;margin-left:.5rem">${gameKeys.length} ${t("games_count","games")}</span>
      </div>
      <div class="tree-games-list">
        ${gameKeys.map(gname => {
          const info = games[gname];
          const hasFiles = info.files.length > 0;
          const hasLic = info.licenses.length > 0;
          const hasImg = info.images.length > 0;
          const fileList = [
            ...info.files.map(f => `<div class="tree-file-item"><span class="type-badge type-${f.name.split('.').pop().toUpperCase()}" style="font-size:.6rem">${f.name.split('.').pop().toUpperCase()}</span><span>${f.name}</span><span style="opacity:.5;margin-left:auto">${f.size}</span></div>`),
            info.licenses.length ? `<div class="tree-section-label">🔑 ${t("licenses","Licenses")} (${info.licenses.length})</div>` + info.licenses.map(l => `<div class="tree-file-item">🔑 ${l}</div>`).join('') : '',
            info.images.length ? `<div class="tree-section-label">🖼️ ${t("images","Images")} (${info.images.length})</div>` + info.images.map(i => `<div class="tree-file-item">🖼️ ${i}</div>`).join('') : ''
          ].join('');
          return `<div>
            <div class="tree-game-row">
              <div class="tree-game-name">🎮 ${gname}</div>
              <div class="tree-badges">
                <span class="tree-badge ${hasFiles?'has':'none'}">${info.files.length} ${t("files_count","files")}</span>
                <span class="tree-badge ${hasLic?'has':'none'}">${info.licenses.length} ${t("licenses_count","licenses")}</span>
                <span class="tree-badge ${hasImg?'has':'none'}">${info.images.length} img</span>
              </div>
              <div style="padding:0 .5rem;font-size:.72rem;color:var(--textd)">${plat}</div>
              <button class="tree-expand-btn" onclick="toggleTreeGame(this)">▼</button>
            </div>
            <div class="tree-file-list">${fileList}</div>
          </div>`;
        }).join('')}
      </div>
    </div>`;
  }).join('');
}

function toggleTreePlat(header) {
  const list = header.nextElementSibling;
  const isOpen = list.style.display !== 'none';
  list.style.display = isOpen ? 'none' : '';
  header.querySelector('span').textContent = isOpen ? '▶' : '▼';
}

function toggleTreeGame(btn) {
  const row = btn.closest('.tree-game-row');
  const detail = row.nextElementSibling;
  const isOpen = detail.classList.contains('open');
  detail.classList.toggle('open', !isOpen);
  btn.textContent = isOpen ? '▼' : '▲';
}

// ─── Inner tab switching ──────────────────────────────────────────────────────
function switchInnerTab(el, tabId) {
  document.querySelectorAll(".inner-tab").forEach(t => t.classList.remove("active"));
  el.classList.add("active");
  ["game-files-tab","licenses-tab","upload-tab","images-tab","tree-tab","saves-tab","dlc-tab"].forEach(id => {
    const panel = document.getElementById(id);
    if (panel) panel.style.display = id === tabId ? "block" : "none";
  });
}

// ─── Saves ────────────────────────────────────────────────────────────────────
let allSaves = [];

async function loadSaves() {
  const gameFilter = document.getElementById("saves-game-filter");
  const gid = gameFilter ? gameFilter.value : "";
  const url = gid ? `/api/saves?game_id=${gid}` : "/api/saves";
  allSaves = await fetch(url).then(r => r.json());
  renderSaves();
}

function renderSaves() {
  const el = document.getElementById("saves-list");
  if (!el) return;
  const status = document.getElementById("saves-status");
  if (status) status.textContent = allSaves.length + " " + t("saves","saves");
  if (!allSaves.length) {
    el.innerHTML = `<div class="loading-row">${t("no_saves","No saves. Upload .psv, .bin, .sav files etc.")}</div>`;
    return;
  }
  el.innerHTML = allSaves.map(s => {
    const isFolder   = s.filename && s.filename.endsWith('/');
    const icon       = isFolder ? '📁' : '💾';
    const dlLabel    = isFolder ? '⬇️ .zip' : '⬇️';
    const displayName = isFolder ? s.filename.slice(0, -1) + '/' : s.filename;
    return `
    <div class="file-row" id="srow-${s.id}">
      <div class="file-name" title="${s.filepath||''}">${icon} ${displayName}</div>
      <div><span class="platform-tag">${s.game_platform||s.platform||'?'}</span></div>
      <div style="font-size:.78rem;color:var(--textd)">${s.game_title||'<span style="opacity:.5">'+t("unassigned","Unassigned")+'</span>'}</div>
      <div style="font-size:.75rem;color:var(--textd)">${s.file_size_str||''}</div>
      <div class="file-actions">
        <a class="btn btn-outline btn-sm" href="/api/saves/${s.id}/download" title="Download">${dlLabel}</a>
        <button class="btn btn-danger btn-sm" onclick="deleteSave(${s.id})">🗑️</button>
      </div>
    </div>`;
  }).join('');
}

async function uploadSave() {
  const inp = document.getElementById("save-upload-input");
  if (!inp || !inp.files.length) return;
  const gameId = document.getElementById("save-game-select") ? document.getElementById("save-game-select").value : "";
  const st = document.getElementById("save-upload-status");
  if (st) st.innerHTML = `<span class="spinner"></span> ${t("uploading","Uploading")}...`;
  for (const file of inp.files) {
    const fd = new FormData();
    fd.append("file", file);
    if (gameId) fd.append("game_id", gameId);
    try {
      const res = await fetch("/api/saves/upload", {method: "POST", body: fd});
      if (res.ok) {
        if (st) st.textContent = `✅ ${file.name} — ${t("uploaded","Uploaded!")}`;
      } else {
        const d = await res.json();
        if (st) st.textContent = `❌ ${d.error||t("error","Error")}`;
      }
    } catch {
      if (st) st.textContent = `❌ ${t("network_error","Network error")}`;
    }
  }
  inp.value = "";
  setTimeout(() => { if (st) st.textContent = ""; }, 3000);
  await loadSaves();
}

async function uploadSaveFolder() {
  const inp = document.getElementById("save-folder-input");
  if (!inp || !inp.files.length) return;
  const gameId = document.getElementById("save-game-select")?.value || "";
  const st     = document.getElementById("save-upload-status");
  const files  = Array.from(inp.files);

  // webkitRelativePath = "FolderName/sub/file.ext" — primul component e numele folderului
  const folderName  = files[0].webkitRelativePath.split("/")[0] || "save_folder";
  const totalSize   = files.reduce((s, f) => s + f.size, 0);
  const fileCount   = files.length;

  if (st) st.innerHTML = `<span class="spinner"></span> ${t("upload_folder","Uploading")} <strong>${folderName}/</strong> (${fileCount} ${t("files_count","files")}, ${formatSize(totalSize)})...`;

  const fd = new FormData();
  fd.append("folder_name", folderName);
  if (gameId) fd.append("game_id", gameId);
  files.forEach(f => {
    fd.append("files[]", f);
    fd.append("relative_paths[]", f.webkitRelativePath);
  });

  try {
    const res = await fetch("/api/saves/upload-folder", {method: "POST", body: fd});
    if (res.ok) {
      if (st) st.textContent = `✅ ${folderName}/ ${t("uploaded","Uploaded!")} — ${fileCount} ${t("files_count","files")}, ${formatSize(totalSize)}`;
    } else {
      const d = await res.json();
      if (st) st.textContent = `❌ ${d.error || t("error","Error")}`;
    }
  } catch {
    if (st) st.textContent = `❌ ${t("network_error","Network error")}`;
  }

  inp.value = "";
  setTimeout(() => { if (st) st.textContent = ""; }, 5000);
  await loadSaves();
}

async function deleteSave(id) {
  if (!confirm(t("delete_confirm","Delete?"))) return;
  await fetch(`/api/saves/${id}`, {method: "DELETE"});
  loadSaves();
}

// ─── DLC ──────────────────────────────────────────────────────────────────────
let allDlc = [];

async function loadDlc() {
  const gameFilter = document.getElementById("dlc-game-filter");
  const gid = gameFilter ? gameFilter.value : "";
  const url = gid ? `/api/dlc?game_id=${gid}` : "/api/dlc";
  allDlc = await fetch(url).then(r => r.json());
  renderDlc();
}

function renderDlc() {
  const el = document.getElementById("dlc-list");
  if (!el) return;
  const status = document.getElementById("dlc-status");
  if (status) status.textContent = allDlc.length + " DLC";
  if (!allDlc.length) {
    el.innerHTML = `<div class="loading-row">${t("no_dlc","No DLC. Upload .pkg files etc.")}</div>`;
    return;
  }
  el.innerHTML = allDlc.map(d => `
    <div class="file-row" id="drow-${d.id}">
      <div class="file-name" title="${d.filepath||''}">📦 ${d.filename}</div>
      <div><span class="type-badge type-${d.file_type||'PKG'}">${d.file_type||'PKG'}</span></div>
      <div><span class="platform-tag">${d.game_platform||d.platform||'?'}</span></div>
      <div style="font-size:.78rem;color:var(--textd)">${d.game_title||'<span style="opacity:.5">'+t("unassigned","Unassigned")+'</span>'}</div>
      <div style="font-size:.75rem;color:var(--textd)">${d.content_id||''}</div>
      <div style="font-size:.75rem;color:var(--textd)">${d.file_size_str||''}</div>
      <div class="file-actions">
        <a class="btn btn-outline btn-sm" href="/api/dlc/${d.id}/download" title="Download">⬇️</a>
        <button class="btn btn-danger btn-sm" onclick="deleteDlc(${d.id})">🗑️</button>
      </div>
    </div>`).join('');
}

async function uploadDlc() {
  const inp = document.getElementById("dlc-upload-input");
  if (!inp || !inp.files.length) return;
  const gameId = document.getElementById("dlc-game-select") ? document.getElementById("dlc-game-select").value : "";
  const st = document.getElementById("dlc-upload-status");
  if (st) st.innerHTML = `<span class="spinner"></span> ${t("uploading","Uploading")}...`;
  for (const file of inp.files) {
    const fd = new FormData();
    fd.append("file", file);
    if (gameId) fd.append("game_id", gameId);
    try {
      const res = await fetch("/api/dlc/upload", {method: "POST", body: fd});
      if (res.ok) {
        if (st) st.textContent = `✅ ${file.name} — ${t("uploaded","Uploaded!")}`;
      } else {
        const d = await res.json();
        if (st) st.textContent = `❌ ${d.error||t("error","Error")}`;
      }
    } catch {
      if (st) st.textContent = `❌ ${t("network_error","Network error")}`;
    }
  }
  inp.value = "";
  setTimeout(() => { if (st) st.textContent = ""; }, 3000);
  await loadDlc();
}

async function deleteDlc(id) {
  if (!confirm(t("delete_confirm","Delete?"))) return;
  await fetch(`/api/dlc/${id}`, {method: "DELETE"});
  loadDlc();
}

function populateSaveDlcGameSelects() {
  const html = `<option value="">${t("all_games","All games")}</option>` +
    allGames.map(g => `<option value="${g.id}">${g.title} [${g.platform}]</option>`).join('');
  ["saves-game-filter","dlc-game-filter","save-game-select","dlc-game-select"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = id.includes("filter")
      ? `<option value="">${t("all_games","All games")}</option>` + allGames.map(g => `<option value="${g.id}">${g.title} [${g.platform}]</option>`).join('')
      : `<option value="">${t("no_game","— No game —")}</option>` + allGames.map(g => `<option value="${g.id}">${g.title} [${g.platform}]</option>`).join('');
  });
}

// ─── Redump verification ──────────────────────────────────────────────────────
const rdumpResults = {}; // cache rezultate per fileId

async function verifyRedump(fileId) {
  const btn = document.getElementById("rdv-" + fileId);
  if (!btn) return;
  const origHtml = btn.innerHTML;
  btn.innerHTML = '<span class="spinner" style="width:10px;height:10px;border-width:2px"></span>';
  btn.disabled = true;

  try {
    const r = await fetch(`/api/redump/identify/${fileId}`, {method:"POST"});
    const d = await r.json();

    if (d.error) {
      btn.innerHTML = '⚠️';
      btn.title = d.error;
      btn.disabled = false;
      setTimeout(() => { btn.innerHTML = '🔍'; btn.title = "Verify with Redump.org"; }, 4000);
      return;
    }

    rdumpResults[fileId] = d; // salvează în cache

    const row = document.getElementById("frow-" + fileId);
    if (d.match) {
      const m = d.match;
      // Înlocuiește butonul cu ✅ clicabil care redeschide editorul
      btn.outerHTML = `<button class="btn btn-sm" id="rdv-${fileId}" onclick="openRedumpModal(${fileId})"
        title="✅ ${m.game_name} — click pentru editor"
        style="font-size:.72rem;padding:2px 6px;background:transparent;color:var(--played);border:1px solid var(--played)44">✅</button>`;
      // Afișează titlul lângă filename dacă nu există
      const nameEl = row && row.querySelector(".file-name");
      if (nameEl && m.game_name) {
        const existingTag = nameEl.querySelector(".rdump-title");
        if (!existingTag) {
          nameEl.insertAdjacentHTML("beforeend",
            `<span class="rdump-title" style="color:var(--cyan);font-size:.72rem;margin-left:.5rem">${m.game_name}${m.disc_name && m.disc_name !== m.game_name + '.bin' ? ' — ' + m.disc_name.replace(/\.bin$/i,'') : ''}</span>`);
        }
      }
    } else {
      // Hash calculat dar nu e în nicio bază Redump importată
      btn.innerHTML = '❓';
      btn.title = `Not in Redump — click for details`;
      btn.disabled = false;
      btn.setAttribute('onclick', `openRedumpModal(${fileId})`);
    }

    // Deschide automat editorul cu rezultatul
    openRedumpModal(fileId);
  } catch(e) {
    btn.innerHTML = origHtml;
    btn.disabled = false;
    console.error("Redump verify error:", e);
  }
}

function openRedumpModal(fileId) {
  const d = rdumpResults[fileId];
  if (!d) return;
  const m = d.match;

  document.getElementById('rdump-fid').value = fileId;

  const statusBar = document.getElementById('rdump-status-bar');
  if (m) {
    statusBar.style.cssText = 'background:var(--played)11;border:1px solid var(--played)44;border-radius:8px;padding:.65rem .9rem;margin-bottom:1rem;font-size:.82rem;color:var(--played)';
    statusBar.innerHTML = `✅ <strong>${t("redump_found","Found in Redump database")}</strong>`;
    document.getElementById('rdump-title').value = m.game_name || '';
    const rawDisc = m.disc_name ? m.disc_name.replace(/\.bin$/i, '') : '';
    document.getElementById('rdump-disc').value = (rawDisc && rawDisc !== m.game_name) ? rawDisc : '';
    document.getElementById('rdump-plat').value = m.platform || '';
  } else {
    statusBar.style.cssText = 'background:var(--unfin)11;border:1px solid var(--unfin)44;border-radius:8px;padding:.65rem .9rem;margin-bottom:1rem;font-size:.82rem;color:var(--unfin)';
    statusBar.innerHTML = `❓ <strong>${t("redump_not_found","Not found in Redump — you can manually add a title")}</strong>`;
    document.getElementById('rdump-title').value = '';
    document.getElementById('rdump-disc').value = '';
    document.getElementById('rdump-plat').value = '';
  }

  document.getElementById('rdump-hashes').textContent =
    `MD5: ${d.md5 || '—'}${d.crc32 ? '   ·   CRC32: ' + d.crc32 : ''}`;

  const applyBtn = document.getElementById('rdump-apply-btn');
  applyBtn.innerHTML = '✅ ' + t("apply_title","Apply title");
  applyBtn.disabled = false;

  document.getElementById('modal-redump').classList.add('show');
}

async function applyRedumpResult() {
  const fileId = document.getElementById('rdump-fid').value;
  const title  = document.getElementById('rdump-title').value.trim();
  const disc   = document.getElementById('rdump-disc').value.trim();
  const applyBtn = document.getElementById('rdump-apply-btn');

  if (!title) {
    applyBtn.textContent = '⚠️ ' + t("enter_title","Enter a title!");
    setTimeout(() => { applyBtn.innerHTML = '✅ ' + t("apply_title","Apply title"); }, 2000);
    return;
  }

  applyBtn.disabled = true;
  applyBtn.innerHTML = '<span class="spinner" style="width:10px;height:10px;border-width:2px"></span>';

  try {
    await fetch(`/api/files/${fileId}/edit`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({detected_title: title})
    });

    // Actualizează afișajul inline din rând
    const row = document.getElementById('frow-' + fileId);
    if (row) {
      const nameEl = row.querySelector('.file-name');
      if (nameEl) {
        const displayText = title + (disc ? ' — ' + disc : '');
        const tag = nameEl.querySelector('.rdump-title');
        if (tag) { tag.textContent = displayText; }
        else {
          nameEl.insertAdjacentHTML('beforeend',
            `<span class="rdump-title" style="color:var(--cyan);font-size:.72rem;margin-left:.5rem">${displayText}</span>`);
        }
      }
    }

    document.getElementById('modal-redump').classList.remove('show');
  } catch(e) {
    applyBtn.innerHTML = '✅ ' + t("apply_title","Apply title");
    applyBtn.disabled = false;
    console.error("Apply redump error:", e);
  }
}

// ─── Modal close ─────────────────────────────────────────────────────────────
document.querySelectorAll(".modal-overlay").forEach(m => m.addEventListener("click", e => {
  if (e.target === m) m.classList.remove("show");
}));

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  await loadLanguages();
  await Promise.all([loadGamesForAssoc(), loadFiles(), loadLicenses()]);
  updateStats();
  setupUpload();
  populateSaveDlcGameSelects();
}

init();
