// ─── Library page JS ─────────────────────────────────────────────────────────
let currentMedia = "";

// ─── Games ───────────────────────────────────────────────────────────────────
async function loadGames() {
  try {
    const params = new URLSearchParams({
      search: document.getElementById("search").value,
      status: currentStatus,
      genre: document.getElementById("filter-genre").value
    });
    const rawGames = await fetch(`/api/games?${params}`).then(r => r.json());
    allGames = currentMedia ? rawGames.filter(g => g.media_type === currentMedia) : rawGames;
    renderGames();
  } catch(e) {
    console.error("loadGames error:", e);
    const grid = document.getElementById("games-grid");
    if (grid) grid.innerHTML = `<div class="empty"><div class="empty-icon">⚠️</div><h3>${t("network_error","Network error")}</h3></div>`;
  }
}

async function loadGenres() {
  const g = await fetch("/api/genres").then(r => r.json());
  const s = document.getElementById("filter-genre");
  s.innerHTML = `<option value="">${t("all_genres","All genres")}</option>`;
  g.forEach(x => s.innerHTML += `<option>${x}</option>`);
}

function renderGames() {
  const grid = document.getElementById("games-grid");
  if (!allGames.length) {
    grid.innerHTML = `<div class="empty"><div class="empty-icon">🕹️</div><h3>${t("no_games","No games")}</h3></div>`;
    return;
  }
  grid.innerHTML = allGames.map(g => {
    const gf = allFiles.filter(f => f.game_id === g.id);
    const gl = allLicenses.filter(l => l.game_id === g.id);
    const dots = (gf.some(f => f.file_type==="ISO") ? '<span class="file-dot iso" title="ISO"></span>' : '') +
                 (gf.some(f => f.file_type==="PKG") ? '<span class="file-dot pkg" title="PKG"></span>' : '') +
                 (gl.length ? '<span class="file-dot lic" title="License"></span>' : '');
    return `<div class="game-card">
      <div class="game-cover" onclick="location.href='/joc/${g.id}'" style="cursor:pointer">
        ${g.cover_url ? `<img src="${g.cover_url}" alt="${esc(g.title)}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=no-cover>🎮<span>NO IMG</span></div>'">` :
          '<div class="no-cover">🎮<span>NO IMG</span></div>'}
        <div class="status-badge status-${g.status}">${g.status}</div>
        ${dots ? `<div class="files-indicator">${dots}</div>` : ''}
      </div>
      <div class="game-info">
        <a class="game-title" href="/joc/${g.id}" title="${esc(g.title)}" style="text-decoration:none;color:inherit;display:block">${g.title}</a>
        <div class="game-meta">
          <span class="platform-tag">${g.platform}</span>
          ${g.genre ? `<span>${g.genre.split(",")[0]}</span>` : ''}
          ${g.metacritic ? `<span style="color:var(--played)">MC ${g.metacritic}</span>` : ''}
        </div>
        ${(g.media_type && g.media_type !== "Digital") ? `<div style="margin-bottom:5px"><span class="media-badge media-${g.media_type}">${mediaLabel(g.media_type)}</span></div>` : ""}
        <div class="stars">${[1,2,3,4,5].map(i => `<span class="star ${i<=g.rating?'filled':''}">★</span>`).join('')}</div>
        <div class="card-actions">
          <button class="btn btn-edit" onclick="openGameDownload(${g.id},${JSON.stringify(g.title).replace(/"/g,'&quot;')},'${g.platform}')" title="Download">⬇️</button>
          <button class="btn btn-edit" onclick="editGame(${g.id})">✏️</button>
          <button class="btn btn-danger" onclick="delGame(${g.id})">🗑️</button>
        </div>
      </div>
    </div>`;
  }).join('');
}

