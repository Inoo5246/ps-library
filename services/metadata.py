import os, re, json, time, urllib.request, urllib.parse
from config import (RAWG_API_KEY, IGDB_CLIENT_ID, IGDB_SECRET, MOBY_API_KEY,
                    ALLOWED_IMAGE_EXTS)

# ─── Simple in-memory cache with TTL ─────────────────────────────────────────
_cache: dict = {}
_CACHE_TTL = 86400  # 24 hours


def _cache_key(query, platform, content_id):
    return f"{(query or '').lower()}|{platform or ''}|{content_id or ''}"


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


def cache_stats():
    now = time.time()
    valid = sum(1 for _, (_, exp) in _cache.items() if exp > now)
    return {"total": len(_cache), "valid": valid}


def cache_clear():
    _cache.clear()


# ─── RAWG API ─────────────────────────────────────────────────────────────────

def rawg_request(path, params=None):
    if not RAWG_API_KEY: return None
    p = {"key": RAWG_API_KEY}
    if params: p.update(params)
    url = f"https://api.rawg.io/api/{path}?{urllib.parse.urlencode(p)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PSLibrary/3.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"RAWG error: {e}"); return None


# ─── IGDB API ─────────────────────────────────────────────────────────────────

_igdb_token = {"token": None, "expires": 0}
IGDB_PLATFORM_MAP = {"PS1": 7, "PS2": 8, "PS3": 9, "PSP": 38, "PS4": 48, "PS5": 167}
IGDB_PLATFORM_REV = {v: k for k, v in IGDB_PLATFORM_MAP.items()}


