"""Prowlarr API client for PS Library — searches indexers for game releases."""
import json, time, urllib.request, urllib.parse
from db import load_settings
from config import PROWLARR_URL, PROWLARR_KEY

# ─── PlayStation title filtering ──────────────────────────────────────────────
import re
# Keywords that indicate a PlayStation release in the title
_PS_TITLE_RE = re.compile(
    r'\b(PS[1-5]|PSX|PSP|PS Vita|PlayStation|CUSA\d|PPSA\d|BCUS\d|BLUS\d|BLES\d|BCES\d|NPUB\d|NPEB\d)\b',
    re.IGNORECASE
)
# Categories that are definitely NOT games (movies, music, TV, books, etc.)
_NON_GAME_CATS = {2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060, 2070,  # Movies
                  3000, 3010, 3020, 3030, 3040, 3050, 3060,              # Audio/Music
                  5000, 5010, 5020, 5030, 5040, 5050, 5060, 5070,        # TV
                  6000, 7000, 7010, 7020, 7030, 8000, 8010}              # Books/Other

# ─── In-memory cache (15min TTL) ────────────────────────────────────────────
_cache: dict = {}
_CACHE_TTL = 900  # 15 minutes


def _get_cached(key):
    entry = _cache.get(key)
    if entry:
        result, expires = entry
        if time.time() < expires:
            return result
        del _cache[key]
    return None


def _set_cached(key, result):
    _cache[key] = (result, time.time() + _CACHE_TTL)


def cache_clear():
    _cache.clear()


# ─── Config helpers ──────────────────────────────────────────────────────────

def get_config():
    """Get Prowlarr config from settings.json, fallback to env vars."""
    s = load_settings()
    cfg = s.get("prowlarr", {})
    return {
        "url": (cfg.get("url") or PROWLARR_URL or "").rstrip("/"),
        "api_key": cfg.get("api_key") or PROWLARR_KEY or ""
    }


def _api_request(path, params=None):
    """Make an authenticated request to Prowlarr API."""
    cfg = get_config()
    if not cfg["url"] or not cfg["api_key"]:
        return None
    url = f"{cfg['url']}/api/v1/{path}"
    if params:
        url += f"?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={
            "X-Api-Key": cfg["api_key"],
            "User-Agent": "PSLibrary/3.0"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[prowlarr] API error ({path}): {e}")
        return None


# ─── Public API ──────────────────────────────────────────────────────────────

def test_connection():
    """Test Prowlarr connectivity. Returns (ok, message)."""
    cfg = get_config()
    if not cfg["url"]:
        return False, "Prowlarr URL is not configured"
    if not cfg["api_key"]:
        return False, "API Key is not configured"
    try:
        url = f"{cfg['url']}/api/v1/health"
        req = urllib.request.Request(url, headers={
            "X-Api-Key": cfg["api_key"],
            "User-Agent": "PSLibrary/3.0"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            json.loads(resp.read().decode())
            return True, "Connected"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Invalid API Key"
        return False, f"HTTP error {e.code}"
    except Exception as e:
        return False, f"Connection error: {e}"


def get_indexers():
    """List configured indexers from Prowlarr."""
    data = _api_request("indexer")
    if data is None:
        return []
    return [{
        "id": idx.get("id"),
        "name": idx.get("name", ""),
        "protocol": idx.get("protocol", ""),
        "enabled": idx.get("enable", False),
        "privacy": idx.get("privacy", "")
    } for idx in data if idx.get("enable")]


def search(query):
    """Search all indexers via Prowlarr. Returns normalized results."""
    if not query:
        return []
    cache_key = f"search:{query.lower()}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    params = {"query": query, "type": "search"}

    data = _api_request("search", params)
    if not data:
        _set_cached(cache_key, [])
        return []

    results = []
    for item in data:
        size = item.get("size", 0) or 0
        # Skip very small results (< 50MB, probably not a game)
        if size > 0 and size < 50 * 1024 * 1024:
            continue
        item_cats = item.get("categories", [])
        cat_names = [c.get("name", "") for c in item_cats]
        cat_ids = [c.get("id", 0) for c in item_cats]
        results.append({
            "title": item.get("title", ""),
            "size": size,
            "indexer": item.get("indexer", {}).get("name", "") if isinstance(item.get("indexer"), dict) else item.get("indexer", ""),
            "download_url": item.get("downloadUrl", ""),
            "info_url": item.get("infoUrl", ""),
            "guid": item.get("guid", ""),
            "seeders": item.get("seeders", 0) or 0,
            "leechers": item.get("leechers", 0) or 0,
            "protocol": item.get("protocol", "torrent"),
            "age": item.get("age", 0) or 0,
            "categories": cat_names,
            "category_ids": cat_ids,
            "indexer_id": item.get("indexerId", 0),
        })

    # Sort by seeders descending
    results.sort(key=lambda x: x["seeders"], reverse=True)
    _set_cached(cache_key, results)
    return results


def _is_ps_release(title, category_ids):
    """Check if a release is likely a PlayStation game based on title and categories."""
    # Exclude if categories are clearly non-game (movies, music, TV, books)
    if category_ids and any(cid in _NON_GAME_CATS for cid in category_ids):
        return False
    # Accept if title contains PS keywords
    if _PS_TITLE_RE.search(title):
        return True
    # Accept if in console category (1000-1199) — likely a game
    if category_ids and any(1000 <= cid < 1200 for cid in category_ids):
        return True
    return False


def _filter_by_platform(results, platform):
    """Filter results to a specific platform by title keywords."""
    if not platform:
        return results
    kw = platform.upper()  # e.g. "PS5", "PS4", "PS3"
    return [r for r in results if kw in r["title"].upper()]


def search_for_game(title, platform=None, ps_only=True):
    """Smart search for a game — filters to PlayStation releases by default."""
    if not title:
        return []

    # Search with platform qualifier first for better results
    if platform:
        results = search(f"{title} {platform}")
        if ps_only:
            results = [r for r in results if _is_ps_release(r["title"], r.get("category_ids", []))]
            results = _filter_by_platform(results, platform)
        if results:
            return results

    # Fallback to title only
    results = search(title)
    if ps_only:
        results = [r for r in results if _is_ps_release(r["title"], r.get("category_ids", []))]
        if platform:
            results = _filter_by_platform(results, platform)
    return results
