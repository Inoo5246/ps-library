"""Scanner service: file scanning + auto-scan scheduler."""
import os, time, threading
from pathlib import Path

from config import GAMES_DIR, LICENSES_DIR, ALLOWED_GAME_EXTS, ALLOWED_LICENSE_EXTS
from db import get_db, load_settings, save_settings
from services.pkg_parser import (parse_pkg, parse_disc_image, parse_license,
                                  get_file_size_str, get_folder_size,
                                  is_ps3_game_root, is_ps4_game_root, is_ps5_game_root,
                                  parse_ps3_folder, parse_ps4_folder, parse_ps5_folder,
                                  _title_from_path, _detect_platform_from_path,
                                  _auto_link_game)
from services.metadata import search_metadata

# ─── Scheduler ────────────────────────────────────────────────────────────────
_stop_event = threading.Event()


def start_scheduler():
    """Start background auto-scan thread (daemon, checks every 5 min)."""
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="auto-scan")
    t.start()
    print("Auto-scan scheduler started.")


def _scheduler_loop():
    while not _stop_event.wait(300):   # check every 5 minutes
        try:
            settings = load_settings()
            interval_h = settings.get("auto_scan_interval_hours", 0)
            if not interval_h:
                continue
            last = settings.get("last_auto_scan", 0)
            if time.time() - last >= interval_h * 3600:
                print(f"[auto-scan] Starting scheduled scan (interval={interval_h}h)...")
                result = scan_files()
                print(f"[auto-scan] Done: {result}")
                settings = load_settings()
                settings["last_auto_scan"] = time.time()
                save_settings(settings)
        except Exception as e:
            print(f"[auto-scan] Error: {e}")


# ─── Core scan logic ──────────────────────────────────────────────────────────

# Foldere interne ignorate la scanare
_SKIP_DIRNAMES = {"licenses", "images", "screenshots", "_uploading", "_licenses",
                  "ps3_game", "sce_sys", "usrdir", "ps3_update"}


def scan_files():
    """Scan /games and custom folders, add new files to DB. Returns stats dict."""
    conn = get_db()
    found_files = found_licenses = 0

    # 1) Scan /games
    found_files += _scan_dir(conn, GAMES_DIR)

    # 2) Scan custom folders from settings
    settings = load_settings()
    for cf in settings.get("custom_folders", []):
        cf_path     = cf.get("path", "")
        cf_platform = cf.get("platform", "") or None
        cf_types    = set(t.lower().lstrip('.') for t in cf.get("file_types", []))
        if not cf_path or not os.path.isdir(cf_path):
            continue
        # If the custom folder itself is a PS3/PS5 game root
        if is_ps3_game_root(cf_path):
            if not conn.execute("SELECT id FROM game_files WHERE filepath=?",
                                (cf_path,)).fetchone():
                found_files += _insert_folder_game(conn, cf_path, "PS3", cf_platform)
        elif is_ps5_game_root(cf_path):
            if not conn.execute("SELECT id FROM game_files WHERE filepath=?",
                                (cf_path,)).fetchone():
                found_files += _insert_folder_game(conn, cf_path, "PS5", cf_platform)
        elif is_ps4_game_root(cf_path):
            if not conn.execute("SELECT id FROM game_files WHERE filepath=?",
                                (cf_path,)).fetchone():
                found_files += _insert_folder_game(conn, cf_path, "PS4", cf_platform)
        else:
            found_files += _scan_dir(conn, cf_path,
                                     cf_types=cf_types if cf_types else None,
                                     forced_platform=cf_platform)

    # 3) Scan license directories
    scan_lic_dirs = [LICENSES_DIR]
    for root, dirs, files in os.walk(GAMES_DIR):
        for d in dirs:
            if d.lower() == "licenses":
                scan_lic_dirs.append(os.path.join(root, d))
    for lic_dir in scan_lic_dirs:
        if not os.path.isdir(lic_dir):
            continue
        for fname in sorted(os.listdir(lic_dir)):
            ext = Path(fname).suffix.lower()
            if ext not in ALLOWED_LICENSE_EXTS:
                continue
            fpath = os.path.join(lic_dir, fname)
            if conn.execute("SELECT id FROM licenses WHERE filepath=?",
                            (fpath,)).fetchone():
                continue
            fsize = os.path.getsize(fpath)
            lic_info = parse_license(fpath)
            game_id = _auto_link_game(conn, lic_info.get("content_id"), fpath)
            conn.execute("""INSERT INTO licenses
                (game_id,filename,filepath,license_type,content_id,file_size,is_uploaded)
                VALUES (?,?,?,?,?,?,0)""",
                (game_id, fname, fpath, ext.lstrip('.').upper(),
                 lic_info.get("content_id"), fsize))
            found_licenses += 1

    conn.commit()
    conn.close()
    return {"scanned_files": found_files, "scanned_licenses": found_licenses}


