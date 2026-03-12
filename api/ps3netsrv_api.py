"""API endpoints for ps3netsrv management."""
from flask import Blueprint, request, jsonify
from services.ps3netsrv import (
    get_status, get_config, save_config,
    start, stop, restart,
)

ps3netsrv_bp = Blueprint("ps3netsrv", __name__)


@ps3netsrv_bp.route("/api/ps3netsrv/status")
def status():
    return jsonify(get_status())


@ps3netsrv_bp.route("/api/ps3netsrv/config", methods=["GET"])
def config_get():
    return jsonify(get_config())


@ps3netsrv_bp.route("/api/ps3netsrv/config", methods=["PUT"])
def config_put():
    data = request.json
    cfg = get_config()
    if "port" in data:
        p = int(data["port"])
        if p < 1 or p > 65535:
            return jsonify({"error": "Invalid port (1-65535)"}), 400
        cfg["port"] = p
    if "games_dir" in data:
        cfg["games_dir"] = data["games_dir"]
    if "enabled" in data:
        cfg["enabled"] = bool(data["enabled"])
    save_config(cfg)
    return jsonify({"ok": True, "config": cfg})


@ps3netsrv_bp.route("/api/ps3netsrv/start", methods=["POST"])
def do_start():
    cfg = get_config()
    ok, msg = start(cfg["port"], cfg["games_dir"])
    return jsonify({"ok": ok, "message": msg, "status": get_status()})


@ps3netsrv_bp.route("/api/ps3netsrv/stop", methods=["POST"])
def do_stop():
    ok, msg = stop()
    return jsonify({"ok": ok, "message": msg, "status": get_status()})


@ps3netsrv_bp.route("/api/ps3netsrv/restart", methods=["POST"])
def do_restart():
    cfg = get_config()
    ok, msg = restart(cfg["port"], cfg["games_dir"])
    return jsonify({"ok": ok, "message": msg, "status": get_status()})


@ps3netsrv_bp.route("/api/ps3netsrv/logs")
def logs():
    st = get_status()
    return jsonify({"lines": st["log_lines"]})
