"""Background download monitor — polls clients, auto-imports, auto-monitors Wishlist."""
import os, time, shutil, threading
from db import get_db, load_settings
from config import GAMES_DIR, DOWNLOADS_DIR
from services.pkg_parser import safe_folder_name, get_file_size_str

_stop_event = threading.Event()
_thread = None


def start_monitor():
    """Start the download monitor daemon thread."""
    global _thread
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_monitor_loop, daemon=True, name="download-monitor")
    _thread.start()
    print("[dl-monitor] Started")


def _monitor_loop():
    """Main loop — checks every 30s, auto-monitor on longer interval."""
    last_auto_check = 0
    while not _stop_event.wait(30):
        try:
            _check_downloads()
        except Exception as e:
            print(f"[dl-monitor] Check error: {e}")

        # Auto-monitor check
        s = load_settings()
        am = s.get("auto_monitor", {})
        if am.get("enabled"):
            interval = max(am.get("interval_minutes", 30), 5) * 60
            if time.time() - last_auto_check > interval:
                last_auto_check = time.time()
                try:
                    _auto_monitor_check()
                except Exception as e:
                    print(f"[auto-monitor] Error: {e}")


def _check_downloads():
    """Poll download clients for active downloads, update progress."""
    from services.download_clients import get_client

    conn = get_db()
    try:
        active = conn.execute(
            "SELECT * FROM downloads WHERE status IN ('pending','downloading','paused')"
        ).fetchall()

        for dl in active:
            dl = dict(dl)
            client_name = dl.get("download_client")
            client_id = dl.get("client_id")
            if not client_name or not client_id:
                continue

            client = get_client(client_name)
            if not client:
                continue

            info = client.get_torrent(client_id)
            if not info:
                # Client might have removed it
                if dl["status"] == "downloading":
                    conn.execute(
                        "UPDATE downloads SET status='failed', error_message='Torrent disappeared from client' WHERE id=?",
                        (dl["id"],))
                continue

            # Update progress
            updates = {
                "progress": info["progress"],
                "download_speed": info.get("download_speed", 0),
                "seeders": info.get("seeders", 0),
                "leechers": info.get("leechers", 0),
            }

            new_status = info["status"]
            if info.get("save_path"):
                updates["save_path"] = info["save_path"]
            if info.get("size") and info["size"] > 0:
                updates["size"] = info["size"]

            if new_status == "completed" and dl["status"] != "completed":
                updates["status"] = "completed"
                updates["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[dl-monitor] Completed: {dl['title']}")
                # Try to import
                try:
                    _import_completed(conn, dl, info)
                    updates["status"] = "imported"
                except Exception as e:
                    print(f"[dl-monitor] Import error for {dl['title']}: {e}")
                    updates["error_message"] = f"Import error: {e}"
            elif new_status == "failed" and dl["status"] != "failed":
                updates["status"] = "failed"
                updates["error_message"] = "Download failed"
            elif new_status in ("downloading", "paused"):
                updates["status"] = new_status

            set_clause = ", ".join(f"{k}=?" for k in updates)
            values = list(updates.values()) + [dl["id"]]
            conn.execute(f"UPDATE downloads SET {set_clause} WHERE id=?", values)

        conn.commit()
    finally:
        conn.close()