def _scan_dir(conn, dirpath, cf_types=None, forced_platform=None):
    """Intelligent recursive scan:
    - Detects PS3 game roots (contain PS3_GAME/) and PS5 (contain sce_sys/param.json)
    - Registers the game folder and does NOT recurse inside
    - Individual files (.pkg, .iso, .bin PS1, .cue, .rar etc.) are processed normally
    """
    found = 0
    try:
        entries = list(os.scandir(dirpath))
    except (PermissionError, OSError) as e:
        print(f"[scan] Cannot access {dirpath}: {e}")
        return 0

    subdirs = sorted([e for e in entries if e.is_dir(follow_symlinks=False)],
                     key=lambda x: x.name.lower())
    files   = sorted([e for e in entries if e.is_file(follow_symlinks=False)],
                     key=lambda x: x.name.lower())

    skip_dirs = set()

    # — Detect game roots in subdirectories —
    for sd in subdirs:
        name_l = sd.name.lower()
        if name_l in _SKIP_DIRNAMES:
            skip_dirs.add(sd.name)
            continue
        if is_ps3_game_root(sd.path):
            found += _insert_folder_game(conn, sd.path, "PS3", forced_platform)
            skip_dirs.add(sd.name)
        elif is_ps5_game_root(sd.path):
            # PS5 before PS4 — some PS5 games may also have param.sfo
            found += _insert_folder_game(conn, sd.path, "PS5", forced_platform)
            skip_dirs.add(sd.name)
        elif is_ps4_game_root(sd.path):
            found += _insert_folder_game(conn, sd.path, "PS4", forced_platform)
            skip_dirs.add(sd.name)

    # — Individual files in the current directory —
    for fe in files:
        ext = Path(fe.name).suffix.lower()
        if ext not in ALLOWED_GAME_EXTS:
            continue
        if cf_types and ext.lstrip('.') not in cf_types:
            continue
        fpath = fe.path
        if conn.execute("SELECT id FROM game_files WHERE filepath=?",
                        (fpath,)).fetchone():
            continue
        found += _insert_game_file(conn, fpath, fe.name, ext,
                                   forced_platform=forced_platform)

    # — Recurse into remaining subdirectories —
    for sd in subdirs:
        if sd.name in skip_dirs or sd.name.lower() in _SKIP_DIRNAMES:
            continue
        found += _scan_dir(conn, sd.path, cf_types=cf_types,
                           forced_platform=forced_platform)
    return found