// ─── Detail modal ─────────────────────────────────────────────────────────────
function showDetail(id) {
  const g = allGames.find(x => x.id === id);
  if (!g) return;
  currentDetailId = id;
  const b = document.getElementById("d-banner");
  if (g.banner_url) { b.src = g.banner_url; b.className = "detail-banner show"; }
  else b.className = "detail-banner";
  document.getElementById("d-cover").src = g.cover_url || "";
  document.getElementById("d-title").textContent = g.title;
  document.getElementById("d-platform").textContent = g.platform;
  const sb = document.getElementById("d-status");
  sb.textContent = g.status; sb.className = `status-badge status-${g.status}`;
  document.getElementById("d-stars").innerHTML = [1,2,3,4,5].map(i =>
    `<span class="star ${i<=g.rating?'filled':''}">★</span>`).join('');
  let m = "";
  if (g.genre)        m += `<div><strong>${t("gen_label","Gen")}:</strong> ${g.genre}</div>`;
  if (g.developer)    m += `<div><strong>${t("dev_label","Dev")}:</strong> ${g.developer}</div>`;
  if (g.publisher)    m += `<div><strong>${t("publisher_label","Publisher")}:</strong> ${g.publisher}</div>`;
  if (g.release_date) m += `<div><strong>${t("launched","Lansat")}:</strong> ${g.release_date}</div>`;
  if (g.metacritic)   m += `<div><strong>${t("metacritic","Metacritic")}:</strong> <span style="color:var(--played)">${g.metacritic}</span></div>`;
  document.getElementById("d-meta").innerHTML = m;
  document.getElementById("d-desc").textContent = g.description || "";
  const pw = document.getElementById("d-pscode-wrap");
  if (g.ps_code) { pw.style.display = "block"; document.getElementById("d-pscode").textContent = g.ps_code; }
  else pw.style.display = "none";
  const phyw = document.getElementById("d-physical-wrap");
  const mt = g.media_type || "Digital";
  if (mt !== "Digital" || g.physical_edition || g.physical_condition) {
    phyw.style.display = "block";
    const mb = document.getElementById("d-media-badge");
    mb.textContent = mediaLabel(mt); mb.className = "media-badge media-" + mt;
    document.getElementById("d-phys-edition").textContent = g.physical_edition || "";
    document.getElementById("d-phys-condition").textContent = g.physical_condition ? (t("condition_label","Condition") + ": " + g.physical_condition) : "";
    document.getElementById("d-phys-notes").textContent = g.physical_notes || "";
    document.getElementById("d-phys-barcode").textContent = g.physical_barcode ? (t("barcode_label","Barcode") + ": " + g.physical_barcode) : "";
  } else phyw.style.display = "none";
  const gf = allFiles.filter(f => f.game_id === id);
  const gl = allLicenses.filter(l => l.game_id === id);
  let fh = gf.map(f => `<span class="file-chip"><span class="type-badge type-${f.file_type}">${f.file_type}</span>${f.filename}<a href="/api/files/${f.id}/download">⬇️</a></span>`).join('');
  fh += gl.map(l => `<span class="file-chip"><span class="type-badge type-${l.license_type}">${l.license_type}</span>${l.filename}<a href="/api/licenses/${l.id}/download">⬇️</a></span>`).join('');
  document.getElementById("d-files-list").innerHTML = fh || `<span style="color:var(--textd);font-size:.79rem">${t("no_associated_files","No associated files")}</span>`;
  document.getElementById("d-edit-btn").onclick = () => { closeModal("modal-detail"); editGame(id); };
  document.getElementById("d-del-btn").onclick = () => { if (confirm(t("delete_game_confirm","Delete game?"))) delGame(id).then(() => closeModal("modal-detail")); };
  document.getElementById("modal-detail").classList.add("show");
}

// ─── Add/Edit modal ───────────────────────────────────────────────────────────
function openAddModal(game = null) {
  document.getElementById("modal-title").textContent = game ? t("modal_edit_title","Edit Game") : t("modal_add_title","Add Game");
  document.getElementById("edit-id").value = game ? game.id : "";
  document.getElementById("f-rawg-id").value = game?.rawg_id || "";
  document.getElementById("f-title").value = game?.title || "";
  document.getElementById("f-genre").value = game?.genre || "";
  document.getElementById("f-platform").value = game?.platform || "PS5";
  document.getElementById("f-status").value = game?.status || "Wishlist";
  document.getElementById("f-developer").value = game?.developer || "";
  document.getElementById("f-publisher").value = game?.publisher || "";
  document.getElementById("f-release").value = game?.release_date || "";
  document.getElementById("f-pscode").value = game?.ps_code || "";
  document.getElementById("f-desc").value = game?.description || "";
  document.getElementById("f-cover").value = game?.cover_url || "";
  document.getElementById("f-banner").value = game?.banner_url || "";
  document.getElementById("ps-search-input").value = "";
  document.getElementById("ps-search-results").style.display = "none";
  document.getElementById("imported-banner").classList.remove("show");
  const note = document.getElementById("modal-add-note");
  if (note) note.style.display = "none";
  setRating(game?.rating || 0);
  setMediaType(game?.media_type || "Digital");
  document.getElementById("f-phys-edition").value = game?.physical_edition || "";
  document.getElementById("f-phys-condition").value = game?.physical_condition || "";
  document.getElementById("f-phys-barcode").value = game?.physical_barcode || "";
  document.getElementById("f-phys-notes").value = game?.physical_notes || "";
  // Show cover/banner previews
  const cp = document.getElementById("cover-preview");
  const bp = document.getElementById("banner-preview");
  if (game?.cover_url) { cp.src = game.cover_url; cp.classList.add("show"); } else { cp.src = ""; cp.classList.remove("show"); }
  if (game?.banner_url) { bp.src = game.banner_url; bp.classList.add("show"); } else { bp.src = ""; bp.classList.remove("show"); }
  // Screenshots & other images
  document.getElementById("screenshot-thumbs").innerHTML = "";
  document.getElementById("other-thumbs").innerHTML = "";
  if (game && game.id) {
    loadGameScreenshots(game.id, "screenshot-thumbs", "screenshot");
    loadGameScreenshots(game.id, "other-thumbs", "other");
  }
  // Video links
  populateVideoLinks(game?.video_links || []);
  // Saves & DLC section — always visible, but disabled in add mode
  const mediaSection = document.getElementById("modal-game-media-section");
  const mediaDisabledMsg = document.getElementById("modal-media-disabled-msg");
  const mediaTabs = mediaSection ? mediaSection.querySelector("[style*='display:flex']") || mediaSection.querySelector("div > div:first-child") : null;
  if (mediaSection) {
    if (game && game.id) {
      if (mediaDisabledMsg) mediaDisabledMsg.style.display = "none";
      mediaSection.querySelectorAll(".modal-media-tab, #modal-file-upload-input, #modal-save-upload-input, #modal-dlc-upload-input").forEach(el => el.disabled = false);
      mediaSection.querySelectorAll("label.btn").forEach(el => el.style.pointerEvents = "");
      const firstTab = mediaSection.querySelector(".modal-media-tab");
      if (firstTab) switchModalMediaTab(firstTab, "modal-files-panel");
      loadModalFiles(game.id);
      loadModalSaves(game.id);
      loadModalDlc(game.id);
    } else {
      if (mediaDisabledMsg) mediaDisabledMsg.style.display = "block";
      document.getElementById("modal-files-list").innerHTML = "";
      document.getElementById("modal-saves-list").innerHTML = "";
      document.getElementById("modal-dlc-list").innerHTML = "";
      mediaSection.querySelectorAll(".modal-media-tab").forEach(el => el.disabled = true);
      mediaSection.querySelectorAll("label.btn").forEach(el => el.style.pointerEvents = "none");
    }
  }
  document.getElementById("modal-add").classList.add("show");
}

