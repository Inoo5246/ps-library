import os
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename

from db import get_db
from config import GAMES_DIR, ALLOWED_IMAGE_EXTS, PLATFORMS
from services.pkg_parser import safe_folder_name, get_file_size_str
from services.paths import get_images_dir

images_bp = Blueprint("images", __name__)

IMG_TYPES = ("cover", "banner", "screenshot", "other")


def _game_img_dir(platform, title, img_type):
    """Structure: {images_dir}/{platform}/{game_slug}/{img_type}/"""
    return os.path.join(get_images_dir(), platform or "unknown",
                        safe_folder_name(title), img_type)


def _find_game_image(platform, title, filename):
    """Search for file in the new structure, then in the old one (GAMES_DIR)."""
    fname_safe = secure_filename(filename)
    for t in IMG_TYPES:
        p = os.path.join(_game_img_dir(platform, title, t), fname_safe)
        if os.path.exists(p):
            return p
    old = os.path.join(GAMES_DIR, platform or "", safe_folder_name(title),
                       "images", fname_safe)
    if os.path.exists(old):
        return old
    return None


# ─── Upload ───────────────────────────────────────────────────────────────────

@images_bp.route("/api/images/upload", methods=["POST"])
def upload_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    f        = request.files['file']
    img_type = request.form.get("type", "cover")
    if img_type not in IMG_TYPES:
        img_type = "other"
    game_id  = request.form.get("game_id", "")
    fname    = secure_filename(f.filename)
    ext      = Path(fname).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        return jsonify({"error": f"Type not allowed: {ext}"}), 400

    if game_id:
        conn = get_db()
        game = conn.execute("SELECT id, platform, title FROM games WHERE id=?",
                            (int(game_id),)).fetchone()
        conn.close()
        if game:
            plat       = game["platform"] or "unknown"
            dest_dir   = _game_img_dir(plat, game["title"], img_type)
            os.makedirs(dest_dir, exist_ok=True)
            dest_fname = f"{img_type}_{game_id}{ext}"
            dest_path  = os.path.join(dest_dir, dest_fname)
            f.save(dest_path)
            url = f"/game-images/{game_id}/{dest_fname}"
            field = "cover_url" if img_type == "cover" else \
                    "banner_url" if img_type == "banner" else None
            if field:
                conn = get_db()
                conn.execute(f"UPDATE games SET {field}=? WHERE id=?",
                             (url, int(game_id)))
                conn.commit()
                conn.close()
            return jsonify({"url": url, "filename": dest_fname}), 201

    # No game_id — general folder
    dest_dir = os.path.join(get_images_dir(), "_general", img_type)
    os.makedirs(dest_dir, exist_ok=True)
    dest_fname = fname
    dest_path  = os.path.join(dest_dir, dest_fname)
    if os.path.exists(dest_path):
        dest_fname = Path(fname).stem + "_1" + ext
        dest_path  = os.path.join(dest_dir, dest_fname)
    f.save(dest_path)
    return jsonify({"url": f"/images/{img_type}/{dest_fname}",
                    "filename": dest_fname}), 201


# ─── Serve ────────────────────────────────────────────────────────────────────

@images_bp.route("/game-images/<int:gid>/<filename>")
def serve_game_image(gid, filename):
    conn = get_db()
    game = conn.execute("SELECT platform, title FROM games WHERE id=?", (gid,)).fetchone()
    conn.close()
    if not game: abort(404)
    p = _find_game_image(game["platform"], game["title"], filename)
    if p:
        return send_file(p)
    abort(404)


@images_bp.route("/images/<img_type>/<filename>")
def serve_image(img_type, filename):
    fname_safe = secure_filename(filename)
    images_dir = get_images_dir()
    # General (new)
    p = os.path.join(images_dir, "_general", secure_filename(img_type), fname_safe)
    if os.path.exists(p):
        return send_file(p)
    # Legacy flat
    p2 = os.path.join(images_dir, secure_filename(img_type), fname_safe)
    if os.path.exists(p2):
        return send_file(p2)
    # Fallback: search in any images/ within GAMES_DIR
    for root, _dirs, files in os.walk(GAMES_DIR):
        if os.path.basename(root) == "images" and fname_safe in files:
            return send_file(os.path.join(root, fname_safe))
    abort(404)


# ─── List ─────────────────────────────────────────────────────────────────────