def _insert_folder_game(conn, folderpath, ps_platform, forced_platform=None):
    """Register a folder-type game (PS3/PS5) in game_files."""
    if conn.execute("SELECT id FROM game_files WHERE filepath=?",
                    (folderpath,)).fetchone():
        return 0  # already exists

    platform = forced_platform or ps_platform
    content_id = detected_title = None
    fsize = 0
    try:
        fsize = get_folder_size(folderpath)
    except Exception:
        pass

    if ps_platform == "PS3":
        info = parse_ps3_folder(folderpath)
        content_id    = info.get("content_id")
        detected_title = info.get("title")
    elif ps_platform == "PS4":
        info = parse_ps4_folder(folderpath)
        content_id    = info.get("content_id")
        detected_title = info.get("title")
    elif ps_platform == "PS5":
        info = parse_ps5_folder(folderpath)
        content_id    = info.get("content_id")
        detected_title = info.get("title")

    if not detected_title:
        detected_title = Path(folderpath).name
    if not platform:
        platform = _detect_platform_from_path(folderpath)

    ftype   = f"{ps_platform}_FOLDER"
    game_id = _auto_link_game(conn, content_id, folderpath)

    conn.execute("""INSERT INTO game_files
        (game_id,filename,filepath,file_type,platform,content_id,
         file_size,file_size_str,pkg_type,is_uploaded,detected_title)
        VALUES (?,?,?,?,?,?,?,?,?,0,?)""",
        (game_id, Path(folderpath).name, folderpath,
         ftype, platform, content_id,
         fsize, get_file_size_str(fsize), None, detected_title))
    return 1


def _insert_game_file(conn, fpath, fname, ext, forced_platform=None):
    fsize = os.path.getsize(fpath)
    ftype = ext.lstrip('.').upper()
    content_id = None
    platform = forced_platform
    pkg_type = None
    detected_title = None

    if ext == '.pkg':
        pkg_info = parse_pkg(fpath)
        content_id = pkg_info.get("content_id")
        if not platform: platform = pkg_info.get("platform")
        pkg_type = pkg_info.get("pkg_type")
    elif ext in ('.iso', '.bin', '.img', '.pbp'):
        disc_info = parse_disc_image(fpath)
        content_id = disc_info.get("content_id")
        if not platform: platform = disc_info.get("platform")
        detected_title = disc_info.get("detected_title")
    elif ext in ('.rar', '.zip'):
        # PS5 backup archive (cannot be parsed without extraction)
        # Platform from path structure; fallback PS5
        if not platform: platform = _detect_platform_from_path(fpath) or "PS5"

    if not detected_title:
        detected_title = _title_from_path(fpath)
    if not platform:
        platform = _detect_platform_from_path(fpath)

    game_id = _auto_link_game(conn, content_id, fpath)
    conn.execute("""INSERT INTO game_files
        (game_id,filename,filepath,file_type,platform,content_id,
         file_size,file_size_str,pkg_type,is_uploaded,detected_title)
        VALUES (?,?,?,?,?,?,?,?,?,0,?)""",
        (game_id, fname, fpath, ftype, platform,
         content_id, fsize, get_file_size_str(fsize), pkg_type, detected_title))
    return 1


def rescan_metadata():
    """Re-parse disc images and PKG files for Content ID."""
    conn = get_db()
    updated = 0
    rows = conn.execute(
        "SELECT id, filepath, file_type FROM game_files "
        "WHERE file_type IN ('ISO','BIN','IMG','PBP')").fetchall()
    for row in rows:
        fpath = row["filepath"]
        if not os.path.exists(fpath): continue
        disc_info = parse_disc_image(fpath)
        cid = disc_info.get("content_id")
        plat = disc_info.get("platform")
        dtitle = disc_info.get("detected_title") or _title_from_path(fpath)
        if cid or dtitle:
            sets, params = [], []
            if cid: sets.append("content_id=?"); params.append(cid)
            if plat: sets.append("platform=?"); params.append(plat)
            if dtitle: sets.append("detected_title=?"); params.append(dtitle)
            if sets:
                params.append(row["id"])
                conn.execute(f"UPDATE game_files SET {','.join(sets)} WHERE id=?", params)
                if cid and not conn.execute(
                        "SELECT game_id FROM game_files WHERE id=? AND game_id IS NOT NULL",
                        (row["id"],)).fetchone():
                    gid = _auto_link_game(conn, cid, fpath)
                    if gid:
                        conn.execute("UPDATE game_files SET game_id=? WHERE id=?", (gid, row["id"]))
                updated += 1

    pkg_rows = conn.execute(
        "SELECT id, filepath FROM game_files "
        "WHERE file_type='PKG' AND (content_id IS NULL OR content_id='')").fetchall()
    for row in pkg_rows:
        if not os.path.exists(row["filepath"]): continue
        pkg_info = parse_pkg(row["filepath"])
        if pkg_info.get("content_id"):
            conn.execute(
                "UPDATE game_files SET content_id=?, platform=COALESCE(?,platform), pkg_type=? WHERE id=?",
                (pkg_info["content_id"], pkg_info.get("platform"), pkg_info.get("pkg_type"), row["id"]))
            updated += 1

    conn.commit()
    conn.close()
    return {"updated": updated, "total_scanned": len(rows) + len(pkg_rows)}