function closeModal(id) { document.getElementById(id).classList.remove("show"); }

function setRating(v) {
  currentRating = v;
  document.querySelectorAll(".star-input").forEach(s => s.classList.toggle("active", parseInt(s.dataset.val) <= v));
}

let currentMediaType = "Digital";
function setMediaType(val) {
  currentMediaType = val;
  document.querySelectorAll(".media-btn").forEach(b => b.classList.toggle("active", b.dataset.val === val));
  document.getElementById("physical-extra").style.display = val !== "Digital" ? "block" : "none";
}

let _saving = false;
async function saveGame() {
  if (_saving) return;
  _saving = true;
  try {
  const title = document.getElementById("f-title").value.trim();
  if (!title) { alert(t("title_required","Titlul e obligatoriu!")); _saving = false; return; }
  const id = document.getElementById("edit-id").value;
  const data = {
    title,
    genre: document.getElementById("f-genre").value.trim(),
    platform: document.getElementById("f-platform").value,
    status: document.getElementById("f-status").value,
    rating: currentRating,
    cover_url: document.getElementById("f-cover").value.trim(),
    banner_url: document.getElementById("f-banner").value.trim(),
    description: document.getElementById("f-desc").value.trim(),
    ps_code: document.getElementById("f-pscode").value.trim(),
    developer: document.getElementById("f-developer").value.trim(),
    publisher: document.getElementById("f-publisher").value.trim(),
    release_date: document.getElementById("f-release").value.trim(),
    rawg_id: document.getElementById("f-rawg-id").value || null,
    media_type: currentMediaType,
    physical_edition: document.getElementById("f-phys-edition").value,
    physical_condition: document.getElementById("f-phys-condition").value,
    physical_barcode: document.getElementById("f-phys-barcode").value.trim(),
    physical_notes: document.getElementById("f-phys-notes").value.trim(),
    video_links: getVideoLinks()
  };
  const url = id ? `/api/games/${id}` : "/api/games";
  const method = id ? "PUT" : "POST";
  const res = await fetch(url, {method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
  if (!res.ok) { alert(t("save_error","Eroare la salvare!")); return; }
  const savedGame = await res.json();

  // Dacă e add nou → activează secțiunea Saves & DLC fără a închide modalul
  if (!id && savedGame && savedGame.id) {
    document.getElementById("edit-id").value = savedGame.id;
    const mediaDisabledMsg = document.getElementById("modal-media-disabled-msg");
    if (mediaDisabledMsg) mediaDisabledMsg.style.display = "none";
    const mediaSection = document.getElementById("modal-game-media-section");
    if (mediaSection) {
      mediaSection.querySelectorAll(".modal-media-tab").forEach(el => el.disabled = false);
      mediaSection.querySelectorAll("label.btn").forEach(el => el.style.pointerEvents = "");
      const firstTab = mediaSection.querySelector(".modal-media-tab");
      if (firstTab) switchModalMediaTab(firstTab, "modal-files-panel");
      loadModalFiles(savedGame.id);
      loadModalSaves(savedGame.id);
      loadModalDlc(savedGame.id);
    }
  }

  // Asociere fișier din File Manager (flux add_for_file)
  if (window._pendingFileId && savedGame && savedGame.id) {
    try {
      await fetch(`/api/files/${window._pendingFileId}/associate`, {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({game_id: savedGame.id})
      });
    } catch(e) { console.warn("Associate file failed:", e); }
    window._pendingFileId = null;
    showToast("✅ " + t("game_added_file_linked","Game added and file linked!"));
  }

  closeModal("modal-add");
  await loadGames();
  loadGenres();
  } finally { _saving = false; }
}

async function delGame(id) {
  if (!confirm(t("delete_game_confirm","Delete game?"))) return;
  await fetch(`/api/games/${id}`, {method: "DELETE"});
  loadGames();
}

function editGame(id) { const g = allGames.find(x => x.id === id); if (g) openAddModal(g); }

// ─── PS/Metadata Search ───────────────────────────────────────────────────────
const psInput = document.getElementById("ps-search-input");
const psResults = document.getElementById("ps-search-results");

psInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = psInput.value.trim();
  if (!q || q.length < 2) { psResults.style.display = "none"; return; }
  searchTimer = setTimeout(() => doSearch(q), 420);
});

document.addEventListener("click", e => {
  if (!e.target.closest(".ps-search-wrap")) psResults.style.display = "none";
});

