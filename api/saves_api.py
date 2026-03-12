"""Saves management API — upload, list, delete, download, associate."""
import os, time, io, zipfile, shutil
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename

from db import get_db
from services.pkg_parser import safe_folder_name, get_file_size_str
from services.paths import get_saves_dir

saves_bp = Blueprint("saves", __name__)


def _game_saves_dir(platform, title):
    """Structure: {saves_dir}/{platform}/{game_slug}/"""
    return os.path.join(get_saves_dir(), platform or "unknown", safe_folder_name(title))


# ─── List ─────────────────────────────────────────────────────────────────────

@saves_bp.route("/api/saves", methods=["GET"])
def list_saves():
    game_id = request.args.get("game_id")
    conn = get_db()
    q = ("SELECT gs.*, g.title as game_title, g.platform as game_platform "
         "FROM game_saves gs LEFT JOIN games g ON gs.game_id=g.id WHERE 1=1")
    p = []
    if game_id:
        q += " AND gs.game_id=?"; p.append(game_id)
    q += " ORDER BY gs.added_at DESC"
    saves = conn.execute(q, p).fetchall()
    conn.close()
    return jsonify([dict(s) for s in saves])


# ─── Upload ───────────────────────────────────────────────────────────────────

@saves_bp.route("/api/saves/upload", methods=["POST"])
def upload_save():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    f       = request.files['file']
    game_id = request.form.get("game_id", "").strip() or None
    fname   = secure_filename(f.filename)
    ext     = Path(fname).suffix.lower()

    conn      = get_db()
    saves_dir = get_saves_dir()

    if game_id:
        game = conn.execute("SELECT id, platform, title FROM games WHERE id=?",
                            (int(game_id),)).fetchone()
        if game:
            plat     = game["platform"] or "unknown"
            dest_dir = _game_saves_dir(plat, game["title"])
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, fname)
            if os.path.exists(dest_path):
                dest_path = os.path.join(dest_dir,
                    Path(fname).stem + f"_{int(time.time())}" + ext)
            f.save(dest_path)
            fsize = os.path.getsize(dest_path)
            cur = conn.execute(
                "INSERT INTO game_saves "
                "(game_id, filename, filepath, file_size, file_size_str, platform, is_uploaded, added_at) "
                "VALUES (?,?,?,?,?,?,1,datetime('now'))",
                (int(game_id), os.path.basename(dest_path), dest_path,
                 fsize, get_file_size_str(fsize), plat))
            conn.commit()
            rec = conn.execute("SELECT * FROM game_saves WHERE id=?",
                               (cur.lastrowid,)).fetchone()
            conn.close()
            return jsonify(dict(rec)), 201

    # General — no game
    dest_dir = os.path.join(saves_dir, "_general")
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, fname)
    if os.path.exists(dest_path):
        dest_path = os.path.join(dest_dir,
            Path(fname).stem + f"_{int(time.time())}" + ext)
    f.save(dest_path)
    fsize = os.path.getsize(dest_path)
    cur = conn.execute(
        "INSERT INTO game_saves "
        "(game_id, filename, filepath, file_size, file_size_str, platform, is_uploaded, added_at) "
        "VALUES (?,?,?,?,?,?,1,datetime('now'))",
        (None, os.path.basename(dest_path), dest_path,
         fsize, get_file_size_str(fsize), None))
    conn.commit()
    rec = conn.execute("SELECT * FROM game_saves WHERE id=?",
                       (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(rec)), 201


# ─── Upload folder ────────────────────────────────────────────────────────────

@saves_bp.route("/api/saves/upload-folder", methods=["POST"])
def upload_save_folder():
    files      = request.files.getlist("files[]")
    rel_paths  = request.form.getlist("relative_paths[]")
    folder_name = secure_filename(request.form.get("folder_name", "").strip()) or "save_folder"
    game_id    = request.form.get("game_id", "").strip() or None

    if not files:
        return jsonify({"error": "No files"}), 400

    conn      = get_db()
    saves_dir = get_saves_dir()

    if game_id:
        game = conn.execute("SELECT id, platform, title FROM games WHERE id=?",
                            (int(game_id),)).fetchone()
        if game:
            base_dir = _game_saves_dir(game["platform"] or "unknown", game["title"])
            plat     = game["platform"] or "unknown"
        else:
            base_dir = os.path.join(saves_dir, "_general"); plat = None
    else:
        base_dir = os.path.join(saves_dir, "_general"); plat = None

    # Destination folder — avoid overwriting
    root_folder = os.path.join(base_dir, folder_name)
    if os.path.exists(root_folder):
        root_folder = os.path.join(base_dir, f"{folder_name}_{int(time.time())}")
    os.makedirs(root_folder, exist_ok=True)

    total_size = 0
    for f, rel in zip(files, rel_paths):
        # rel = "FolderName/sub/file.ext" — remove the first component (folderName)
        parts = rel.replace("\\", "/").strip("/").split("/")
        inner = parts[1:] if len(parts) > 1 else parts
        if not inner or not inner[-1]:
            continue
        # Sanitize each component
        safe_parts = [secure_filename(p) for p in inner if p]
        if not safe_parts:
            continue
        dest_dir = os.path.join(root_folder, *safe_parts[:-1]) if len(safe_parts) > 1 else root_folder
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, safe_parts[-1])
        f.save(dest_path)
        total_size += os.path.getsize(dest_path)

    cur = conn.execute(
        "INSERT INTO game_saves "
        "(game_id, filename, filepath, file_size, file_size_str, platform, is_uploaded, added_at) "
        "VALUES (?,?,?,?,?,?,1,datetime('now'))",
        (int(game_id) if game_id else None,
         folder_name + "/",          # trailing / → indicator folder
         root_folder,
         total_size,
         get_file_size_str(total_size),
         plat))
    conn.commit()
    rec = conn.execute("SELECT * FROM game_saves WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(rec)), 201


# ─── Delete ───────────────────────────────────────────────────────────────────

@saves_bp.route("/api/saves/<int:sid>", methods=["DELETE"])
def delete_save(sid):
    conn = get_db()
    row  = conn.execute("SELECT * FROM game_saves WHERE id=?", (sid,)).fetchone()
    if row and row["is_uploaded"]:
        fp = row["filepath"]
        if os.path.isdir(fp):
            try: shutil.rmtree(fp)
            except: pass
        elif os.path.exists(fp):
            try: os.remove(fp)
            except: pass
    conn.execute("DELETE FROM game_saves WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ─── Download ─────────────────────────────────────────────────────────────────

@saves_bp.route("/api/saves/<int:sid>/download")
def download_save(sid):
    conn = get_db()
    row  = conn.execute("SELECT * FROM game_saves WHERE id=?", (sid,)).fetchone()
    conn.close()
    if not row: abort(404)
    fp = row["filepath"]
    if not os.path.exists(fp): abort(404)

    # Folder save — served as ZIP
    if os.path.isdir(fp):
        folder_name = os.path.basename(fp)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(fp):
                for fname in files:
                    full = os.path.join(root, fname)
                    arc  = os.path.join(folder_name, os.path.relpath(full, fp))
                    zf.write(full, arc)
        buf.seek(0)
        return send_file(buf, as_attachment=True,
                         download_name=folder_name + ".zip",
                         mimetype="application/zip")

    return send_file(fp, as_attachment=True, download_name=row["filename"])


# ─── Associate ────────────────────────────────────────────────────────────────

@saves_bp.route("/api/saves/<int:sid>/associate", methods=["PUT"])
def associate_save(sid):
    game_id = (request.json or {}).get("game_id")
    conn = get_db()
    conn.execute("UPDATE game_saves SET game_id=? WHERE id=?", (game_id, sid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})
