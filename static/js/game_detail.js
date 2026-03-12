// ─── Game Detail Page JS ──────────────────────────────────────────────────────

// Switch Files / Saves / DLC tabs
function switchGdpTab(el, tabId) {
  document.querySelectorAll(".gdp-tab-btn").forEach(btn => btn.classList.remove("active"));
  el.classList.add("active");
  ["gdp-files-panel", "gdp-saves-panel", "gdp-dlc-panel"].forEach(id => {
    const p = document.getElementById(id);
    if (p) p.style.display = id === tabId ? "block" : "none";
  });
}

// Delete game → navigate back to library
async function gdpDeleteGame() {
  if (!confirm(t("delete_game_confirm", "Delete game? This action is irreversible."))) return;
  try {
    const res = await fetch(`/api/games/${GAME_ID}`, { method: "DELETE" });
    if (res.ok) {
      window.location.href = "/";
    } else {
      alert(t("error", "Delete error"));
    }
  } catch {
    alert(t("network_error", "Network error"));
  }
}

// Fetch & save images locally, then reload page
async function gdpFetchImages() {
  const btn = document.getElementById("gdp-btn-fetch");
  if (btn) { btn.innerHTML = `⏳ <span>${t("downloading","Downloading...")}</span>`; btn.disabled = true; }
  try {
    const res = await fetch(`/api/games/${GAME_ID}/fetch-images`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      const r = data.results || {};
      const msgs = [];
      if (r.cover === "already_local")          msgs.push(t("cover_already_local","cover: already local"));
      else if (r.cover && r.cover.startsWith("/")) msgs.push("✅ " + t("cover_saved","cover saved"));
      else                                         msgs.push("❌ " + t("cover_error","cover: error"));
      if (r.banner === "already_local")            msgs.push(t("banner_already_local","banner: already local"));
      else if (r.banner && r.banner.startsWith("/")) msgs.push("✅ " + t("banner_saved","banner saved"));
      else                                          msgs.push("❌ " + t("banner_error","banner: error"));
      if (btn) btn.innerHTML = "✅ " + msgs.join(", ");
      setTimeout(() => location.reload(), 1800);
    } else {
      if (btn) { btn.innerHTML = `❌ ${t("error","Error")}`; btn.disabled = false; }
    }
  } catch {
    if (btn) { btn.innerHTML = `❌ ${t("network_error","Network error")}`; btn.disabled = false; }
  }
}

// ─── YouTube helpers ──────────────────────────────────────────────────────────

function parseYoutubeId(url) {
  if (!url) return null;
  // youtube.com/watch?v=ID  |  youtu.be/ID  |  youtube.com/embed/ID  |  shorts/ID
  const patterns = [
    /(?:youtube\.com\/watch\?.*v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})/,
  ];
  for (const p of patterns) {
    const m = url.match(p);
    if (m) return m[1];
  }
  return null;
}

function renderVideos() {
  const grid = document.getElementById("gdp-video-grid");
  if (!grid || typeof VIDEO_LINKS === "undefined" || !VIDEO_LINKS.length) return;

  grid.innerHTML = "";
  for (const v of VIDEO_LINKS) {
    const url = typeof v === "string" ? v : v.url;
    const title = (typeof v === "object" && v.title) ? v.title : "";
    const ytId = parseYoutubeId(url);

    const item = document.createElement("div");
    item.className = "gdp-video-item";

    if (ytId) {
      // YouTube embed
      item.innerHTML = `
        <div class="gdp-video-embed">
          <iframe src="https://www.youtube.com/embed/${ytId}" frameborder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowfullscreen loading="lazy"></iframe>
        </div>
        ${title ? `<div class="gdp-video-title">${esc(title)}</div>` : ""}`;
    } else {
      // External link
      item.innerHTML = `
        <a class="gdp-video-link-ext" href="${esc(url)}" target="_blank" rel="noopener">
          <span class="gdp-vle-icon">🔗</span>
          <span class="gdp-vle-text">${esc(title || url)}</span>
        </a>`;
    }
    grid.appendChild(item);
  }
}


// ─── Gallery Lightbox ─────────────────────────────────────────────────────────

let lbIndex = 0;

function openLightbox(url) {
  const lb = document.getElementById("gdp-lightbox");
  const img = document.getElementById("gdp-lb-img");
  if (!lb || !img) return;
  // Find index in GALLERY
  if (typeof GALLERY !== "undefined" && GALLERY.length) {
    const idx = GALLERY.findIndex(g => g.url === url);
    if (idx >= 0) lbIndex = idx;
  }
  img.src = url;
  lb.classList.add("active");
  document.body.style.overflow = "hidden";
}

function closeLightbox(e) {
  if (e && e.target !== document.getElementById("gdp-lightbox") &&
      e.target !== document.querySelector(".gdp-lb-close")) return;
  const lb = document.getElementById("gdp-lightbox");
  if (lb) lb.classList.remove("active");
  document.body.style.overflow = "";
}

function lbNav(dir, e) {
  if (e) { e.stopPropagation(); e.preventDefault(); }
  if (typeof GALLERY === "undefined" || !GALLERY.length) return;
  lbIndex = (lbIndex + dir + GALLERY.length) % GALLERY.length;
  const img = document.getElementById("gdp-lb-img");
  if (img) img.src = GALLERY[lbIndex].url;
}

// Keyboard navigation for lightbox
document.addEventListener("keydown", e => {
  const lb = document.getElementById("gdp-lightbox");
  if (!lb || !lb.classList.contains("active")) return;
  if (e.key === "Escape") closeLightbox();
  if (e.key === "ArrowLeft") lbNav(-1);
  if (e.key === "ArrowRight") lbNav(1);
});


// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  await loadLanguages();
  updateStats();
  renderVideos();
}

init();
