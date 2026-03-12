"""Redump.org API Blueprint — DAT import and disc image identification."""
import os, tempfile
from flask import Blueprint, jsonify, request

from db import get_db
from services.redump import import_dat, identify_file

redump_bp = Blueprint("redump", __name__)

# Disc file types that can be verified with Redump
_REDUMP_TYPES = {"BIN", "ISO", "IMG"}


# ─── DAT management ───────────────────────────────────────────────────────────

@redump_bp.route("/api/redump/dats")
def list_dats():
    """Returns the list of imported DATs."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, platform, filename, game_count, imported_at "
        "FROM redump_dats ORDER BY imported_at DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@redump_bp.route("/api/redump/import-dat", methods=["POST"])
def import_dat_route():
    """Receives a .dat file (Redump XML) and imports it into the local DB."""
    if "file" not in request.files:
        return jsonify({"error": "No file sent"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".dat"):
        return jsonify({"error": "Only .dat files are accepted"}), 400

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".dat")
    try:
        os.close(tmp_fd)
        f.save(tmp_path)
        result = import_dat(tmp_path)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@redump_bp.route("/api/redump/dats/<int:dat_id>", methods=["DELETE"])
def delete_dat(dat_id):
    """Deletes an imported DAT and all associated entries."""
    conn = get_db()
    conn.execute("DELETE FROM redump_entries WHERE dat_id=?", (dat_id,))
    conn.execute("DELETE FROM redump_dats WHERE id=?",        (dat_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ─── File identification ───────────────────────────────────────────────────────

@redump_bp.route("/api/redump/identify/<int:file_id>", methods=["POST"])
def identify_game_file(file_id):
    """Computes the hash of a disc file and looks it up in the Redump DB.

    Returns {"md5", "crc32", "match": {...} | null}.
    If a match is found, saves md5_hash and (optionally) the detected title.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT filepath, file_type, detected_title FROM game_files WHERE id=?",
        (file_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "File not found in DB"}), 404
    if not os.path.isfile(row["filepath"]):
        return jsonify({"error": "File not found on disk"}), 404
    if row["file_type"] not in _REDUMP_TYPES:
        return jsonify({
            "error": f"Type {row['file_type']} cannot be verified with Redump "
                     f"(only {', '.join(sorted(_REDUMP_TYPES))})"
        }), 400

    result = identify_file(row["filepath"])
    if "error" in result:
        return jsonify(result), 500

    # Save the hash and (if match) the detected title
    if result.get("md5"):
        conn = get_db()
        conn.execute("UPDATE game_files SET md5_hash=? WHERE id=?",
                     (result["md5"], file_id))
        match = result.get("match")
        if match and match.get("game_name") and not row["detected_title"]:
            conn.execute("UPDATE game_files SET detected_title=? WHERE id=?",
                         (match["game_name"], file_id))
        conn.commit()
        conn.close()

    return jsonify(result)


@redump_bp.route("/api/redump/stats")
def redump_stats():
    """How many entries are imported in total."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM redump_entries").fetchone()[0]
    dats  = conn.execute("SELECT COUNT(*) FROM redump_dats").fetchone()[0]
    conn.close()
    return jsonify({"total_entries": total, "total_dats": dats})