def auto_titles():
    """Lookup metadata via APIs for files without titles, auto-create game entries."""
    from config import RAWG_API_KEY, IGDB_CLIENT_ID, IGDB_SECRET, MOBY_API_KEY
    has_any_api = RAWG_API_KEY or (IGDB_CLIENT_ID and IGDB_SECRET) or MOBY_API_KEY
    if not has_any_api:
        return {"error": "No API key configured (RAWG / IGDB / MobyGames)"}

    conn = get_db()
    rows = conn.execute("""SELECT gf.id, gf.content_id, gf.detected_title, gf.filepath,
                                  gf.platform, gf.game_id
                           FROM game_files gf
                           WHERE gf.content_id IS NOT NULL AND gf.content_id != ''""").fetchall()
    updated = auto_created = 0
    sources_used = {}

    for row in rows:
        cid = row["content_id"]
        fpath = row["filepath"]
        current_title = row["detected_title"] or ""
        platform = row["platform"]
        path_title = _title_from_path(fpath) or ""
        if current_title and current_title != path_title:
            continue

        folder_title = _title_from_path(fpath)
        result = search_metadata(folder_title, platform=platform, content_id=cid)
        if result:
            conn.execute("UPDATE game_files SET detected_title=? WHERE id=?",
                         (result["title"], row["id"]))
            updated += 1
            src = result.get("source", "?")
            sources_used[src] = sources_used.get(src, 0) + 1

            if not row["game_id"]:
                existing = conn.execute(
                    "SELECT id FROM games WHERE title=? OR ps_code LIKE ?",
                    (result["title"], f"%{cid[:9]}%")).fetchone()
                if not existing:
                    cur = conn.execute("""INSERT INTO games
                        (title, platform, ps_code, cover_url, banner_url, description,
                         genre, developer, publisher, release_date, metacritic,
                         rawg_id, status, metadata_source)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (result["title"],
                         result.get("platform") or platform or "PS1",
                         cid,
                         result.get("cover_url", ""),
                         result.get("banner_url", ""),
                         result.get("description", ""),
                         result.get("genre", ""),
                         result.get("developer", ""),
                         result.get("publisher", ""),
                         result.get("release_date", ""),
                         result.get("metacritic"),
                         result.get("rawg_id"),
                         "Wishlist", src))
                    new_gid = cur.lastrowid
                    conn.execute("UPDATE game_files SET game_id=? WHERE id=?", (new_gid, row["id"]))
                    auto_created += 1
                elif existing:
                    conn.execute("UPDATE game_files SET game_id=? WHERE id=?",
                                 (existing["id"], row["id"]))
        time.sleep(0.3)

    conn.commit()
    conn.close()
    return {
        "updated_titles": updated,
        "auto_created_games": auto_created,
        "total_checked": len(rows),
        "sources": sources_used
    }