def _import_completed(conn, dl, info):
    """Import completed download into game library."""
    save_path = info.get("save_path") or dl.get("save_path") or ""
    if not save_path or not os.path.exists(save_path):
        print(f"[dl-monitor] Save path not found: {save_path}")
        return

    game_id = dl.get("game_id")
    if not game_id:
        return

    game = conn.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
    if not game:
        return

    game = dict(game)
    platform = game.get("platform", "PS5")
    title = game.get("title", "Unknown")
    dest_dir = os.path.join(GAMES_DIR, platform, safe_folder_name(title))
    os.makedirs(dest_dir, exist_ok=True)

    # Move files from save_path to game folder
    if os.path.isfile(save_path):
        fname = os.path.basename(save_path)
        dest = os.path.join(dest_dir, fname)
        if not os.path.exists(dest):
            shutil.move(save_path, dest)
            _insert_file(conn, game_id, fname, dest, platform)
    elif os.path.isdir(save_path):
        for root, dirs, files in os.walk(save_path):
            for fname in files:
                src = os.path.join(root, fname)
                rel = os.path.relpath(src, save_path)
                dest = os.path.join(dest_dir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if not os.path.exists(dest):
                    shutil.move(src, dest)
                    _insert_file(conn, game_id, fname, dest, platform)

    print(f"[dl-monitor] Imported: {title} → {dest_dir}")


def _insert_file(conn, game_id, filename, filepath, platform):
    """Insert a game file record after import."""
    ext = os.path.splitext(filename)[1].lower()
    file_type = {
        '.iso': 'ISO', '.pkg': 'PKG', '.bin': 'BIN', '.cue': 'CUE',
        '.chd': 'CHD', '.pbp': 'PBP', '.rar': 'RAR', '.zip': 'ZIP',
        '.img': 'IMG', '.apk': 'APK'
    }.get(ext, ext.upper().lstrip('.') or 'OTHER')
    try:
        fsize = os.path.getsize(filepath)
    except:
        fsize = 0
    # Check if already exists
    existing = conn.execute("SELECT id FROM game_files WHERE filepath=?", (filepath,)).fetchone()
    if existing:
        return
    conn.execute("""INSERT INTO game_files
        (game_id, filename, filepath, file_type, platform, file_size, file_size_str, is_uploaded)
        VALUES (?,?,?,?,?,?,?,0)""",
        (game_id, filename, filepath, file_type, platform, fsize, get_file_size_str(fsize)))


def _auto_monitor_check():
    """Check Wishlist games and auto-grab from Prowlarr."""
    from services.prowlarr import search_for_game
    from services.download_clients import get_client, get_client_config

    conn = get_db()
    try:
        # Get monitored Wishlist games
        games = conn.execute(
            "SELECT * FROM games WHERE status='Wishlist' AND monitored=1"
        ).fetchall()

        if not games:
            return

        cfg = get_client_config()
        default_client = cfg.get("default_client", "qbittorrent")
        client = get_client(default_client)
        if not client:
            return

        for game in games:
            game = dict(game)
            # Check if already has an active download
            existing = conn.execute(
                "SELECT id FROM downloads WHERE game_id=? AND status IN ('pending','downloading','paused','completed','imported')",
                (game["id"],)
            ).fetchone()
            if existing:
                continue

            # Search Prowlarr
            results = search_for_game(game["title"], game.get("platform"))
            if not results:
                continue

            # Pick best result (most seeders, reasonable size)
            best = results[0]  # Already sorted by seeders
            if best["seeders"] < 1:
                continue

            # Grab it
            ok, msg, client_id = client.add_torrent(
                best["download_url"],
                save_path=cfg.get(default_client, {}).get("save_path", DOWNLOADS_DIR)
            )
            if not ok:
                print(f"[auto-monitor] Failed to grab {game['title']}: {msg}")
                continue

            conn.execute("""INSERT INTO downloads
                (game_id, title, indexer, download_url, download_client, client_id,
                 size, status, seeders, leechers, save_path, auto_grabbed)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
                (game["id"], best["title"], best.get("indexer", ""), best["download_url"],
                 default_client, client_id or "", best.get("size", 0), "downloading",
                 best.get("seeders", 0), best.get("leechers", 0),
                 cfg.get(default_client, {}).get("save_path", DOWNLOADS_DIR)))

            print(f"[auto-monitor] Auto-grabbed: {game['title']} → {best['title']}")
            time.sleep(2)  # Rate limit

        conn.commit()
    finally:
        conn.close()