async function doSearch(q) {
  if (!hasAnyApi) {
    psResults.innerHTML = `<div style="padding:.7rem;font-size:.8rem;color:var(--textd)">⚠️ ${t("add_rawg_key","Add an API key (RAWG/IGDB/MobyGames)")}</div>`;
    psResults.style.display = "block"; return;
  }
  psResults.innerHTML = `<div style="padding:.7rem;font-size:.8rem"><span class="spinner"></span> ${t("searching","Caut...")}</div>`;
  psResults.style.display = "block";
  const res = await fetch(`/api/metadata/search?q=${encodeURIComponent(q)}`);
  const data = await res.json();
  if (!res.ok) { psResults.innerHTML = `<div style="padding:.7rem;font-size:.8rem;color:var(--danger)">${data.error||"Eroare"}</div>`; return; }
  if (!data.length) { psResults.innerHTML = `<div style="padding:.7rem;font-size:.8rem;color:var(--textd)">${t("no_results","Niciun rezultat")}</div>`; return; }
  psResults.innerHTML = data.map((g, i) => `<div class="search-result-item" onclick="selectSearchResult(${i})">
    <img class="search-result-thumb" src="${g.cover_url||''}" onerror="this.style.opacity=0">
    <div><div class="search-result-title">${g.title}</div>
    <div class="search-result-meta">
      ${g.platform ? `<span class="platform-tag">${g.platform}</span>` : ''}
      ${g.release_date ? `<span>${g.release_date.slice(0,4)}</span>` : ''}
      ${g.metacritic ? `<span class="mc-badge">MC ${g.metacritic}</span>` : ''}
      <span style="color:var(--textd);font-size:.65rem">${g.source||''}</span>
    </div></div></div>`).join('');
  psResults._data = data;
}

async function selectSearchResult(i) {
  const data = psResults._data || [];
  const item = data[i];
  if (!item) return;
  psResults.innerHTML = `<div style="padding:.7rem;font-size:.8rem"><span class="spinner"></span> ${t("loading_details","Loading details...")}</div>`;
  let g;
  if (item.source === "RAWG" && item.rawg_id) {
    g = await fetch(`/api/rawg/game/${item.rawg_id}`).then(r => r.json());
  } else {
    const params = new URLSearchParams({source: item.source, title: item.title});
    if (item.igdb_id) params.set("id", item.igdb_id);
    if (item.moby_id) params.set("id", item.moby_id);
    g = await fetch(`/api/metadata/detail?${params}`).then(r => r.json());
  }
  psResults.style.display = "none";
  if (g.error) { alert(t("error","Eroare")); return; }
  document.getElementById("f-rawg-id").value = g.rawg_id || "";
  document.getElementById("f-title").value = g.title || "";
  document.getElementById("f-genre").value = g.genre || "";
  document.getElementById("f-platform").value = g.platform || "PS5";
  document.getElementById("f-developer").value = g.developer || "";
  document.getElementById("f-publisher").value = g.publisher || "";
  document.getElementById("f-release").value = g.release_date || "";
  document.getElementById("f-pscode").value = g.ps_code || "";
  document.getElementById("f-desc").value = g.description || "";
  document.getElementById("f-cover").value = g.cover_url || "";
  document.getElementById("f-banner").value = g.banner_url || "";
  psInput.value = g.title;
  document.getElementById("imported-thumb").src = g.cover_url || "";
  document.getElementById("imported-banner").classList.add("show");
  // Show preview
  if (g.cover_url) {
    const cp = document.getElementById("cover-preview");
    cp.src = g.cover_url; cp.classList.add("show");
  }
}

// ─── Image Browser ────────────────────────────────────────────────────────────
let browseTargetField = null, browseTargetPreview = null, allBrowseImages = [];

async function openImageBrowser(fieldId, previewId) {
  browseTargetField = fieldId;
  browseTargetPreview = previewId;
  document.getElementById("browse-img-title").textContent = "🔍 " + t("browse_images_title","Alege imagine de pe server");
  document.getElementById("browse-img-search").placeholder = t("browse_search_placeholder","Search images...");
  document.getElementById("browse-img-search").value = "";
  document.getElementById("browse-img-grid").innerHTML = '<div class="browse-empty"><span class="spinner"></span></div>';
  document.getElementById("modal-browse-img").classList.add("show");
  try {
    allBrowseImages = await fetch("/api/images/browse").then(r => r.json());
    renderBrowseImages(allBrowseImages);
  } catch {
    document.getElementById("browse-img-grid").innerHTML = `<div class="browse-empty">${t("error","Eroare")}</div>`;
  }
}

function filterBrowseImages() {
  const q = document.getElementById("browse-img-search").value.trim().toLowerCase();
  if (!q) { renderBrowseImages(allBrowseImages); return; }
  renderBrowseImages(allBrowseImages.filter(img =>
    img.filename.toLowerCase().includes(q) ||
    (img.source||"").toLowerCase().includes(q) ||
    (img.type||"").toLowerCase().includes(q)
  ));
}

function renderBrowseImages(images) {
  const grid = document.getElementById("browse-img-grid");
  if (!images.length) {
    grid.innerHTML = `<div class="browse-empty">${t("no_server_images","No images available on server.")}</div>`;
    return;
  }
  grid.innerHTML = images.map((img, i) => `
    <div class="browse-item" onclick="selectBrowseImage(${i})" title="${img.filename}">
      <img src="${img.url}" alt="${img.filename}" onerror="this.style.opacity=0.2" loading="lazy">
      <div class="browse-item-info">${img.filename}</div>
      <div class="browse-item-source">${img.source} · ${img.size}</div>
    </div>`).join('');
  grid._images = images;
}

