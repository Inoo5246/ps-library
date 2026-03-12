"""Unified download client interface — qBittorrent + Transmission."""
import json, time, base64, urllib.request, urllib.parse, http.cookiejar
from db import load_settings


# ─── qBittorrent ─────────────────────────────────────────────────────────────

class QBittorrentClient:
    def __init__(self, url, username="admin", password="", category="ps-library", save_path="/downloads"):
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.category = category
        self.save_path = save_path
        self._cookie = None

    def _auth(self):
        """Authenticate and store SID cookie."""
        if self._cookie:
            return True
        try:
            data = urllib.parse.urlencode({
                "username": self.username,
                "password": self.password
            }).encode()
            req = urllib.request.Request(f"{self.url}/api/v2/auth/login", data=data, method="POST")
            cj = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            resp = opener.open(req, timeout=10)
            body = resp.read().decode()
            if body.strip().lower() == "ok.":
                self._cookie = cj
                self._opener = opener
                return True
            return False
        except Exception as e:
            print(f"[qbt] Auth error: {e}")
            return False

    def _request(self, path, data=None, method="GET"):
        """Make authenticated request to qBittorrent."""
        if not self._auth():
            return None
        url = f"{self.url}{path}"
        try:
            if data and isinstance(data, dict):
                data = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(url, data=data, method=method if data is None else "POST")
            resp = self._opener.open(req, timeout=15)
            body = resp.read().decode()
            if not body.strip():
                return True
            return json.loads(body)
        except Exception as e:
            print(f"[qbt] Request error ({path}): {e}")
            return None

    def test_connection(self):
        """Test qBittorrent connectivity. Returns (ok, message)."""
        self._cookie = None
        if not self.url:
            return False, "URL is not configured"
        if self._auth():
            ver = self._request("/api/v2/app/version")
            return True, f"Connected (v{ver})" if ver else "Connected"
        return False, "Authentication failed"

    def add_torrent(self, url_or_magnet, save_path=None, category=None):
        """Add torrent by URL/magnet. Returns (ok, message, info_hash)."""
        if not self._auth():
            return False, "Not authenticated", None
        cat = category or self.category
        path = save_path or self.save_path

        # Ensure category exists
        self._request("/api/v2/torrents/createCategory", {
            "category": cat, "savePath": path
        })

        data = urllib.parse.urlencode({
            "urls": url_or_magnet,
            "savepath": path,
            "category": cat,
        }).encode()
        try:
            req = urllib.request.Request(
                f"{self.url}/api/v2/torrents/add", data=data, method="POST")
            resp = self._opener.open(req, timeout=15)
            body = resp.read().decode()
            if "ok" in body.lower() or resp.status == 200:
                # Get hash from recently added torrents
                time.sleep(1)
                torrents = self.get_all(cat)
                if torrents:
                    # Return the most recent one
                    latest = max(torrents, key=lambda t: t.get("added_on", 0))
                    return True, "Added", latest.get("hash", "")
                return True, "Added", ""
            return False, f"Error: {body}", None
        except Exception as e:
            return False, f"Error: {e}", None

    def get_torrent(self, info_hash):
        """Get torrent status by hash."""
        data = self._request(f"/api/v2/torrents/info?hashes={info_hash}")
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        t = data[0]
        state = t.get("state", "")
        # Map qBt states to our statuses
        if state in ("uploading", "pausedUP", "stalledUP", "forcedUP", "queuedUP", "checkingUP"):
            status = "completed"
        elif state in ("downloading", "stalledDL", "forcedDL", "queuedDL", "checkingDL", "metaDL", "allocating"):
            status = "downloading"
        elif state in ("pausedDL",):
            status = "paused"
        elif state in ("error", "missingFiles"):
            status = "failed"
        else:
            status = "downloading"
        return {
            "progress": round(t.get("progress", 0) * 100, 1),
            "status": status,
            "download_speed": t.get("dlspeed", 0),
            "size": t.get("total_size", 0) or t.get("size", 0),
            "save_path": t.get("content_path", "") or t.get("save_path", ""),
            "name": t.get("name", ""),
            "hash": t.get("hash", ""),
            "seeders": t.get("num_seeds", 0),
            "leechers": t.get("num_leechs", 0),
            "added_on": t.get("added_on", 0),
        }

    def get_all(self, category=None):
        """Get all torrents, optionally filtered by category."""
        cat = category or self.category
        data = self._request(f"/api/v2/torrents/info?category={urllib.parse.quote(cat)}")
        if not data or not isinstance(data, list):
            return []
        return data

    def remove(self, info_hash, delete_files=False):
        """Remove a torrent."""
        data = {"hashes": info_hash, "deleteFiles": "true" if delete_files else "false"}
        result = self._request("/api/v2/torrents/delete", data)
        return (True, "Deleted") if result is not None else (False, "Error deleting")

    def pause(self, info_hash):
        self._request("/api/v2/torrents/pause", {"hashes": info_hash})

    def resume(self, info_hash):
        self._request("/api/v2/torrents/resume", {"hashes": info_hash})


