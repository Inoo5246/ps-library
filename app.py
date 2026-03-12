"""PS Library v3 - Flask application factory."""
import os, json
from pathlib import Path
from flask import Flask, render_template, jsonify

from db import init_db, get_db
from config import ALLOWED_IMAGE_EXTS, MAX_UPLOAD_MB
from services.pkg_parser import safe_folder_name
from services.paths import get_images_dir
from api.games import games_bp
from api.files import files_bp
from api.images import images_bp
from api.settings_api import settings_bp
from api.metadata_api import metadata_bp
from api.redump_api import redump_bp
from api.saves_api import saves_bp
from api.dlc_api import dlc_bp
from api.ps3netsrv_api import ps3netsrv_bp
from api.downloads_api import downloads_bp
from services.scanner import start_scheduler
from services.ps3netsrv import auto_start as ps3netsrv_auto_start
from services.download_monitor import start_monitor as start_dl_monitor


def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.errorhandler(404)
    def handle_404(e):
        from flask import request
        if request.path.startswith('/api/'):
            return jsonify({"error": "Not found"}), 404
        return render_template("library.html", page="library"), 404

    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(413)
    def handle_413(e):
        return jsonify({"error": f"File exceeds the {MAX_UPLOAD_MB} MB limit"}), 413

    app.register_blueprint(games_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(images_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(metadata_bp)
    app.register_blueprint(redump_bp)
    app.register_blueprint(saves_bp)
    app.register_blueprint(dlc_bp)
    app.register_blueprint(ps3netsrv_bp)
    app.register_blueprint(downloads_bp)

    @app.route("/")
    def library():
        return render_template("library.html", page="library")

    @app.route("/fisiere")
    def files_page():
        return render_template("files.html", page="files")

    @app.route("/setari")
    def settings_page():
        return render_template("settings.html", page="settings")

    @app.route("/descarcari")
    def downloads_page():
        return render_template("downloads.html", page="downloads")

    @app.route("/joc/<int:gid>")
    def game_detail_page(gid):
        conn = get_db()
        game = conn.execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
        if not game:
            conn.close()
            return render_template("library.html", page="library"), 404
        files    = conn.execute(
            "SELECT * FROM game_files WHERE game_id=? ORDER BY added_at DESC", (gid,)).fetchall()
        licenses = conn.execute(
            "SELECT * FROM licenses WHERE game_id=? ORDER BY id DESC", (gid,)).fetchall()
        saves    = conn.execute(
            "SELECT * FROM game_saves WHERE game_id=? ORDER BY added_at DESC", (gid,)).fetchall()
        dlcs     = conn.execute(
            "SELECT * FROM game_dlc WHERE game_id=? ORDER BY added_at DESC", (gid,)).fetchall()
        conn.close()

        game_dict = dict(game)

        # Parse video_links JSON
        video_links = []
        try:
            video_links = json.loads(game_dict.get("video_links") or "[]")
        except Exception:
            pass

        # Gather gallery images (screenshot + other)
        gallery = []
        images_dir = get_images_dir()
        plat = game_dict.get("platform") or "unknown"
        slug = safe_folder_name(game_dict["title"])
        for img_type in ("screenshot", "other"):
            tdir = os.path.join(images_dir, plat, slug, img_type)
            if os.path.isdir(tdir):
                for fname in sorted(os.listdir(tdir)):
                    if Path(fname).suffix.lower() in ALLOWED_IMAGE_EXTS:
                        gallery.append({
                            "type": img_type,
                            "filename": fname,
                            "url": f"/game-image-browse/{plat}/{slug}/{img_type}/{fname}"
                        })

        return render_template("game_detail.html", page="library",
                               game=game_dict,
                               files=[dict(f) for f in files],
                               licenses=[dict(l) for l in licenses],
                               saves=[dict(s) for s in saves],
                               dlcs=[dict(d) for d in dlcs],
                               video_links=video_links,
                               gallery=gallery)

    return app


if __name__ == "__main__":
    init_db()
    start_scheduler()
    ps3netsrv_auto_start()
    start_dl_monitor()
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
else:
    # When run via gunicorn / waitress
    init_db()
    start_scheduler()
    ps3netsrv_auto_start()
    start_dl_monitor()
    app = create_app()