@images_bp.route("/api/images", methods=["GET"])
def list_images():
    filter_game_id = request.args.get("game_id")
    filter_type    = request.args.get("type")
    result    = []
    images_dir = get_images_dir()

    # Resolve game slug for filtering
    game_slug_filter = None
    game_plat_filter = None
    if filter_game_id:
        conn = get_db()
        game = conn.execute("SELECT platform, title FROM games WHERE id=?",
                            (int(filter_game_id),)).fetchone()
        conn.close()
        if game:
            game_slug_filter = safe_folder_name(game["title"])
            game_plat_filter = game["platform"] or "unknown"

    # New structure
    if os.path.isdir(images_dir):
        for plat in sorted(os.listdir(images_dir)):
            if plat.startswith("_"): continue
            if game_plat_filter and plat != game_plat_filter: continue
            plat_dir = os.path.join(images_dir, plat)
            if not os.path.isdir(plat_dir): continue
            for game_slug in sorted(os.listdir(plat_dir)):
                if game_slug_filter and game_slug != game_slug_filter: continue
                game_dir = os.path.join(plat_dir, game_slug)
                if not os.path.isdir(game_dir): continue
                for img_type in IMG_TYPES:
                    if filter_type and img_type != filter_type: continue
                    tdir = os.path.join(game_dir, img_type)
                    if not os.path.isdir(tdir): continue
                    for fname in sorted(os.listdir(tdir)):
                        if Path(fname).suffix.lower() not in ALLOWED_IMAGE_EXTS: continue
                        fpath = os.path.join(tdir, fname)
                        result.append({
                            "type": img_type, "filename": fname,
                            "url": f"/game-image-browse/{plat}/{game_slug}/{img_type}/{fname}",
                            "game_path": f"{plat}/{game_slug}",
                            "size": get_file_size_str(os.path.getsize(fpath))
                        })

    # Legacy GAMES_DIR (skip if filtering by game_id)
    if not filter_game_id:
        for root, _dirs, files in os.walk(GAMES_DIR):
            if os.path.basename(root) != "images": continue
            for fname in sorted(files):
                if Path(fname).suffix.lower() not in ALLOWED_IMAGE_EXTS: continue
                if filter_type:
                    ft = next((t for t in IMG_TYPES if fname.startswith(t)), "other")
                    if ft != filter_type: continue
                if any(r["filename"] == fname for r in result): continue
                fpath = os.path.join(root, fname)
                img_type = next((t for t in IMG_TYPES if fname.startswith(t)), "other")
                result.append({
                    "type": img_type, "filename": fname,
                    "url": f"/images/{img_type}/{fname}",
                    "game_path": "(legacy)",
                    "size": get_file_size_str(os.path.getsize(fpath))
                })
    return jsonify(result)


@images_bp.route("/api/images/<img_type>/<filename>", methods=["DELETE"])
def delete_image(img_type, filename):
    fname_safe = secure_filename(filename)
    images_dir = get_images_dir()
    if os.path.isdir(images_dir):
        for plat in os.listdir(images_dir):
            plat_dir = os.path.join(images_dir, plat)
            if not os.path.isdir(plat_dir): continue
            for gs in os.listdir(plat_dir):
                p = os.path.join(plat_dir, gs, img_type, fname_safe)
                if os.path.exists(p):
                    os.remove(p)
                    return jsonify({"ok": True})
    for root, _dirs, files in os.walk(GAMES_DIR):
        if os.path.basename(root) == "images" and fname_safe in files:
            os.remove(os.path.join(root, fname_safe))
            return jsonify({"ok": True})
    return jsonify({"ok": True})


# ─── Browse ───────────────────────────────────────────────────────────────────

@images_bp.route("/api/images/browse")
def browse_images():
    q          = request.args.get("q", "").strip().lower()
    result     = []
    images_dir = get_images_dir()

    if os.path.isdir(images_dir):
        for plat in sorted(os.listdir(images_dir)):
            if plat.startswith("_"): continue
            plat_dir = os.path.join(images_dir, plat)
            if not os.path.isdir(plat_dir): continue
            for game_slug in sorted(os.listdir(plat_dir)):
                game_dir = os.path.join(plat_dir, game_slug)
                if not os.path.isdir(game_dir): continue
                for img_type in IMG_TYPES:
                    tdir = os.path.join(game_dir, img_type)
                    if not os.path.isdir(tdir): continue
                    for fname in sorted(os.listdir(tdir)):
                        if Path(fname).suffix.lower() not in ALLOWED_IMAGE_EXTS: continue
                        if q and q not in fname.lower() and q not in game_slug.lower(): continue
                        result.append({
                            "filename": fname,
                            "url": f"/game-image-browse/{plat}/{game_slug}/{img_type}/{fname}",
                            "type": img_type,
                            "source": f"{plat}/{game_slug}",
                            "size": get_file_size_str(
                                os.path.getsize(os.path.join(tdir, fname)))
                        })

    for plat in PLATFORMS:
        plat_dir = os.path.join(GAMES_DIR, plat)
        if not os.path.isdir(plat_dir): continue
        for gf in sorted(os.listdir(plat_dir)):
            gf_path = os.path.join(plat_dir, gf)
            if not os.path.isdir(gf_path): continue
            for sub in ("images", "screenshots"):
                img_dir = os.path.join(gf_path, sub)
                if not os.path.isdir(img_dir): continue
                for fname in sorted(os.listdir(img_dir)):
                    if Path(fname).suffix.lower() not in ALLOWED_IMAGE_EXTS: continue
                    if q and q not in fname.lower() and q not in gf.lower(): continue
                    result.append({
                        "filename": fname,
                        "url": f"/api/game-image/{plat}/{gf}/{sub}/{fname}",
                        "type": sub, "source": f"{plat}/{gf} (legacy)",
                        "size": get_file_size_str(
                            os.path.getsize(os.path.join(img_dir, fname)))
                    })
    return jsonify(result)


@images_bp.route("/game-image-browse/<path:rel_path>")
def browse_game_image_new(rel_path):
    images_dir = get_images_dir()
    safe_path  = os.path.normpath(os.path.join(images_dir, rel_path))
    if not safe_path.startswith(os.path.normpath(images_dir)): abort(403)
    if not os.path.exists(safe_path): abort(404)
    if Path(safe_path).suffix.lower() not in ALLOWED_IMAGE_EXTS: abort(400)
    return send_file(safe_path)


@images_bp.route("/api/game-image/<path:rel_path>")
def browse_game_image(rel_path):
    safe_path = os.path.normpath(os.path.join(GAMES_DIR, rel_path))
    if not safe_path.startswith(os.path.normpath(GAMES_DIR)): abort(403)
    if not os.path.exists(safe_path): abort(404)
    if Path(safe_path).suffix.lower() not in ALLOWED_IMAGE_EXTS: abort(400)
    return send_file(safe_path)
