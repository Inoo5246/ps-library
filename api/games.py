import os, shutil, json
from pathlib import Path
from flask import Blueprint, request, jsonify
from db import get_db
from config import GAMES_DIR, ALLOWED_IMAGE_EXTS
from services.pkg_parser import safe_folder_name, get_file_size_str
from services.metadata import download_image_url
from services.paths import get_images_dir

games_bp = Blueprint("games", __name__)


@games_bp.route("/api/games", methods=["GET"])
def get_games():
    search = request.args.get("search", "")
    status = request.args.get("status", "")
    genre  = request.args.get("genre", "")
    conn = get_db()
    q = "SELECT * FROM games WHERE 1=1"
    params = []
    if search: q += " AND title LIKE ?"; params.append(f"%{search}%")
    if status: q += " AND status = ?"; params.append(status)
    if genre:  q += " AND genre LIKE ?"; params.append(f"%{genre}%")
    q += " ORDER BY added_at DESC"
    games = conn.execute(q, params).fetchall()
    conn.close()
    return jsonify([dict(g) for g in games])


@games_bp.route("/api/games", methods=["POST"])
def add_game():
    d = request.json
    conn = get_db()
    cur = conn.execute("""INSERT INTO games
        (title,genre,platform,rating,status,cover_url,banner_url,
         description,ps_code,developer,publisher,release_date,metacritic,rawg_id,
         media_type,physical_edition,physical_condition,physical_notes,physical_barcode,
         video_links)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d["title"], d.get("genre", ""), d.get("platform", "PS5"), d.get("rating", 0),
         d.get("status", "Wishlist"), d.get("cover_url", ""), d.get("banner_url", ""),
         d.get("description", ""), d.get("ps_code", ""), d.get("developer", ""),
         d.get("publisher", ""), d.get("release_date", ""), d.get("metacritic"),
         d.get("rawg_id"), d.get("media_type", "Digital"), d.get("physical_edition", ""),
         d.get("physical_condition", ""), d.get("physical_notes", ""),
         d.get("physical_barcode", ""),
         json.dumps(d.get("video_links", []))))
    conn.commit()
    game = conn.execute("SELECT * FROM games WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(game)), 201


@games_bp.route("/api/games/<int:gid>", methods=["PUT"])
def update_game(gid):
    d = request.json
    conn = get_db()
    old_game = conn.execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
    if not old_game:
        conn.close()
        return jsonify({"error": "Game not found"}), 404

    old_title    = old_game["title"]
    old_platform = old_game["platform"]
    new_title    = d["title"]
    new_platform = d.get("platform", "PS5")
    title_changed    = safe_folder_name(new_title) != safe_folder_name(old_title)
    platform_changed = new_platform != old_platform
    files_moved = 0

    if title_changed or platform_changed:
        old_dir = os.path.join(GAMES_DIR, old_platform, safe_folder_name(old_title))
        new_dir = os.path.join(GAMES_DIR, new_platform, safe_folder_name(new_title))
        if old_dir != new_dir:
            if os.path.isdir(old_dir):
                os.makedirs(os.path.dirname(new_dir), exist_ok=True)
                if os.path.exists(new_dir):
                    for item in os.listdir(old_dir):
                        src = os.path.join(old_dir, item)
                        dst = os.path.join(new_dir, item)
                        if os.path.isdir(src) and os.path.isdir(dst):
                            for sub in os.listdir(src):
                                s2 = os.path.join(src, sub)
                                d2 = os.path.join(dst, sub)
                                if not os.path.exists(d2):
                                    shutil.move(s2, d2)
                        elif not os.path.exists(dst):
                            shutil.move(src, dst)
                    try: shutil.rmtree(old_dir)
                    except: pass
                else:
                    shutil.move(old_dir, new_dir)

                game_files = conn.execute(
                    "SELECT id, filepath FROM game_files WHERE game_id=?", (gid,)).fetchall()
                for gf in game_files:
                    if old_dir in gf["filepath"]:
                        new_fp = gf["filepath"].replace(old_dir, new_dir)
                        if os.path.exists(new_fp):
                            conn.execute("UPDATE game_files SET filepath=? WHERE id=?",
                                         (new_fp, gf["id"]))
                            files_moved += 1
                licenses = conn.execute(
                    "SELECT id, filepath FROM licenses WHERE game_id=?", (gid,)).fetchall()
                for lic in licenses:
                    if old_dir in lic["filepath"]:
                        new_fp = lic["filepath"].replace(old_dir, new_dir)
                        if os.path.exists(new_fp):
                            conn.execute("UPDATE licenses SET filepath=? WHERE id=?",
                                         (new_fp, lic["id"]))
                            files_moved += 1

                old_plat_dir = os.path.join(GAMES_DIR, old_platform)
                if os.path.isdir(old_plat_dir) and not os.listdir(old_plat_dir):
                    try: os.rmdir(old_plat_dir)
                    except: pass
            else:
                game_files = conn.execute(
                    "SELECT id, filepath FROM game_files WHERE game_id=?", (gid,)).fetchall()
                if game_files:
                    os.makedirs(new_dir, exist_ok=True)
                    os.makedirs(os.path.join(new_dir, "images"), exist_ok=True)
                    os.makedirs(os.path.join(new_dir, "licenses"), exist_ok=True)
                    for gf in game_files:
                        if os.path.exists(gf["filepath"]):
                            new_fp = os.path.join(new_dir, os.path.basename(gf["filepath"]))
                            if gf["filepath"] != new_fp:
                                shutil.move(gf["filepath"], new_fp)
                                conn.execute(
                                    "UPDATE game_files SET filepath=?, platform=? WHERE id=?",
                                    (new_fp, new_platform, gf["id"]))
                                files_moved += 1
                    licenses = conn.execute(
                        "SELECT id, filepath FROM licenses WHERE game_id=?", (gid,)).fetchall()
                    for lic in licenses:
                        if os.path.exists(lic["filepath"]):
                            new_fp = os.path.join(new_dir, "licenses", os.path.basename(lic["filepath"]))
                            if lic["filepath"] != new_fp:
                                shutil.move(lic["filepath"], new_fp)
                                conn.execute("UPDATE licenses SET filepath=? WHERE id=?",
                                             (new_fp, lic["id"]))
                                files_moved += 1

    if platform_changed:
        conn.execute("UPDATE game_files SET platform=? WHERE game_id=?", (new_platform, gid))
        from services.paths import get_images_dir, get_saves_dir, get_dlc_dir
        old_slug = safe_folder_name(old_title)
        new_slug = safe_folder_name(new_title)

        def _move_dir(base_dir, table, platform_col="platform", filepath_col="filepath"):
            old_d = os.path.join(base_dir, old_platform, old_slug)
            new_d = os.path.join(base_dir, new_platform, new_slug)
            if os.path.isdir(old_d) and old_d != new_d:
                os.makedirs(os.path.dirname(new_d), exist_ok=True)
                if not os.path.exists(new_d):
                    shutil.move(old_d, new_d)
                else:
                    for item in os.listdir(old_d):
                        src = os.path.join(old_d, item)
                        dst = os.path.join(new_d, item)
                        if not os.path.exists(dst):
                            shutil.move(src, dst)
                    try: shutil.rmtree(old_d)
                    except: pass
            if table:
                for row in conn.execute(
                        f"SELECT id, {filepath_col} FROM {table} WHERE game_id=?", (gid,)).fetchall():
                    if old_d in row[filepath_col]:
                        new_fp = row[filepath_col].replace(old_d, new_d)
                        conn.execute(
                            f"UPDATE {table} SET {filepath_col}=?, {platform_col}=? WHERE id=?",
                            (new_fp, new_platform, row["id"]))

        _move_dir(get_images_dir(), None)          # images — no DB table
        _move_dir(get_saves_dir(),  "game_saves")  # saves
        _move_dir(get_dlc_dir(),    "game_dlc")    # DLC

    conn.execute("""UPDATE games SET title=?,genre=?,platform=?,rating=?,status=?,cover_url=?,
        banner_url=?,description=?,ps_code=?,developer=?,publisher=?,release_date=?,metacritic=?,
        rawg_id=?,media_type=?,physical_edition=?,physical_condition=?,physical_notes=?,
        physical_barcode=?,video_links=? WHERE id=?""",
        (d["title"], d.get("genre", ""), d.get("platform", "PS5"), d.get("rating", 0),
         d.get("status", "Wishlist"), d.get("cover_url", ""), d.get("banner_url", ""),
         d.get("description", ""), d.get("ps_code", ""), d.get("developer", ""),
         d.get("publisher", ""), d.get("release_date", ""), d.get("metacritic"),
         d.get("rawg_id"), d.get("media_type", "Digital"), d.get("physical_edition", ""),
         d.get("physical_condition", ""), d.get("physical_notes", ""),
         d.get("physical_barcode", ""),
         json.dumps(d.get("video_links", [])), gid))
    conn.commit()
    game = conn.execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
    conn.close()
    result = dict(game)
    result["files_moved"] = files_moved
    return jsonify(result)


@games_bp.route("/api/games/<int:gid>", methods=["DELETE"])
def delete_game(gid):
    conn = get_db()
    conn.execute("DELETE FROM games WHERE id=?", (gid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@games_bp.route("/api/genres")
def get_genres():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT genre FROM games WHERE genre!='' ORDER BY genre").fetchall()
    conn.close()
    genres = set()
    for r in rows:
        for g in r["genre"].split(","):
            g = g.strip()
            if g: genres.add(g)
    return jsonify(sorted(genres))


@games_bp.route("/api/stats")
def stats():
    conn = get_db()
    games    = conn.execute("SELECT status FROM games").fetchall()
    files    = conn.execute(
        "SELECT platform, file_type, SUM(file_size) as total_size "
        "FROM game_files GROUP BY platform, file_type").fetchall()
    files_total = conn.execute("SELECT COUNT(*) as cnt FROM game_files").fetchone()
    licenses = conn.execute("SELECT COUNT(*) as cnt FROM licenses").fetchone()
    unassigned = conn.execute(
        "SELECT COUNT(*) as cnt FROM game_files WHERE game_id IS NULL").fetchone()
    conn.close()
    return jsonify({
        "total_games":      len(games),
        "played":           sum(1 for g in games if g["status"] == "Jucat"),
        "unfinished":       sum(1 for g in games if g["status"] == "Neterminat"),
        "wishlist":         sum(1 for g in games if g["status"] == "Wishlist"),
        "total_files":      files_total["cnt"],
        "total_licenses":   licenses["cnt"],
        "unassigned_files": unassigned["cnt"],
        "files_by_platform": [dict(f) for f in files],
    })


@games_bp.route("/api/games/<int:gid>/fetch-images", methods=["POST"])
def fetch_game_images(gid):
    conn = get_db()
    game = conn.execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
    if not game:
        conn.close()
        return jsonify({"error": "Game not found"}), 404
    results = {}
    plat = game["platform"] or "unknown"
    for img_type, url_field in [("cover", "cover_url"), ("banner", "banner_url")]:
        url = game[url_field]
        if not url or url.startswith("/game-images/") or url.startswith("/images/"):
            results[img_type] = "already_local"; continue
        ext = Path(url.split("?")[0]).suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTS: ext = ".jpg"
        dest_fname = f"{img_type}_{gid}{ext}"
        # Save to IMAGES_DIR/{platform}/{game_slug}/{img_type}/ (separate from game backups)
        img_dir = os.path.join(get_images_dir(), plat,
                               safe_folder_name(game["title"]), img_type)
        os.makedirs(img_dir, exist_ok=True)
        game_img_path = os.path.join(img_dir, dest_fname)
        if download_image_url(url, game_img_path):
            local_url = f"/game-images/{gid}/{dest_fname}"
            conn.execute(f"UPDATE games SET {url_field}=? WHERE id=?", (local_url, gid))
            results[img_type] = local_url
        else:
            results[img_type] = "failed"
    conn.commit()
    game = conn.execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
    conn.close()
    return jsonify({"results": results, "game": dict(game)})