function selectBrowseImage(index) {
  const grid = document.getElementById("browse-img-grid");
  const images = grid._images || allBrowseImages;
  const img = images[index];
  if (!img) return;
  if (browseTargetField) {
    const field = document.getElementById(browseTargetField);
    field.value = img.url;
    field.dispatchEvent(new Event("input"));
  }
  if (browseTargetPreview) {
    const prev = document.getElementById(browseTargetPreview);
    prev.src = img.url; prev.classList.add("show");
  }
  closeBrowseModal();
}

function closeBrowseModal() {
  document.getElementById("modal-browse-img").classList.remove("show");
}

// ─── Image Upload ─────────────────────────────────────────────────────────────
async function uploadImageFile(file, imgType, gameId = null) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("type", imgType);
  if (gameId) fd.append("game_id", gameId);
  const res = await fetch("/api/images/upload", {method: "POST", body: fd});
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Eroare upload");
  return data;
}

function setupImgInput(inputId, urlFieldId, previewId, progressId, imgType) {
  const inp = document.getElementById(inputId);
  if (!inp) return;
  inp.addEventListener("change", async () => {
    const file = inp.files[0];
    if (!file) return;
    const prog = document.getElementById(progressId);
    const prev = document.getElementById(previewId);
    prog.textContent = `⏳ ${t("uploading","Uploadez")}...`;
    prog.classList.add("show");
    try {
      const gameId = document.getElementById("edit-id").value || null;
      const result = await uploadImageFile(file, imgType, gameId);
      document.getElementById(urlFieldId).value = result.url;
      prev.src = result.url; prev.classList.add("show");
      prog.textContent = `✅ ${t("uploaded","Uploadat!")}`;
      setTimeout(() => prog.classList.remove("show"), 2500);
    } catch(e) {
      prog.textContent = "❌ " + e.message;
      setTimeout(() => prog.classList.remove("show"), 3000);
    }
    inp.value = "";
  });
  document.getElementById(urlFieldId).addEventListener("input", function() {
    const prev = document.getElementById(previewId);
    if (this.value.startsWith("http") || this.value.startsWith("/")) {
      prev.src = this.value; prev.classList.add("show");
    } else { prev.classList.remove("show"); }
  });
}

// ─── Fetch images from API ────────────────────────────────────────────────────
async function fetchGameImages(gameId) {
  const btn = document.getElementById("btn-fetch-images");
  if (btn) { btn.textContent = `⏳ ${t("downloading","Downloading...")}`; btn.disabled = true; }
  try {
    const res = await fetch(`/api/games/${gameId}/fetch-images`, {method: "POST"});
    const data = await res.json();
    if (res.ok) {
      const r = data.results;
      const msgs = [];
      if (r.cover === "already_local") msgs.push(t("cover_already_local","cover: already local"));
      else if (r.cover && r.cover.startsWith("/")) msgs.push("✅ " + t("cover_saved","cover saved"));
      else msgs.push("❌ " + t("cover_error","cover: error"));
      if (r.banner === "already_local") msgs.push(t("banner_already_local","banner: deja local"));
      else if (r.banner && r.banner.startsWith("/")) msgs.push("✅ " + t("banner_saved","banner salvat"));
      else msgs.push("❌ " + t("banner_error","banner: eroare"));
      const g = allGames.find(x => x.id === gameId);
      if (g && data.game) { Object.assign(g, data.game); renderGames(); }
      if (btn) btn.textContent = "✅ " + msgs.join(", ");
    }
  } catch(e) {
    if (btn) btn.textContent = `❌ ${t("error","Eroare")}`;
  }
  setTimeout(() => { if (btn) { btn.textContent = `⬇️ ${t("save_images_local","Save images locally")}`; btn.disabled = false; }}, 3000);
}

// ─── Filter events ────────────────────────────────────────────────────────────
document.querySelectorAll(".pill").forEach(p => p.addEventListener("click", () => {
  document.querySelectorAll(".pill").forEach(x => x.classList.remove("active"));
  p.classList.add("active");
  currentStatus = p.dataset.status || "";
  currentMedia = p.dataset.media || "";
  loadGames();
}));

document.getElementById("search").addEventListener("input", debounce(loadGames, 300));
document.getElementById("filter-genre").addEventListener("change", loadGames);

document.querySelectorAll(".modal-overlay").forEach(m => m.addEventListener("click", e => {
  if (e.target !== m) return;
  if (m.id === "modal-add") return;
  m.classList.remove("show");
}));

document.getElementById("modal-browse-img").addEventListener("click", e => {
  if (e.target === document.getElementById("modal-browse-img")) closeBrowseModal();
});

document.querySelectorAll(".star-input").forEach(s => s.addEventListener("click", () => setRating(parseInt(s.dataset.val))));
document.querySelectorAll(".media-btn").forEach(b => b.addEventListener("click", () => setMediaType(b.dataset.val)));