# ─── Transmission ────────────────────────────────────────────────────────────

class TransmissionClient:
    def __init__(self, url, username="", password="", save_path="/downloads"):
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.save_path = save_path
        self._session_id = ""

    def _rpc(self, method, arguments=None):
        """Make Transmission JSON-RPC call with 409 retry."""
        rpc_url = f"{self.url}/transmission/rpc"
        payload = json.dumps({"method": method, "arguments": arguments or {}}).encode()

        for attempt in range(2):
            try:
                req = urllib.request.Request(rpc_url, data=payload, method="POST")
                req.add_header("Content-Type", "application/json")
                if self._session_id:
                    req.add_header("X-Transmission-Session-Id", self._session_id)
                if self.username:
                    creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                    req.add_header("Authorization", f"Basic {creds}")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 409:
                    self._session_id = e.headers.get("X-Transmission-Session-Id", "")
                    continue
                raise
        return None

    def test_connection(self):
        """Test Transmission connectivity."""
        if not self.url:
            return False, "URL is not configured"
        try:
            result = self._rpc("session-get", {"fields": ["version"]})
            if result and result.get("result") == "success":
                ver = result.get("arguments", {}).get("version", "")
                return True, f"Connected (v{ver})" if ver else "Connected"
            return False, "Connection error"
        except Exception as e:
            return False, f"Error: {e}"

    @staticmethod
    def _resolve_download_url(url):
        """Resolve Prowlarr download URL — may redirect to magnet or .torrent file.
        Returns (type, data) where type is 'magnet', 'torrent_bytes', or 'error'.
        """
        import urllib.error
        try:
            # Build request with Prowlarr auth if needed
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "ps-library/1.0")
            from db import load_settings
            s = load_settings()
            prowlarr_cfg = s.get("prowlarr", {})
            prowlarr_url = (prowlarr_cfg.get("url") or "").rstrip("/")
            if prowlarr_url and url.startswith(prowlarr_url):
                api_key = prowlarr_cfg.get("api_key", "")
                if api_key:
                    req.add_header("X-Api-Key", api_key)

            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if len(data) < 100:
                    return "error", f"Torrent file too small ({len(data)} bytes)"
                return "torrent_bytes", data

        except urllib.error.HTTPError as e:
            # Catch 301/302 redirects — urllib refuses magnet: scheme redirects
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get("Location", "")
                if location.startswith("magnet:"):
                    print(f"[transmission] Prowlarr redirected to magnet link")
                    return "magnet", location
                # Regular HTTP redirect — follow manually
                if location.startswith("http"):
                    try:
                        req2 = urllib.request.Request(location, method="GET")
                        req2.add_header("User-Agent", "ps-library/1.0")
                        with urllib.request.urlopen(req2, timeout=30) as resp:
                            data = resp.read()
                            if len(data) < 100:
                                return "error", f"Torrent file too small ({len(data)} bytes)"
                            return "torrent_bytes", data
                    except Exception as e2:
                        return "error", f"Redirect fetch failed: {e2}"
                return "error", f"Redirect to unknown URL: {location}"
            return "error", f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            print(f"[transmission] Resolve URL error: {e}")
            return "error", str(e)

    def add_torrent(self, url_or_magnet, save_path=None, category=None):
        """Add torrent. Returns (ok, message, client_id).
        Resolves Prowlarr URLs (which may redirect to magnets or .torrent files).
        """
        args = {}
        if save_path or self.save_path:
            args["download-dir"] = save_path or self.save_path

        if url_or_magnet.startswith("magnet:"):
            args["filename"] = url_or_magnet
        else:
            # Resolve Prowlarr download URL
            rtype, rdata = self._resolve_download_url(url_or_magnet)
            if rtype == "magnet":
                args["filename"] = rdata
            elif rtype == "torrent_bytes":
                args["metainfo"] = base64.b64encode(rdata).decode()
            else:
                return False, f"Could not download the torrent: {rdata}", None

        try:
            result = self._rpc("torrent-add", args)
            if not result or result.get("result") != "success":
                return False, f"Error: {result}", None
            ta = result.get("arguments", {})
            torrent = ta.get("torrent-added") or ta.get("torrent-duplicate")
            if torrent:
                return True, "Added", str(torrent.get("id", ""))
            return True, "Added", ""
        except Exception as e:
            return False, f"Error: {e}", None

    def get_torrent(self, client_id):
        """Get torrent status by ID."""
        try:
            tid = int(client_id)
        except (ValueError, TypeError):
            return None
        result = self._rpc("torrent-get", {
            "ids": [tid],
            "fields": ["percentDone", "status", "rateDownload", "totalSize",
                       "downloadDir", "name", "hashString", "id",
                       "peersGettingFromUs", "peersSendingToUs"]
        })
        if not result or result.get("result") != "success":
            return None
        torrents = result.get("arguments", {}).get("torrents", [])
        if not torrents:
            return None
        t = torrents[0]
        # Transmission status codes: 0=stopped, 4=downloading, 6=seeding
        st = t.get("status", 0)
        if st == 6:
            status = "completed"
        elif st == 4:
            status = "downloading"
        elif st == 0:
            status = "paused"
        else:
            status = "downloading"
        return {
            "progress": round(t.get("percentDone", 0) * 100, 1),
            "status": status,
            "download_speed": t.get("rateDownload", 0),
            "size": t.get("totalSize", 0),
            "save_path": t.get("downloadDir", ""),
            "name": t.get("name", ""),
            "hash": t.get("hashString", ""),
            "seeders": t.get("peersSendingToUs", 0),
            "leechers": t.get("peersGettingFromUs", 0),
        }

    def get_all(self, category=None):
        """Get all torrents."""
        result = self._rpc("torrent-get", {
            "fields": ["id", "name", "percentDone", "status", "rateDownload",
                       "totalSize", "downloadDir", "hashString"]
        })
        if not result or result.get("result") != "success":
            return []
        return result.get("arguments", {}).get("torrents", [])

    def remove(self, client_id, delete_files=False):
        try:
            tid = int(client_id)
            result = self._rpc("torrent-remove", {
                "ids": [tid], "delete-local-data": delete_files
            })
            if result and result.get("result") == "success":
                return True, "Deleted"
            return False, "Error"
        except Exception as e:
            return False, f"Error: {e}"

    def pause(self, client_id):
        try:
            self._rpc("torrent-stop", {"ids": [int(client_id)]})
        except: pass

    def resume(self, client_id):
        try:
            self._rpc("torrent-start", {"ids": [int(client_id)]})
        except: pass


# ─── Factory / Config ────────────────────────────────────────────────────────

def get_client_config():
    """Get download clients config from settings."""
    s = load_settings()
    return s.get("download_clients", {})


def get_client(name=None):
    """Get a client instance by name (or default)."""
    cfg = get_client_config()
    name = name or cfg.get("default_client", "qbittorrent")
    if name == "qbittorrent":
        c = cfg.get("qbittorrent", {})
        return QBittorrentClient(
            url=c.get("url", ""), username=c.get("username", "admin"),
            password=c.get("password", ""), category=c.get("category", "ps-library"),
            save_path=c.get("save_path", "/downloads"))
    elif name == "transmission":
        c = cfg.get("transmission", {})
        return TransmissionClient(
            url=c.get("url", ""), username=c.get("username", ""),
            password=c.get("password", ""), save_path=c.get("save_path", "/downloads"))
    return None


def test_client(name):
    """Test a download client connection. Returns (ok, message)."""
    client = get_client(name)
    if not client:
        return False, f"Client '{name}' unknown"
    return client.test_connection()
