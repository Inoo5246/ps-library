"""Downloads API — Prowlarr search + download client management."""
import time
from flask import Blueprint, request, jsonify
from db import get_db
from config import DOWNLOADS_DIR

downloads_bp = Blueprint("downloads", __name__)


# ─── Prowlarr endpoints ─────────────────────────────────────────────────────

@downloads_bp.route("/api/prowlarr/status")
def prowlarr_status():
    from services.prowlarr import test_connection, get_indexers
    ok, msg = test_connection()
    indexers = get_indexers() if ok else []
    return jsonify({"ok": ok, "message": msg, "indexers": indexers})


@downloads_bp.route("/api/prowlarr/indexers")
def prowlarr_indexers():
    from services.prowlarr import get_indexers
    return jsonify(get_indexers())


# ─── Search ──────────────────────────────────────────────────────────────────

@downloads_bp.route("/api/downloads/search", methods=["POST"])
def search():
    data = request.json or {}
    query = data.get("query", "").strip()
    platform = data.get("platform")
    game_id = data.get("game_id")

    if game_id and not query:
        conn = get_db()
        game = conn.execute("SELECT title, platform FROM games WHERE id=?", (game_id,)).fetchone()
        conn.close()
        if game:
            query = query or game["title"]
            platform = platform or game["platform"]

    if not query:
        return jsonify({"error": "Missing query"}), 400

    ps_only = data.get("ps_only", True)  # default: only PS categories
    from services.prowlarr import search_for_game
    results = search_for_game(query, platform, ps_only=ps_only)
    return jsonify(results)


# ─── Grab (send to download client) ─────────────────────────────────────────