// ─── Multi-image upload (screenshots/other) ─────────────────────────────────
function setupMultiImgUpload(inputId, containerId, imgType) {
  const inp = document.getElementById(inputId);
  if (!inp) return;
  inp.addEventListener("change", async () => {
    const files = Array.from(inp.files);
    if (!files.length) return;
    const gameId = document.getElementById("edit-id").value || null;
    const progId = imgType === "screenshot" ? "screenshot-upload-progress" : "other-upload-progress";
    const prog = document.getElementById(progId);
    if (prog) { prog.textContent = `⏳ ${t("uploading","Uploadez")} ${files.length} imagini...`; prog.classList.add("show"); }
    for (const file of files) {
      try {
        const result = await uploadImageFile(file, imgType, gameId);
        addScreenshotThumb(containerId, result.url);
      } catch(e) {
        if (prog) prog.textContent = "❌ " + e.message;
      }
    }
    if (prog) { prog.textContent = `✅ ${files.length} imagini uploadate`; setTimeout(() => prog.classList.remove("show"), 2500); }
    inp.value = "";
  });
}

function addScreenshotThumb(containerId, url) {
  const c = document.getElementById(containerId);
  if (!c) return;
  const wrap = document.createElement("span");
  wrap.className = "screenshot-thumb-wrap";
  wrap.innerHTML = `<img src="${url}" class="screenshot-thumb" title="${url}">
    <button class="ss-remove" onclick="this.parentElement.remove()" title="Remove">×</button>`;
  c.appendChild(wrap);
}

async function loadGameScreenshots(gameId, containerId, imgType) {
  const c = document.getElementById(containerId);
  if (!c) return;
  c.innerHTML = "";
  try {
    const imgs = await fetch(`/api/images?game_id=${gameId}&type=${imgType}`).then(r => r.json());
    imgs.forEach(img => addScreenshotThumb(containerId, img.url));
  } catch {}
}

// ─── Video Links ─────────────────────────────────────────────────────────────
function addVideoLinkRow(url, title) {
  const list = document.getElementById("video-links-list");
  if (!list) return;
  const row = document.createElement("div");
  row.className = "video-link-row";
  row.innerHTML = `<input type="text" class="vlr-url" placeholder="https://youtube.com/watch?v=..." value="${url||''}">
    <input type="text" class="vlr-title" placeholder="Title (optional)" value="${title||''}">
    <button class="vlr-remove" onclick="this.parentElement.remove()" title="Remove">×</button>`;
  list.appendChild(row);
}

function getVideoLinks() {
  const rows = document.querySelectorAll("#video-links-list .video-link-row");
  const links = [];
  rows.forEach(row => {
    const url = row.querySelector(".vlr-url").value.trim();
    const title = row.querySelector(".vlr-title").value.trim();
    if (url) links.push({url, title});
  });
  return links;
}

function populateVideoLinks(videoLinks) {
  const list = document.getElementById("video-links-list");
  if (!list) return;
  list.innerHTML = "";
  if (!videoLinks || !videoLinks.length) return;
  let links = videoLinks;
  if (typeof links === "string") {
    try { links = JSON.parse(links); } catch { return; }
  }
  links.forEach(v => addVideoLinkRow(v.url, v.title));
}

// ─── Download integration ────────────────────────────────────────────────────
function openGameDownload(gameId, title, platform) {
  window.location.href = `/descarcari?game_id=${gameId}&search=${encodeURIComponent(title)}`;
}

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  const cfg = await fetch("/api/config").then(r => r.json());
  hasRawg = cfg.has_rawg_key;
  hasAnyApi = cfg.has_rawg_key || cfg.has_igdb_key || cfg.has_moby_key;
  await loadLanguages();
  await Promise.all([loadGames(), loadFiles_quiet(), loadLicenses_quiet()]);
  updateStats();
  loadGenres();
  setupImgInput("cover-file-input", "f-cover", "cover-preview", "cover-upload-progress", "cover");
  setupImgInput("banner-file-input", "f-banner", "banner-preview", "banner-upload-progress", "banner");
  setupMultiImgUpload("screenshot-file-input", "screenshot-thumbs", "screenshot");
  setupMultiImgUpload("other-file-input", "other-thumbs", "other");
  checkAutoAddFromFile();
}

// ─── Add Game from File Manager ───────────────────────────────────────────────
function checkAutoAddFromFile() {
  const params = new URLSearchParams(window.location.search);

  // ─── edit_game: deschide editarea unui joc existent ───────────────────────
  const editGameId = params.get("edit_game");
  if (editGameId) {
    window.history.replaceState({}, document.title, "/");
    // Retry până când jocurile sunt încărcate
    const tryOpen = () => {
      const game = allGames.find(g => g.id == editGameId);
      if (game) { editGame(game.id); }
      else { setTimeout(tryOpen, 150); }
    };
    setTimeout(tryOpen, 150);
    return;
  }

  // ─── add_for_file: adaugă joc nou și asociază fișierul ────────────────────
  const fileId = params.get("add_for_file");
  if (!fileId) return;
  window._pendingFileId = parseInt(fileId);
  const ftitle   = decodeURIComponent(params.get("ftitle") || "");
  const fplatform = params.get("platform") || "PS5";
  // Șterge parametrii din URL fără reload
  window.history.replaceState({}, document.title, "/");
  // Deschide modalul de adăugare
  openAddModal(null);
  if (ftitle) {
    document.getElementById("f-title").value = ftitle;
    document.getElementById("f-platform").value = fplatform;
    document.getElementById("ps-search-input").value = ftitle;
    // Banner informativ
    const note = document.getElementById("modal-add-note");
    if (note) {
      note.style.display = "block";
      note.textContent = `📎 ${t("file_pending_assoc","File will be auto-linked after saving")}`;
    }
    // Auto-search dacă avem API keys
    if (hasAnyApi && ftitle.length >= 2) {
      setTimeout(() => doSearch(ftitle), 300);
    }
  }
}

