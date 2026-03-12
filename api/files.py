import os, time
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename

from db import get_db
from config import (GAMES_DIR, LICENSES_DIR, ALLOWED_GAME_EXTS, ALLOWED_LICENSE_EXTS,
                    ALLOWED_IMAGE_EXTS, PLATFORMS)
from services.pkg_parser import (parse_pkg, parse_disc_image, parse_license,
                                  get_file_size_str, safe_folder_name, get_game_dir,
                                  _title_from_path, _detect_platform_from_path, _auto_link_game)
from services.metadata import search_metadata, download_image_url
from services import scanner as scanner_svc

files_bp = Blueprint("files", __name__)


@files_bp.route("/api/files", methods=["GET"])
def list_files():
    game_id  = request.args.get("game_id")
    platform = request.args.get("platform")
    ftype    = request.args.get("type")
    conn = get_db()
    q = ("SELECT gf.*, g.title as game_title, g.cover_url as game_cover "
         "FROM game_files gf LEFT JOIN games g ON gf.game_id=g.id WHERE 1=1")
    p = []
    if game_id:  q += " AND gf.game_id=?"; p.append(game_id)
    if platform: q += " AND gf.platform=?"; p.append(platform)
    if ftype:    q += " AND gf.file_type=?"; p.append(ftype.upper())
    q += " ORDER BY gf.platform, gf.filename"
    files = conn.execute(q, p).fetchall()
    conn.close()
    return jsonify([dict(f) for f in files])


@files_bp.route("/api/licenses", methods=["GET"])
def list_licenses():
    game_id = request.args.get("game_id")
    conn = get_db()
    q = ("SELECT l.*, g.title as game_title "
         "FROM licenses l LEFT JOIN games g ON l.game_id=g.id WHERE 1=1")
    p = []
    if game_id: q += " AND l.game_id=?"; p.append(game_id)
    q += " ORDER BY l.filename"
    lic = conn.execute(q, p).fetchall()
    conn.close()
    return jsonify([dict(l) for l in lic])


@files_bp.route("/api/files/scan", methods=["POST"])
def scan_files():
    result = scanner_svc.scan_files()
    return jsonify(result)


@files_bp.route("/api/files/rescan-metadata", methods=["POST"])
def rescan_metadata():
    result = scanner_svc.rescan_metadata()
    return jsonify(result)


