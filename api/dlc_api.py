"""DLC management API — upload, list, delete, download, associate."""
import os, time
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename

from db import get_db
from services.pkg_parser import parse_pkg, safe_folder_name, get_file_size_str
from services.paths import get_dlc_dir

dlc_bp = Blueprint("dlc", __name__)


def _game_dlc_dir(platform, title):
    """Structure: {dlc_dir}/{platform}/{game_slug}/"""
    return os.path.join(get_dlc_dir(), platform or "unknown", safe_folder_name(title))


# ─── List ─────────────────────────────────────────────────────────────────────

@dlc_bp.route("/api/dlc", methods=["GET"])
def list_dlc():
    game_id = request.args.get("game_id")
    conn = get_db()
    q = ("SELECT gd.*, g.title as game_title, g.platform as game_platform "
         "FROM game_dlc gd LEFT JOIN games g ON gd.game_id=g.id WHERE 1=1")
    p = []
    if game_id:
        q += " AND gd.game_id=?"; p.append(game_id)
    q += " ORDER BY gd.added_at DESC"
    dlcs = conn.execute(q, p).fetchall()
    conn.close()
    return jsonify([dict(d) for d in dlcs])


# ─── Upload ───────────────────────────────────────────────────────────────────

@dlc_bp.route("/api/dlc/upload", methods=["POST"])
def upload_dlc():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    f       = request.files['file']
    game_id = request.form.get("game_id", "").strip() or None
    fname   = secure_filename(f.filename)
    ext     = Path(fname).suffix.lower()

    conn    = get_db()
    dlc_dir = get_dlc_dir()

    # Save to temp first (so we can parse PKG before deciding dest)
    tmp_dir = os.path.join(dlc_dir, "_uploading")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, fname)
    if os.path.exists(tmp_path):
        tmp_path = os.path.join(tmp_dir,
            Path(fname).stem + f"_{int(time.time())}" + ext)
    f.save(tmp_path)

    content_id = None
    file_type  = ext.lstrip('.').upper()

    if ext == '.pkg':
        try:
            pkg_info   = parse_pkg(tmp_path)
            content_id = pkg_info.get("content_id")
        except Exception:
            pass
        # Try auto-match by content_id if no game_id supplied
        if not game_id and content_id:
            row = conn.execute("SELECT id FROM games WHERE ps_code LIKE ?",
                               (f"%{content_id[:9]}%",)).fetchone()
            if row:
                game_id = row["id"]

    if game_id:
        game = conn.execute("SELECT id, platform, title FROM games WHERE id=?",
                            (int(game_id),)).fetchone()
        if game:
            plat     = game["platform"] or "unknown"
            dest_dir = _game_dlc_dir(plat, game["title"])
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, fname)
            if os.path.exists(dest_path):
                dest_path = os.path.join(dest_dir,
                    Path(fname).stem + f"_{int(time.time())}" + ext)
            os.rename(tmp_path, dest_path)
            fsize = os.path.getsize(dest_path)
            cur = conn.execute(
                "INSERT INTO game_dlc "
                "(game_id, filename, filepath, file_type, content_id, "
                "file_size, file_size_str, platform, is_uploaded, added_at) "
                "VALUES (?,?,?,?,?,?,?,?,1,datetime('now'))",
                (int(game_id), os.path.basename(dest_path), dest_path,
                 file_type, content_id, fsize, get_file_size_str(fsize), plat))
            conn.commit()
            rec = conn.execute("SELECT * FROM game_dlc WHERE id=?",
                               (cur.lastrowid,)).fetchone()
            conn.close()
            return jsonify(dict(rec)), 201

    # No game — general folder
    dest_dir = os.path.join(dlc_dir, "_general")
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, fname)
    if os.path.exists(dest_path):
        dest_path = os.path.join(dest_dir,
            Path(fname).stem + f"_{int(time.time())}" + ext)
    os.rename(tmp_path, dest_path)
    fsize = os.path.getsize(dest_path)
    cur = conn.execute(
        "INSERT INTO game_dlc "
        "(game_id, filename, filepath, file_type, content_id, "
        "file_size, file_size_str, platform, is_uploaded, added_at) "
        "VALUES (?,?,?,?,?,?,?,?,1,datetime('now'))",
        (None, os.path.basename(dest_path), dest_path,
         file_type, content_id, fsize, get_file_size_str(fsize), None))
    conn.commit()
    rec = conn.execute("SELECT * FROM game_dlc WHERE id=?",
                       (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(rec)), 201


# ─── Delete ───────────────────────────────────────────────────────────────────

@dlc_bp.route("/api/dlc/<int:did>", methods=["DELETE"])
def delete_dlc(did):
    conn = get_db()
    row  = conn.execute("SELECT * FROM game_dlc WHERE id=?", (did,)).fetchone()
    if row and row["is_uploaded"] and os.path.exists(row["filepath"]):
        try: os.remove(row["filepath"])
        except: pass
    conn.execute("DELETE FROM game_dlc WHERE id=?", (did,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ─── Download ─────────────────────────────────────────────────────────────────

@dlc_bp.route("/api/dlc/<int:did>/download")
def download_dlc(did):
    conn = get_db()
    row  = conn.execute("SELECT * FROM game_dlc WHERE id=?", (did,)).fetchone()
    conn.close()
    if not row: abort(404)
    if not os.path.exists(row["filepath"]): abort(404)
    return send_file(row["filepath"], as_attachment=True,
                     download_name=row["filename"])


# ─── Associate ────────────────────────────────────────────────────────────────

@dlc_bp.route("/api/dlc/<int:did>/associate", methods=["PUT"])
def associate_dlc(did):
    game_id = (request.json or {}).get("game_id")
    conn = get_db()
    conn.execute("UPDATE game_dlc SET game_id=? WHERE id=?", (game_id, did))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})