// Load files/licenses without rendering (for dots on cards)
async function loadFiles_quiet() {
  allFiles = await fetch("/api/files").then(r => r.json());
}
async function loadLicenses_quiet() {
  allLicenses = await fetch("/api/licenses").then(r => r.json());
}

// ─── Modal Saves & DLC (secțiune din Add/Edit Game modal) ─────────────────────
function switchModalMediaTab(el, tabId) {
  document.querySelectorAll(".modal-media-tab").forEach(btn => {
    btn.classList.remove("active");
    btn.style.color = "var(--textd)";
    btn.style.borderBottom = "none";
  });
  el.classList.add("active");
  el.style.color = "var(--text)";
  el.style.borderBottom = "2px solid var(--cyan)";
  ["modal-files-panel", "modal-saves-panel", "modal-dlc-panel"].forEach(id => {
    const p = document.getElementById(id);
    if (p) p.style.display = id === tabId ? "block" : "none";
  });
}

async function loadModalFiles(gameId) {
  const el = document.getElementById("modal-files-list");
  if (!el) return;
  el.innerHTML = '<span class="spinner" style="width:12px;height:12px;border-width:2px;vertical-align:middle"></span>';
  try {
    const files = await fetch(`/api/files?game_id=${gameId}`).then(r => r.json());
    const lics  = await fetch(`/api/licenses?game_id=${gameId}`).then(r => r.json());
    const all = [...files, ...lics];
    if (!all.length) {
      el.innerHTML = `<span style="color:var(--textd);font-size:.78rem">${t("no_associated_files","No associated files")}</span>`;
    } else {
      el.innerHTML = all.map(f => {
        const isLic = !!f.license_type;
        const ftype = f.file_type || f.license_type || '?';
        const icon = isLic ? '🔑' : '💿';
        return `
        <div style="display:flex;align-items:center;gap:.5rem;padding:.3rem 0;border-bottom:1px solid var(--border)44">
          <span class="type-badge type-${ftype}" style="font-size:.62rem;padding:1px 5px">${ftype}</span>
          <span style="flex:1;font-size:.78rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${f.filepath||''}">${icon} ${f.filename}</span>
          ${f.content_id ? `<span style="font-size:.68rem;color:var(--cyan);white-space:nowrap;font-family:monospace">${f.content_id}</span>` : ''}
          <span style="font-size:.7rem;color:var(--textd);white-space:nowrap">${f.file_size_str||''}</span>
          <a class="btn btn-outline btn-sm" href="/api/${isLic?'licenses':'files'}/${f.id}/download" style="font-size:.7rem;padding:2px 6px;flex-shrink:0">⬇️</a>
          <button class="btn btn-danger btn-sm" onclick="deleteModalFile(${f.id},${isLic})" style="font-size:.7rem;padding:2px 6px;flex-shrink:0">🗑️</button>
        </div>`;
      }).join('');
    }
  } catch {
    el.innerHTML = `<span style="color:var(--danger);font-size:.78rem">${t("error","Load error")}</span>`;
  }
}

async function uploadModalFile() {
  const gameId = document.getElementById("edit-id").value;
  if (!gameId) return;
  const inp = document.getElementById("modal-file-upload-input");
  if (!inp || !inp.files.length) return;
  const st = document.getElementById("modal-file-upload-status");
  if (st) st.innerHTML = `<span class="spinner" style="width:10px;height:10px;border-width:2px;vertical-align:middle"></span> ${t("uploading","Uploadez")}...`;
  for (const file of inp.files) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("game_id", gameId);
    fd.append("auto_organize", "0");
    try {
      const res = await fetch("/api/files/upload", {method: "POST", body: fd});
      if (res.ok) {
        if (st) st.textContent = `✅ ${file.name}`;
      } else {
        const d = await res.json();
        if (st) st.textContent = `❌ ${d.error||t("error","Eroare")}`;
      }
    } catch {
      if (st) st.textContent = `❌ ${t("network_error","Network error")}`;
    }
  }
  inp.value = "";
  setTimeout(() => { if (st) st.textContent = ""; }, 3000);
  await loadModalFiles(gameId);
}

async function deleteModalFile(id, isLicense) {
  if (!confirm(t("delete_confirm","Delete?"))) return;
  const endpoint = isLicense ? 'licenses' : 'files';
  await fetch(`/api/${endpoint}/${id}`, {method: "DELETE"});
  const gameId = document.getElementById("edit-id").value;
  if (gameId) await loadModalFiles(gameId);
}