def _igdb_get_token():
    if _igdb_token["token"] and time.time() < _igdb_token["expires"]:
        return _igdb_token["token"]
    if not IGDB_CLIENT_ID or not IGDB_SECRET: return None
    try:
        data = urllib.parse.urlencode({
            "client_id": IGDB_CLIENT_ID, "client_secret": IGDB_SECRET,
            "grant_type": "client_credentials"
        }).encode()
        req = urllib.request.Request("https://id.twitch.tv/oauth2/token", data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            r = json.loads(resp.read().decode())
            _igdb_token["token"] = r["access_token"]
            _igdb_token["expires"] = time.time() + r.get("expires_in", 3600) - 60
            return _igdb_token["token"]
    except Exception as e:
        print(f"IGDB OAuth error: {e}"); return None


def _igdb_request(endpoint, body):
    token = _igdb_get_token()
    if not token: return None
    try:
        req = urllib.request.Request(f"https://api.igdb.com/v4/{endpoint}",
            data=body.encode(), method="POST",
            headers={"Client-ID": IGDB_CLIENT_ID, "Authorization": f"Bearer {token}",
                     "Content-Type": "text/plain"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"IGDB error: {e}"); return None


def igdb_search(query, platform=None):
    plat_filter = ""
    if platform and platform in IGDB_PLATFORM_MAP:
        plat_filter = f"& platforms = ({IGDB_PLATFORM_MAP[platform]})"
    body = f'''search "{query}";
        fields name,summary,cover.url,genres.name,platforms.id,
               first_release_date,involved_companies.company.name,
               involved_companies.developer,involved_companies.publisher,
               screenshots.url;
        where platforms = ({",".join(str(v) for v in IGDB_PLATFORM_MAP.values())}) {plat_filter};
        limit 5;'''
    results = _igdb_request("games", body)
    if not results: return None
    for g in results:
        cover_url = ""
        if g.get("cover") and g["cover"].get("url"):
            cover_url = "https:" + g["cover"]["url"].replace("t_thumb", "t_cover_big")
        banner_url = ""
        if g.get("screenshots"):
            banner_url = "https:" + g["screenshots"][0]["url"].replace("t_thumb", "t_screenshot_big")
        genres = [gn["name"] for gn in g.get("genres", [])]
        developer = publisher = ""
        for ic in g.get("involved_companies", []):
            co = ic.get("company", {}).get("name", "")
            if ic.get("developer"): developer = co
            if ic.get("publisher"): publisher = co
        ps_plat = None
        for p in g.get("platforms", []):
            pid = p if isinstance(p, int) else p.get("id")
            if pid in IGDB_PLATFORM_REV:
                ps_plat = IGDB_PLATFORM_REV[pid]; break
        release_date = ""
        if g.get("first_release_date"):
            try:
                release_date = time.strftime("%Y-%m-%d", time.gmtime(g["first_release_date"]))
            except: pass
        return {
            "title": g.get("name", ""),
            "description": (g.get("summary", "") or "")[:1000],
            "genre": ", ".join(genres[:3]),
            "cover_url": cover_url,
            "banner_url": banner_url,
            "developer": developer,
            "publisher": publisher,
            "release_date": release_date,
            "metacritic": None,
            "platform": ps_plat or platform,
            "source": "IGDB"
        }
    return None


# ─── MobyGames API ────────────────────────────────────────────────────────────

MOBY_PLATFORM_MAP = {"PS1": 6, "PS2": 7, "PS3": 81, "PSP": 46, "PS4": 141, "PS5": 283}


def moby_search(query, platform=None):
    if not MOBY_API_KEY: return None
    params = {"api_key": MOBY_API_KEY, "title": query, "format": "normal"}
    if platform and platform in MOBY_PLATFORM_MAP:
        params["platform"] = MOBY_PLATFORM_MAP[platform]
    url = f"https://api.mobygames.com/v1/games?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PSLibrary/3.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"MobyGames error: {e}"); return None
    games = data.get("games", [])
    if not games: return None
    g = games[0]
    cover_url = ""
    if g.get("sample_cover") and g["sample_cover"].get("image"):
        cover_url = g["sample_cover"]["image"]
    genres = [gn.get("genre_name", "") for gn in g.get("genres", [])]
    description = re.sub(r'<[^>]+>', '', (g.get("description", "") or "")[:1000])
    return {
        "title": g.get("title", ""),
        "description": description,
        "genre": ", ".join(genres[:3]),
        "cover_url": cover_url,
        "banner_url": "",
        "developer": "",
        "publisher": "",
        "release_date": str(g.get("first_release_date", "")),
        "metacritic": None,
        "platform": platform,
        "source": "MobyGames"
    }


# ─── Unified cascade search ───────────────────────────────────────────────────

def _rawg_search_full(query, platform=None):
    if not RAWG_API_KEY: return None
    params = {"search": query, "page_size": 5}
    plat_ids = {"PS1": "27", "PS2": "15", "PS3": "16", "PS4": "18", "PS5": "187", "PSP": "17"}
    if platform in plat_ids:
        params["platforms"] = plat_ids[platform]
    data = rawg_request("games", params)
    if not data or not data.get("results"): return None
    g = data["results"][0]
    platforms = [p["platform"]["name"] for p in g.get("platforms", [])]
    ps_plat = next((p for p in ["PS5", "PS4", "PS3", "PS2", "PS1", "PSP"] if any(p in pl for pl in platforms)), platform)
    detail = rawg_request(f"games/{g['id']}")
    if detail:
        developer = next((t["name"] for t in detail.get("developers", [])), "")
        publisher = next((t["name"] for t in detail.get("publishers", [])), "")
        desc = (detail.get("description_raw", "") or "")[:1000]
        genres = [gn["name"] for gn in detail.get("genres", [])]
    else:
        developer = publisher = desc = ""
        genres = [gn["name"] for gn in g.get("genres", [])]
    banner_url = ""
    screenshots = rawg_request(f"games/{g['id']}/screenshots", {"page_size": 3})
    if screenshots and screenshots.get("results"):
        banner_url = screenshots["results"][0].get("image", "")
    return {
        "title": g.get("name", ""),
        "description": desc,
        "genre": ", ".join(genres[:3]),
        "cover_url": g.get("background_image", ""),
        "banner_url": banner_url,
        "developer": developer,
        "publisher": publisher,
        "release_date": g.get("released", ""),
        "metacritic": g.get("metacritic"),
        "rawg_id": g.get("id"),
        "platform": ps_plat,
        "source": "RAWG"
    }


def _title_hint_from_content_id(content_id):
    if not content_id: return None
    parts = re.split(r'[-_]00[-_]|[-_]', content_id)
    slug = None
    for part in reversed(parts):
        if len(part) < 4: continue
        if re.match(r'^[A-Z]{2}\d{4}$|^[A-Z]{4}\d{4,5}$|^\d+$', part): continue
        slug = part; break
    if not slug: return None
    slug = re.sub(r'\d+$', '', slug)
    for suffix in ['GAME', 'FULLGAME', 'FULL', 'TRIAL', 'DEMO', 'BUNDLE', 'PKG', 'INSTALL',
                   'PATCH', 'UPDATE', 'DLC', 'ADDON', 'CONTENT', 'DATA']:
        if slug.upper().endswith(suffix) and len(slug) > len(suffix) + 2:
            slug = slug[:len(slug)-len(suffix)]
    slug = slug.rstrip('_- ')
    if len(slug) < 3: return None
    words = re.sub(r'([a-z])([A-Z])', r'\1 \2', slug)
    words = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', words)
    if ' ' not in words and words.isupper() and len(words) > 6:
        known = ['UNCHARTED', 'ASSASSIN', 'RESIDENT', 'HORIZON', 'RATCHET', 'COLOSSUS',
                 'PERSONA', 'THUNDER', 'FIGHTER', 'SPIDER', 'SHADOW', 'SILENT', 'RAIDER',
                 'BOMBER', 'BATTLE', 'STRIKE', 'METAL', 'SOLID', 'THEFT', 'GRAND',
                 'QUEST', 'WORLD', 'CRAFT', 'FORCE', 'CLANK', 'SPEED', 'TALES', 'ULTRA',
                 'CREED', 'DEMON', 'SOULS', 'ELDEN', 'RINGS', 'FINAL', 'BLOOD', 'BORNE',
                 'DARK', 'DEAD', 'EVIL', 'GEAR', 'HILL', 'LAST', 'DAWN', 'TOMB', 'NEED',
                 'AUTO', 'ZERO', 'MAN', 'WAR', 'GOD', 'FAR', 'CRY']
        result = words
        for w in sorted(known, key=len, reverse=True):
            result = result.replace(w, ' ' + w + ' ')
        words = re.sub(r'\s+', ' ', result).strip()
    words = re.sub(r'\s+', ' ', words).strip()
    return words.title() if words else None


def search_metadata(query, platform=None, content_id=None):
    """Cascade: RAWG → IGDB → MobyGames, with in-memory cache."""
    cache_k = _cache_key(query, platform, content_id)
    cached = _get_cached(cache_k)
    if cached:
        print(f"  ✓ Cache hit: '{query}'")
        return cached

    search_terms = []
    if content_id:
        title_hint = _title_hint_from_content_id(content_id)
        if title_hint and len(title_hint) > 3:
            search_terms.append(title_hint)
        code_match = re.search(
            r'(NPEB|NPUA|NPUB|NPHA|NPJA|BLES|BCUS|BLAS|BLJM|BCJS|BCAS|CUSA|PPSA|UCUS|UCES|UCAS|UCJS|SLUS|SCUS|SLES|SCES|SLPS)\d{4,5}',
            content_id.upper())
        if code_match:
            search_terms.append(code_match.group(0))
    if query:
        for existing in search_terms:
            if query.lower() == existing.lower(): break
        else:
            search_terms.append(query)

    result = None
    for search_q in search_terms:
        result = _rawg_search_full(search_q, platform)
        if result:
            print(f"  ✓ RAWG: '{search_q}' → {result['title']}")
            break
        time.sleep(0.25)
        result = igdb_search(search_q, platform)
        if result:
            print(f"  ✓ IGDB: '{search_q}' → {result['title']}")
            break
        time.sleep(0.25)
        result = moby_search(search_q, platform)
        if result:
            print(f"  ✓ MobyGames: '{search_q}' → {result['title']}")
            break
        time.sleep(0.25)

    if result:
        _set_cached(cache_k, result)
    return result


def download_image_url(url, dest_path):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PSLibrary/3.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'wb') as f:
                f.write(resp.read())
        return True
    except Exception as e:
        print(f"Image download error {url}: {e}"); return False
