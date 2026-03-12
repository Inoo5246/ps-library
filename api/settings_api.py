import os, time
from pathlib import Path
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from db import load_settings, save_settings
from config import LANG_DIR, ALLOWED_GAME_EXTS, ALLOWED_LICENSE_EXTS

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(load_settings())


@settings_bp.route("/api/settings", methods=["PUT"])
def update_settings():
    data = request.json
    folders = data.get("custom_folders", [])
    for i, f in enumerate(folders):
        if not f.get("id"):
            f["id"] = f"cf_{int(time.time())}_{i}"
        if not f.get("path"):
            return jsonify({"error": f"Folder {i+1}: path is required"}), 400
        if not f.get("platform"):
            return jsonify({"error": f"Folder {i+1}: platform is required"}), 400
    save_settings(data)
    return jsonify({"ok": True, "settings": load_settings()})


@settings_bp.route("/api/settings/test-path", methods=["POST"])
def test_path():
    p = request.json.get("path", "")
    if not p:
        return jsonify({"exists": False, "error": "Empty path"})
    exists = os.path.isdir(p)
    file_count = 0
    if exists:
        try:
            for f in os.listdir(p):
                ext = Path(f).suffix.lower()
                if ext in ALLOWED_GAME_EXTS or ext in ALLOWED_LICENSE_EXTS:
                    file_count += 1
        except: pass
    return jsonify({"exists": exists, "file_count": file_count, "path": p})


@settings_bp.route("/api/settings/browse-dirs", methods=["POST"])
def browse_dirs():
    p = request.json.get("path", "/")
    if not p: p = "/"
    p = os.path.normpath(p)
    blocked = ["/proc", "/sys", "/dev", "/run", "/boot", "/sbin", "/bin",
               "/usr/sbin", "/usr/bin", "/usr/lib", "/lib", "/lib64", "/etc/shadow"]
    if any(p.startswith(b) for b in blocked):
        return jsonify({"path": p, "dirs": [], "error": "Access restricted"})
    if not os.path.isdir(p):
        return jsonify({"path": p, "dirs": [], "parent": os.path.dirname(p), "error": "Does not exist"})
    try:
        entries = sorted(os.listdir(p))
    except PermissionError:
        return jsonify({"path": p, "dirs": [], "error": "No permissions"})
    dirs = []
    game_files_count = 0
    for e in entries:
        full = os.path.join(p, e)
        if os.path.isdir(full) and not e.startswith('.'):
            gf = 0
            try:
                for f in os.listdir(full):
                    if Path(f).suffix.lower() in ALLOWED_GAME_EXTS: gf += 1
            except: pass
            dirs.append({"name": e, "path": full, "game_files": gf})
        elif os.path.isfile(full):
            if Path(e).suffix.lower() in ALLOWED_GAME_EXTS:
                game_files_count += 1
    parent = os.path.dirname(p) if p != "/" else None
    return jsonify({
        "path": p, "parent": parent,
        "dirs": dirs, "game_files_here": game_files_count
    })


@settings_bp.route("/api/lang")
def list_languages():
    langs = []
    if os.path.isdir(LANG_DIR):
        for fname in sorted(os.listdir(LANG_DIR)):
            if fname.endswith('.json'):
                code = fname[:-5]
                try:
                    import json
                    with open(os.path.join(LANG_DIR, fname), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    langs.append({"code": code, "name": data.get("lang_name", code)})
                except:
                    langs.append({"code": code, "name": code})
    return jsonify(langs)


@settings_bp.route("/api/lang/<code>")
def get_language(code):
    import json
    safe_code = secure_filename(code)
    fpath = os.path.join(LANG_DIR, f"{safe_code}.json")
    if not os.path.exists(fpath):
        return jsonify({"error": "Language not found"}), 404
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify(data)