@downloads_bp.route("/api/downloads/grab", methods=["POST"])
def grab():
    data = request.json or {}
    download_url = data.get("download_url")
    title = data.get("title", "Unknown")
    if not download_url:
        return jsonify({"error": "Missing download_url"}), 400

    from services.download_clients import get_client, get_client_config
    cfg = get_client_config()
    client_name = data.get("client") or cfg.get("default_client", "qbittorrent")
    client = get_client(client_name)
    if not client:
        return jsonify({"error": f"Client '{client_name}' is not configured"}), 400

    save_path = cfg.get(client_name, {}).get("save_path", DOWNLOADS_DIR)
    ok, msg, client_id = client.add_torrent(download_url, save_path)
    if not ok:
        return jsonify({"error": msg}), 500

    game_id = data.get("game_id")
    conn = get_db()
    try:
        conn.execute("""INSERT INTO downloads
            (game_id, title, indexer, download_url, download_client, client_id,
             size, status, seeders, leechers, save_path)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (game_id, title, data.get("indexer", ""), download_url,
             client_name, client_id or "", data.get("size", 0), "downloading",
             data.get("seeders", 0), data.get("leechers", 0), save_path))
        conn.commit()
        dl = conn.execute("SELECT * FROM downloads ORDER BY id DESC LIMIT 1").fetchone()
        return jsonify({"ok": True, "download": dict(dl)})
    finally:
        conn.close()


# ─── Downloads CRUD ──────────────────────────────────────────────────────────

@downloads_bp.route("/api/downloads")
def list_downloads():
    status = request.args.get("status")
    conn = get_db()
    try:
        if status:
            rows = conn.execute(
                "SELECT d.*, g.title as game_title, g.platform as game_platform, g.cover_url as game_cover "
                "FROM downloads d LEFT JOIN games g ON d.game_id=g.id "
                "WHERE d.status=? ORDER BY d.added_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT d.*, g.title as game_title, g.platform as game_platform, g.cover_url as game_cover "
                "FROM downloads d LEFT JOIN games g ON d.game_id=g.id "
                "ORDER BY d.added_at DESC").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@downloads_bp.route("/api/downloads/<int:did>")
def get_download(did):
    conn = get_db()
    try:
        dl = conn.execute(
            "SELECT d.*, g.title as game_title FROM downloads d "
            "LEFT JOIN games g ON d.game_id=g.id WHERE d.id=?", (did,)).fetchone()
        if not dl:
            return jsonify({"error": "Not found"}), 404
        return jsonify(dict(dl))
    finally:
        conn.close()


@downloads_bp.route("/api/downloads/<int:did>", methods=["DELETE"])
def delete_download(did):
    conn = get_db()
    try:
        dl = conn.execute("SELECT * FROM downloads WHERE id=?", (did,)).fetchone()
        if not dl:
            return jsonify({"error": "Not found"}), 404
        dl = dict(dl)

        # Remove from client if still active
        if dl.get("client_id") and dl.get("download_client") and dl["status"] in ("downloading", "paused", "pending"):
            from services.download_clients import get_client
            client = get_client(dl["download_client"])
            if client:
                delete_files = request.args.get("delete_files") == "true"
                client.remove(dl["client_id"], delete_files)

        conn.execute("DELETE FROM downloads WHERE id=?", (did,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@downloads_bp.route("/api/downloads/<int:did>/pause", methods=["POST"])
def pause_download(did):
    conn = get_db()
    try:
        dl = conn.execute("SELECT * FROM downloads WHERE id=?", (did,)).fetchone()
        if not dl:
            return jsonify({"error": "Not found"}), 404
        dl = dict(dl)
        if dl.get("client_id") and dl.get("download_client"):
            from services.download_clients import get_client
            client = get_client(dl["download_client"])
            if client:
                client.pause(dl["client_id"])
        conn.execute("UPDATE downloads SET status='paused' WHERE id=?", (did,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@downloads_bp.route("/api/downloads/<int:did>/resume", methods=["POST"])
def resume_download(did):
    conn = get_db()
    try:
        dl = conn.execute("SELECT * FROM downloads WHERE id=?", (did,)).fetchone()
        if not dl:
            return jsonify({"error": "Not found"}), 404
        dl = dict(dl)
        if dl.get("client_id") and dl.get("download_client"):
            from services.download_clients import get_client
            client = get_client(dl["download_client"])
            if client:
                client.resume(dl["client_id"])
        conn.execute("UPDATE downloads SET status='downloading' WHERE id=?", (did,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@downloads_bp.route("/api/downloads/<int:did>/retry", methods=["POST"])
def retry_download(did):
    conn = get_db()
    try:
        dl = conn.execute("SELECT * FROM downloads WHERE id=?", (did,)).fetchone()
        if not dl:
            return jsonify({"error": "Not found"}), 404
        dl = dict(dl)
        if not dl.get("download_url"):
            return jsonify({"error": "No download URL available"}), 400

        from services.download_clients import get_client, get_client_config
        cfg = get_client_config()
        client_name = dl.get("download_client") or cfg.get("default_client")
        client = get_client(client_name)
        if not client:
            return jsonify({"error": "Client unavailable"}), 400

        save_path = cfg.get(client_name, {}).get("save_path", DOWNLOADS_DIR)
        ok, msg, client_id = client.add_torrent(dl["download_url"], save_path)
        if not ok:
            return jsonify({"error": msg}), 500

        conn.execute(
            "UPDATE downloads SET status='downloading', progress=0, error_message=NULL, "
            "client_id=?, download_client=?, save_path=? WHERE id=?",
            (client_id or "", client_name, save_path, did))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


# ─── Download clients status/test ────────────────────────────────────────────

@downloads_bp.route("/api/downloads/clients/status")
def clients_status():
    from services.download_clients import get_client_config, test_client
    cfg = get_client_config()
    result = {"default": cfg.get("default_client", "qbittorrent")}
    for name in ("qbittorrent", "transmission"):
        c = cfg.get(name, {})
        if c.get("enabled") and c.get("url"):
            ok, msg = test_client(name)
            result[name] = {"enabled": True, "ok": ok, "message": msg}
        else:
            result[name] = {"enabled": False, "ok": False, "message": "Disabled"}
    return jsonify(result)


@downloads_bp.route("/api/downloads/clients/test", methods=["POST"])
def test_client_endpoint():
    data = request.json or {}
    name = data.get("client", "")
    if name not in ("qbittorrent", "transmission"):
        return jsonify({"error": "Unknown client"}), 400
    from services.download_clients import test_client
    ok, msg = test_client(name)
    return jsonify({"ok": ok, "message": msg})


# ─── Game monitoring toggle ──────────────────────────────────────────────────

@downloads_bp.route("/api/games/<int:gid>/monitor", methods=["POST"])
def toggle_monitor(gid):
    data = request.json or {}
    monitored = 1 if data.get("monitored") else 0
    conn = get_db()
    try:
        conn.execute("UPDATE games SET monitored=? WHERE id=?", (monitored, gid))
        conn.commit()
        return jsonify({"ok": True, "monitored": monitored})
    finally:
        conn.close()