async function loadModalSaves(gameId) {
  const el = document.getElementById("modal-saves-list");
  if (!el) return;
  el.innerHTML = '<span class="spinner" style="width:12px;height:12px;border-width:2px;vertical-align:middle"></span>';
  try {
    const saves = await fetch(`/api/saves?game_id=${gameId}`).then(r => r.json());
    if (!saves.length) {
      el.innerHTML = `<span style="color:var(--textd);font-size:.78rem">${t("no_saves","Niciun save uploadat")}</span>`;
    } else {
      el.innerHTML = saves.map(s => `
        <div style="display:flex;align-items:center;gap:.5rem;padding:.3rem 0;border-bottom:1px solid var(--border)44">
          <span style="flex:1;font-size:.78rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${s.filepath||''}">💾 ${s.filename}</span>
          <span style="font-size:.7rem;color:var(--textd);white-space:nowrap">${s.file_size_str||''}</span>
          <a class="btn btn-outline btn-sm" href="/api/saves/${s.id}/download" style="font-size:.7rem;padding:2px 6px;flex-shrink:0">⬇️</a>
          <button class="btn btn-danger btn-sm" onclick="deleteModalSave(${s.id})" style="font-size:.7rem;padding:2px 6px;flex-shrink:0">🗑️</button>
        </div>`).join('');
    }
  } catch {
    el.innerHTML = `<span style="color:var(--danger);font-size:.78rem">${t("error","Load error")}</span>`;
  }
}

async function loadModalDlc(gameId) {
  const el = document.getElementById("modal-dlc-list");
  if (!el) return;
  el.innerHTML = '<span class="spinner" style="width:12px;height:12px;border-width:2px;vertical-align:middle"></span>';
  try {
    const dlcs = await fetch(`/api/dlc?game_id=${gameId}`).then(r => r.json());
    if (!dlcs.length) {
      el.innerHTML = `<span style="color:var(--textd);font-size:.78rem">${t("no_dlc","Niciun DLC uploadat")}</span>`;
    } else {
      el.innerHTML = dlcs.map(d => `
        <div style="display:flex;align-items:center;gap:.5rem;padding:.3rem 0;border-bottom:1px solid var(--border)44">
          <span style="flex:1;font-size:.78rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${d.filepath||''}">📦 ${d.filename}</span>
          ${d.content_id ? `<span style="font-size:.68rem;color:var(--cyan);white-space:nowrap;font-family:monospace">${d.content_id}</span>` : ''}
          <span style="font-size:.7rem;color:var(--textd);white-space:nowrap">${d.file_size_str||''}</span>
          <a class="btn btn-outline btn-sm" href="/api/dlc/${d.id}/download" style="font-size:.7rem;padding:2px 6px;flex-shrink:0">⬇️</a>
          <button class="btn btn-danger btn-sm" onclick="deleteModalDlc(${d.id})" style="font-size:.7rem;padding:2px 6px;flex-shrink:0">🗑️</button>
        </div>`).join('');
    }
  } catch {
    el.innerHTML = `<span style="color:var(--danger);font-size:.78rem">${t("error","Load error")}</span>`;
  }
}

async function uploadModalSave() {
  const gameId = document.getElementById("edit-id").value;
  if (!gameId) return;
  const inp = document.getElementById("modal-save-upload-input");
  if (!inp || !inp.files.length) return;
  const st = document.getElementById("modal-save-upload-status");
  if (st) st.innerHTML = `<span class="spinner" style="width:10px;height:10px;border-width:2px;vertical-align:middle"></span> ${t("uploading","Uploadez")}...`;
  for (const file of inp.files) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("game_id", gameId);
    try {
      const res = await fetch("/api/saves/upload", {method: "POST", body: fd});
      if (res.ok) {
        if (st) st.textContent = `✅ ${file.name}`;
      } else {
        const d = await res.json();
        if (st) st.textContent = `❌ ${d.error||t("error","Eroare")}`;
      }
    } catch {
      if (st) st.textContent = `❌ ${t("network_error","Network error")}`;
    }
  }
  inp.value = "";
  setTimeout(() => { if (st) st.textContent = ""; }, 3000);
  await loadModalSaves(gameId);
}

async function uploadModalDlc() {
  const gameId = document.getElementById("edit-id").value;
  if (!gameId) return;
  const inp = document.getElementById("modal-dlc-upload-input");
  if (!inp || !inp.files.length) return;
  const st = document.getElementById("modal-dlc-upload-status");
  if (st) st.innerHTML = `<span class="spinner" style="width:10px;height:10px;border-width:2px;vertical-align:middle"></span> ${t("uploading","Uploadez")}...`;
  for (const file of inp.files) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("game_id", gameId);
    try {
      const res = await fetch("/api/dlc/upload", {method: "POST", body: fd});
      if (res.ok) {
        if (st) st.textContent = `✅ ${file.name}`;
      } else {
        const d = await res.json();
        if (st) st.textContent = `❌ ${d.error||t("error","Eroare")}`;
      }
    } catch {
      if (st) st.textContent = `❌ ${t("network_error","Network error")}`;
    }
  }
  inp.value = "";
  setTimeout(() => { if (st) st.textContent = ""; }, 3000);
  await loadModalDlc(gameId);
}

async function deleteModalSave(id) {
  if (!confirm(t("delete_confirm","Delete?"))) return;
  await fetch(`/api/saves/${id}`, {method: "DELETE"});
  const gameId = document.getElementById("edit-id").value;
  if (gameId) await loadModalSaves(gameId);
}

async function deleteModalDlc(id) {
  if (!confirm(t("delete_confirm","Delete?"))) return;
  await fetch(`/api/dlc/${id}`, {method: "DELETE"});
  const gameId = document.getElementById("edit-id").value;
  if (gameId) await loadModalDlc(gameId);
}

init();