@files_bp.route("/api/files/auto-titles", methods=["POST"])
def auto_titles():
    result = scanner_svc.auto_titles()
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@files_bp.route("/api/files/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    f        = request.files['file']
    fname    = secure_filename(f.filename)
    ext      = Path(fname).suffix.lower()
    game_id  = request.form.get("game_id", "").strip() or None
    platform = request.form.get("platform", "").strip()
    notes    = request.form.get("notes", "").strip()
    auto_organize = request.form.get("auto_organize", "1") != "0"
    is_license = ext in ALLOWED_LICENSE_EXTS
    is_game    = ext in ALLOWED_GAME_EXTS
    if not (is_license or is_game):
        return jsonify({"error": f"Type not allowed: {ext}"}), 400
    conn = get_db()

    tmp_dir = os.path.join(GAMES_DIR, "_uploading")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, fname)
    if os.path.exists(tmp_path):
        tmp_path = os.path.join(tmp_dir, Path(fname).stem + f"_{int(time.time())}" + ext)
    f.save(tmp_path)
    fsize = os.path.getsize(tmp_path)

    if is_license:
        lic_info = parse_license(tmp_path)
        cid = lic_info.get("content_id")
        if not game_id and cid:
            row = conn.execute("SELECT id FROM games WHERE ps_code LIKE ?",
                               (f"%{cid[:9]}%",)).fetchone()
            if row: game_id = row["id"]
        if game_id:
            game = conn.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
            dest_dir = os.path.join(get_game_dir(game["platform"] or "PS3", game["title"]),
                                    "licenses") if game else LICENSES_DIR
        else:
            dest_dir = LICENSES_DIR
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, fname)
        if os.path.exists(dest_path):
            dest_path = os.path.join(dest_dir, Path(fname).stem + "_1" + ext)
        os.rename(tmp_path, dest_path)
        cur = conn.execute(
            "INSERT INTO licenses (game_id,filename,filepath,license_type,content_id,file_size,is_uploaded,notes) "
            "VALUES (?,?,?,?,?,?,1,?)",
            (game_id, fname, dest_path, ext.lstrip('.').upper(), cid, fsize, notes))
        conn.commit()
        rec = conn.execute(
            "SELECT l.*, g.title as game_title FROM licenses l "
            "LEFT JOIN games g ON l.game_id=g.id WHERE l.id=?", (cur.lastrowid,)).fetchone()
        conn.close()
        return jsonify({"type": "license", "record": dict(rec)}), 201

    # Game file upload
    content_id = None; plat_det = None; pkg_type = None; detected_title = None
    if ext == '.pkg':
        pkg_info = parse_pkg(tmp_path)
        content_id = pkg_info.get("content_id")
        plat_det   = pkg_info.get("platform")
        pkg_type   = pkg_info.get("pkg_type")
    elif ext in ('.iso', '.bin', '.img', '.pbp'):
        disc_info = parse_disc_image(tmp_path)
        content_id     = disc_info.get("content_id")
        plat_det       = disc_info.get("platform")
        detected_title = disc_info.get("detected_title")
    if not detected_title:
        detected_title = _title_from_path(tmp_path) or Path(fname).stem
    plat_det = plat_det or platform or _detect_platform_from_path(tmp_path) or "PS3"

    auto_created = False
    metadata = None
    if not game_id and content_id:
        row = conn.execute("SELECT id FROM games WHERE ps_code LIKE ?",
                           (f"%{content_id[:9]}%",)).fetchone()
        if row: game_id = row["id"]
    if not game_id:
        row = conn.execute("SELECT id FROM games WHERE title=? LIMIT 1",
                           (detected_title,)).fetchone()
        if row: game_id = row["id"]

    if not game_id and auto_organize:
        from config import RAWG_API_KEY, IGDB_CLIENT_ID, IGDB_SECRET, MOBY_API_KEY
        has_any_api = RAWG_API_KEY or (IGDB_CLIENT_ID and IGDB_SECRET) or MOBY_API_KEY
        if has_any_api:
            metadata = search_metadata(detected_title, platform=plat_det, content_id=content_id)
        if metadata:
            game_title = metadata.get("title") or detected_title
            row = conn.execute("SELECT id FROM games WHERE title=? OR ps_code LIKE ?",
                               (game_title, f"%{(content_id or 'XXXX')[:9]}%")).fetchone()
            if row:
                game_id = row["id"]
            else:
                cur = conn.execute("""INSERT INTO games
                    (title, platform, ps_code, cover_url, banner_url, description,
                     genre, developer, publisher, release_date, metacritic, rawg_id, status, metadata_source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (game_title, plat_det, content_id or "",
                     metadata.get("cover_url", ""), metadata.get("banner_url", ""),
                     metadata.get("description", ""), metadata.get("genre", ""),
                     metadata.get("developer", ""), metadata.get("publisher", ""),
                     metadata.get("release_date", ""), metadata.get("metacritic"),
                     metadata.get("rawg_id"), "Wishlist", metadata.get("source", "")))
                game_id = cur.lastrowid
                auto_created = True
                detected_title = game_title
        else:
            cur = conn.execute("INSERT INTO games (title, platform, ps_code, status) VALUES (?,?,?,?)",
                               (detected_title, plat_det, content_id or "", "Wishlist"))
            game_id = cur.lastrowid
            auto_created = True

    game = conn.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone() if game_id else None
    img_results = {}
    if game and auto_organize:
        game_dir = os.path.join(GAMES_DIR, plat_det, safe_folder_name(game["title"]))
        img_dir  = os.path.join(game_dir, "images")
        lic_dir  = os.path.join(game_dir, "licenses")
        os.makedirs(game_dir, exist_ok=True)
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lic_dir, exist_ok=True)
        dest_path = os.path.join(game_dir, fname)
        if os.path.exists(dest_path):
            dest_path = os.path.join(game_dir, Path(fname).stem + f"_{int(time.time())}" + ext)
        os.rename(tmp_path, dest_path)
        if auto_created and metadata:
            for img_type, url_field in [("cover", "cover_url"), ("banner", "banner_url")]:
                url = metadata.get(url_field, "")
                if not url or not url.startswith("http"): continue
                img_ext = Path(url.split("?")[0]).suffix.lower()
                if img_ext not in ALLOWED_IMAGE_EXTS: img_ext = ".jpg"
                img_fname = f"{img_type}_{game_id}{img_ext}"
                img_path = os.path.join(img_dir, img_fname)
                if download_image_url(url, img_path):
                    local_url = f"/game-images/{game_id}/{img_fname}"
                    conn.execute(f"UPDATE games SET {url_field}=? WHERE id=?", (local_url, game_id))
                    img_results[img_type] = local_url
    else:
        dest_dir = os.path.join(GAMES_DIR, plat_det) if plat_det else GAMES_DIR
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, fname)
        if os.path.exists(dest_path):
            dest_path = os.path.join(dest_dir, Path(fname).stem + f"_{int(time.time())}" + ext)
        os.rename(tmp_path, dest_path)

    cur = conn.execute("""INSERT INTO game_files
        (game_id,filename,filepath,file_type,platform,content_id,
         file_size,file_size_str,pkg_type,is_uploaded,notes,detected_title)
        VALUES (?,?,?,?,?,?,?,?,?,1,?,?)""",
        (game_id, fname, dest_path, ext.lstrip('.').upper(), plat_det,
         content_id, fsize, get_file_size_str(fsize), pkg_type, notes, detected_title))
    conn.commit()
    rec = conn.execute(
        "SELECT gf.*, g.title as game_title, g.cover_url as game_cover "
        "FROM game_files gf LEFT JOIN games g ON gf.game_id=g.id WHERE gf.id=?",
        (cur.lastrowid,)).fetchone()
    game_data = dict(conn.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()) if game_id else None
    conn.close()
    return jsonify({
        "type": "game_file",
        "record": dict(rec),
        "auto_created": auto_created,
        "game": game_data,
        "metadata_source": metadata.get("source") if metadata else None,
        "images_downloaded": img_results,
        "organized_path": dest_path
    }), 201


@files_bp.route("/api/files/<int:fid>/associate", methods=["PUT"])
def associate_file(fid):
    game_id = request.json.get("game_id")
    conn = get_db()
    conn.execute("UPDATE game_files SET game_id=? WHERE id=?", (game_id, fid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@files_bp.route("/api/files/<int:fid>/edit", methods=["PUT"])
def edit_file(fid):
    d = request.json
    conn = get_db()
    row = conn.execute("SELECT * FROM game_files WHERE id=?", (fid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    sets, params = [], []
    for field in ["detected_title", "platform", "content_id", "notes"]:
        if field in d:
            sets.append(f"{field}=?"); params.append(d[field])
    if sets:
        params.append(fid)
        conn.execute(f"UPDATE game_files SET {','.join(sets)} WHERE id=?", params)
    conn.commit()
    updated = conn.execute(
        "SELECT gf.*, g.title as game_title FROM game_files gf "
        "LEFT JOIN games g ON gf.game_id=g.id WHERE gf.id=?", (fid,)).fetchone()
    conn.close()
    return jsonify(dict(updated))


@files_bp.route("/api/files/<int:fid>/create-game", methods=["POST"])
def create_game_from_file(fid):
    conn = get_db()
    row = conn.execute("SELECT * FROM game_files WHERE id=?", (fid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    title = (request.json or {}).get("title") or row["detected_title"] or Path(row["filename"]).stem
    platform = (request.json or {}).get("platform") or row["platform"] or "PS3"
    content_id = row["content_id"] or ""

    existing = conn.execute(
        "SELECT id FROM games WHERE title=? OR (ps_code!='' AND ps_code LIKE ?)",
        (title, f"%{content_id[:9]}%" if content_id else "XXXXX")).fetchone()
    if existing:
        conn.execute("UPDATE game_files SET game_id=? WHERE id=?", (existing["id"], fid))
        folder = os.path.dirname(row["filepath"])
        conn.execute("UPDATE game_files SET game_id=? WHERE game_id IS NULL AND filepath LIKE ?",
                     (existing["id"], folder + "%"))
        conn.commit()
        game = conn.execute("SELECT * FROM games WHERE id=?", (existing["id"],)).fetchone()
        conn.close()
        return jsonify({"game": dict(game), "created": False, "linked": True})

    metadata = None
    from config import RAWG_API_KEY, IGDB_CLIENT_ID, IGDB_SECRET, MOBY_API_KEY
    if RAWG_API_KEY or (IGDB_CLIENT_ID and IGDB_SECRET) or MOBY_API_KEY:
        metadata = search_metadata(title, platform=platform, content_id=content_id)

    if metadata:
        game_title = metadata.get("title") or title
        cur = conn.execute("""INSERT INTO games
            (title, platform, ps_code, cover_url, banner_url, description,
             genre, developer, publisher, release_date, metacritic, rawg_id, status, metadata_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (game_title, metadata.get("platform") or platform, content_id,
             metadata.get("cover_url", ""), metadata.get("banner_url", ""),
             metadata.get("description", ""), metadata.get("genre", ""),
             metadata.get("developer", ""), metadata.get("publisher", ""),
             metadata.get("release_date", ""), metadata.get("metacritic"),
             metadata.get("rawg_id"), "Wishlist", metadata.get("source", "")))
    else:
        cur = conn.execute("INSERT INTO games (title, platform, ps_code, status) VALUES (?,?,?,?)",
                           (title, platform, content_id, "Wishlist"))
    new_gid = cur.lastrowid
    conn.execute("UPDATE game_files SET game_id=? WHERE id=?", (new_gid, fid))
    folder = os.path.dirname(row["filepath"])
    conn.execute("UPDATE game_files SET game_id=? WHERE game_id IS NULL AND filepath LIKE ?",
                 (new_gid, folder + "%"))

    game = conn.execute("SELECT * FROM games WHERE id=?", (new_gid,)).fetchone()
    if metadata and game:
        game_dir = os.path.join(GAMES_DIR, platform, safe_folder_name(game["title"]))
        img_dir = os.path.join(game_dir, "images")
        os.makedirs(img_dir, exist_ok=True)
        for img_type, url_field in [("cover", "cover_url"), ("banner", "banner_url")]:
            url = metadata.get(url_field, "")
            if not url or not url.startswith("http"): continue
            img_ext = Path(url.split("?")[0]).suffix.lower()
            if img_ext not in ALLOWED_IMAGE_EXTS: img_ext = ".jpg"
            img_fname = f"{img_type}_{new_gid}{img_ext}"
            img_path = os.path.join(img_dir, img_fname)
            if download_image_url(url, img_path):
                local_url = f"/game-images/{new_gid}/{img_fname}"
                conn.execute(f"UPDATE games SET {url_field}=? WHERE id=?", (local_url, new_gid))

    conn.commit()
    game = conn.execute("SELECT * FROM games WHERE id=?", (new_gid,)).fetchone()
    conn.close()
    return jsonify({
        "game": dict(game), "created": True,
        "metadata_source": metadata.get("source") if metadata else None
    }), 201


@files_bp.route("/api/licenses/<int:lid>/associate", methods=["PUT"])
def associate_license(lid):
    game_id = request.json.get("game_id")
    conn = get_db()
    conn.execute("UPDATE licenses SET game_id=? WHERE id=?", (game_id, lid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@files_bp.route("/api/files/<int:fid>", methods=["DELETE"])
def delete_file_record(fid):
    conn = get_db()
    row = conn.execute("SELECT * FROM game_files WHERE id=?", (fid,)).fetchone()
    if row and row["is_uploaded"] and os.path.exists(row["filepath"]):
        try: os.remove(row["filepath"])
        except: pass
    conn.execute("DELETE FROM game_files WHERE id=?", (fid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@files_bp.route("/api/licenses/<int:lid>", methods=["DELETE"])
def delete_license_record(lid):
    conn = get_db()
    row = conn.execute("SELECT * FROM licenses WHERE id=?", (lid,)).fetchone()
    if row and row["is_uploaded"] and os.path.exists(row["filepath"]):
        try: os.remove(row["filepath"])
        except: pass
    conn.execute("DELETE FROM licenses WHERE id=?", (lid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@files_bp.route("/api/files/<int:fid>/download")
def download_file(fid):
    conn = get_db()
    row = conn.execute("SELECT * FROM game_files WHERE id=?", (fid,)).fetchone()
    conn.close()
    if not row: abort(404)
    if not os.path.exists(row["filepath"]): abort(404)
    return send_file(row["filepath"], as_attachment=True, download_name=row["filename"])


@files_bp.route("/api/licenses/<int:lid>/download")
def download_license(lid):
    conn = get_db()
    row = conn.execute("SELECT * FROM licenses WHERE id=?", (lid,)).fetchone()
    conn.close()
    if not row: abort(404)
    if not os.path.exists(row["filepath"]): abort(404)
    return send_file(row["filepath"], as_attachment=True, download_name=row["filename"])


@files_bp.route("/api/files/tree")
def files_tree():
    tree = {}
    for plat in PLATFORMS:
        plat_dir = os.path.join(GAMES_DIR, plat)
        if not os.path.isdir(plat_dir): continue
        tree[plat] = {}
        for game_folder in sorted(os.listdir(plat_dir)):
            gf_path = os.path.join(plat_dir, game_folder)
            if not os.path.isdir(gf_path): continue
            info = {"files": [], "licenses": [], "images": []}
            for fname in sorted(os.listdir(gf_path)):
                fp = os.path.join(gf_path, fname)
                ext = Path(fname).suffix.lower()
                if os.path.isfile(fp):
                    if ext in ALLOWED_GAME_EXTS:
                        info["files"].append({"name": fname, "size": get_file_size_str(os.path.getsize(fp))})
                    elif ext in ALLOWED_IMAGE_EXTS:
                        info["images"].append(fname)
                elif os.path.isdir(fp):
                    sub = fname.lower()
                    if sub == "licenses":
                        for lf in sorted(os.listdir(fp)):
                            if Path(lf).suffix.lower() in ALLOWED_LICENSE_EXTS:
                                info["licenses"].append(lf)
                    elif sub in ("images", "screenshots"):
                        for img in sorted(os.listdir(fp)):
                            if Path(img).suffix.lower() in ALLOWED_IMAGE_EXTS:
                                info["images"].append(img)
            if info["files"] or info["licenses"]:
                tree[plat][game_folder] = info
    return jsonify(tree)


@files_bp.route("/api/files/browse")
def browse_game_files():
    q = request.args.get("q", "").strip().lower()
    result = []
    for plat in PLATFORMS:
        plat_dir = os.path.join(GAMES_DIR, plat)
        if not os.path.isdir(plat_dir): continue
        for game_folder in sorted(os.listdir(plat_dir)):
            gf_path = os.path.join(plat_dir, game_folder)
            if not os.path.isdir(gf_path): continue
            for fname in sorted(os.listdir(gf_path)):
                fp = os.path.join(gf_path, fname)
                ext = Path(fname).suffix.lower()
                if ext not in ALLOWED_GAME_EXTS or not os.path.isfile(fp): continue
                if q and q not in fname.lower() and q not in game_folder.lower(): continue
                result.append({
                    "filename": fname, "filepath": fp, "platform": plat,
                    "game_folder": game_folder, "type": ext.lstrip('.').upper(),
                    "size": get_file_size_str(os.path.getsize(fp))
                })
    return jsonify(result)
