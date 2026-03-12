"""ps3netsrv process manager — start/stop/status."""
import os
import subprocess
import threading
import signal

from db import load_settings, save_settings

_process = None
_lock = threading.Lock()
_log_lines = []
_MAX_LOG = 200


def _default_config():
    return {
        "enabled": False,
        "port": 38008,
        "games_dir": "/games",
    }


def get_config():
    settings = load_settings()
    cfg = settings.get("ps3netsrv", _default_config())
    # ensure all keys exist
    d = _default_config()
    d.update(cfg)
    return d


def save_config(cfg):
    settings = load_settings()
    settings["ps3netsrv"] = cfg
    save_settings(settings)


def is_running():
    global _process
    with _lock:
        if _process is None:
            return False
        poll = _process.poll()
        if poll is not None:
            _process = None
            return False
        return True


def get_pid():
    global _process
    with _lock:
        if _process and _process.poll() is None:
            return _process.pid
    return None


def start(port=None, games_dir=None):
    """Start ps3netsrv process. Returns (ok, message)."""
    global _process, _log_lines
    with _lock:
        if _process and _process.poll() is None:
            return False, "ps3netsrv is already running"

        cfg = get_config()
        p = port or cfg["port"]
        gdir = games_dir or cfg["games_dir"]

        # Validate path safety
        if '..' in gdir or '\0' in gdir:
            return False, "Invalid path"
        if not os.path.isdir(gdir):
            return False, f"Directory does not exist: {gdir}"

        bin_path = "/usr/local/bin/ps3netsrv"
        if not os.path.isfile(bin_path):
            # fallback: check PATH
            bin_path = "ps3netsrv"

        cmd = [bin_path, gdir, str(p)]
        try:
            _log_lines = []
            _process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            # background thread to read output
            t = threading.Thread(target=_read_output, daemon=True)
            t.start()
            return True, f"ps3netsrv started on port {p}, serving {gdir}"
        except FileNotFoundError:
            return False, "ps3netsrv binary not found. Check Dockerfile."
        except Exception as e:
            return False, f"Start error: {e}"


def stop():
    """Stop ps3netsrv process. Returns (ok, message)."""
    global _process
    with _lock:
        if _process is None or _process.poll() is not None:
            _process = None
            return False, "ps3netsrv is not running"
        try:
            _process.terminate()
            _process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _process.kill()
            _process.wait(timeout=3)
        _process = None
        return True, "ps3netsrv stopped"


def restart(port=None, games_dir=None):
    """Restart ps3netsrv."""
    stop()
    return start(port, games_dir)


def get_status():
    running = is_running()
    cfg = get_config()
    return {
        "running": running,
        "pid": get_pid(),
        "port": cfg["port"],
        "games_dir": cfg["games_dir"],
        "enabled": cfg["enabled"],
        "log_lines": list(_log_lines[-50:]),
    }


def _read_output():
    """Read stdout from ps3netsrv process in background."""
    global _process, _log_lines
    proc = _process
    if not proc:
        return
    try:
        for line in proc.stdout:
            line = line.rstrip('\n')
            if line:
                _log_lines.append(line)
                if len(_log_lines) > _MAX_LOG:
                    _log_lines[:] = _log_lines[-_MAX_LOG:]
    except (ValueError, OSError):
        pass


def auto_start():
    """Called at app startup — start ps3netsrv if enabled in settings."""
    cfg = get_config()
    if cfg.get("enabled"):
        ok, msg = start(cfg["port"], cfg["games_dir"])
        print(f"[ps3netsrv] Auto-start: {msg}")
