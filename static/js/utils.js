// ─── Global shared state ──────────────────────────────────────────────────────
let allGames = [], allFiles = [], allLicenses = [];
let currentStatus = "", currentRating = 0;
let currentPlatform = "", currentFileType = "", currentDetailId = null;
let hasRawg = false, hasAnyApi = false, searchTimer = null;

// ─── i18n System ─────────────────────────────────────────────────────────────
let currentLang = {};
let langCode = "en";

function t(key, fallback) {
  return currentLang[key] || fallback || key;
}

async function loadLanguages() {
  const sel = document.getElementById("lang-select");
  if (!sel) return;
  let langList = [];
  try {
    const apiLangs = await fetch("/api/lang").then(r => r.json());
    if (Array.isArray(apiLangs)) langList = apiLangs;
  } catch(e) {}
  if (!langList.length) langList = [{code:"en", name:"English"}];
  const flags = {ro:"\u{1F1F7}\u{1F1F4}", en:"\u{1F1EC}\u{1F1E7}"};
  sel.innerHTML = langList.map(l =>
    `<option value="${l.code}">${flags[l.code]||"\u{1F310}"} ${l.name}</option>`
  ).join('');
  const saved = localStorage.getItem("ps-library-lang");
  if (saved && langList.find(l => l.code === saved)) {
    langCode = saved;
    sel.value = saved;
  }
  await applyLanguage(langCode);
  sel.addEventListener("change", function() {
    langCode = this.value;
    localStorage.setItem("ps-library-lang", langCode);
    applyLanguage(langCode);
  });
}

async function applyLanguage(code) {
  try {
    const resp = await fetch("/api/lang/" + code);
    if (resp.ok) {
      currentLang = await resp.json();
    } else {
      const fallback = await fetch("/api/lang/en");
      currentLang = fallback.ok ? await fallback.json() : {};
    }
  } catch(e) {
    currentLang = {};
  }
  _updateDomLanguage();
}

function _updateDomLanguage() {
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    if (currentLang[key]) el.textContent = currentLang[key];
  });
  document.querySelectorAll("[data-i18n-html]").forEach(el => {
    const key = el.getAttribute("data-i18n-html");
    if (currentLang[key]) el.innerHTML = currentLang[key];
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (currentLang[key]) el.placeholder = currentLang[key];
  });
  const genSel = document.getElementById("filter-genre");
  if (genSel) {
    const curVal = genSel.value;
    genSel.querySelector("option:first-child").textContent = t("all_genres", "All genres");
    genSel.value = curVal;
  }
  // Re-render dynamic content if loaded
  if (typeof renderGames === 'function' && allGames.length) renderGames();
  if (typeof renderFiles === 'function' && allFiles.length) renderFiles();
  if (typeof renderLicenses === 'function' && allLicenses.length) renderLicenses();
}

// ─── Shared helpers ───────────────────────────────────────────────────────────
function formatSize(b) {
  if (!b) return "0 B";
  const u = ["B","KB","MB","GB","TB"];
  let i = 0, n = b;
  while (n >= 1024 && i < 4) { n /= 1024; i++; }
  return n.toFixed(1) + " " + u[i];
}

function mediaLabel(type) {
  const icons = {"BD":"📀","DVD":"💿","CD":"💿","Cartridge":"🎴","UMD":"🔘","GD-ROM":"🔵","Digital":"💾","Images":"🖼️","Arhiva":"📦","Folder":"📁"};
  const keys = {"BD":"blu_ray","DVD":"dvd","CD":"cd","Cartridge":"cartridge","UMD":"umd","Digital":"digital","Images":"media_images","Arhiva":"media_archive","Folder":"media_folder"};
  const icon = icons[type] || "";
  const label = keys[type] ? t(keys[type], type) : type;
  return icon ? icon + " " + label : label;
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || "";
  return d.innerHTML.replace(/'/g, "&#39;").replace(/"/g, "&quot;");
}

function debounce(fn, delay = 300) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
}

function showToast(message, duration = 3000) {
  const toast = document.createElement("div");
  toast.style.cssText = "position:fixed;bottom:1.5rem;right:1.5rem;background:var(--bg2);border:1px solid var(--cyan);color:var(--cyan);padding:.7rem 1.3rem;border-radius:8px;font-size:.84rem;z-index:9999;animation:modalIn .2s ease";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), duration);
}

// ─── Stats (header) ───────────────────────────────────────────────────────────
async function updateStats() {
  const s = await fetch("/api/stats").then(r => r.json());
  document.getElementById("st-total").textContent = s.total_games;
  document.getElementById("st-played").textContent = s.played;
  document.getElementById("st-unfin").textContent = s.unfinished;
  document.getElementById("st-wish").textContent = s.wishlist;
  const filesEl = document.getElementById("st-files");
  if (filesEl) filesEl.textContent = s.total_files || allFiles.length;
  document.getElementById("st-lic").textContent = s.total_licenses;
  const ub = document.getElementById("unassigned-badge");
  if (ub) {
    if (s.unassigned_files > 0) { ub.style.display = "inline"; ub.textContent = s.unassigned_files + " " + t("unassigned_count","unassigned"); }
    else ub.style.display = "none";
  }
  return s;
}
