import time
from flask import Blueprint, request, jsonify
from config import RAWG_API_KEY, IGDB_CLIENT_ID, IGDB_SECRET, MOBY_API_KEY
from db import load_settings
from services.metadata import (rawg_request, igdb_search, moby_search, search_metadata,
                                IGDB_PLATFORM_MAP, IGDB_PLATFORM_REV, _igdb_request,
                                cache_stats, cache_clear)

metadata_bp = Blueprint("metadata", __name__)


@metadata_bp.route("/api/config")
def config():
    return jsonify({
        "has_rawg_key":  bool(RAWG_API_KEY),
        "has_igdb_key":  bool(IGDB_CLIENT_ID and IGDB_SECRET),
        "has_moby_key":  bool(MOBY_API_KEY),
        "games_dir":     "/games",
        "licenses_dir":  "/games/_licenses",
        "custom_folders_count": len(load_settings().get("custom_folders", []))
    })


@metadata_bp.route("/api/rawg/search")
def rawg_search():
    q = request.args.get("q", "").strip()
    if not q: return jsonify([])
    data = rawg_request("games", {"search": q, "platforms": "18,187", "page_size": 10})
    if not data: return jsonify({"error": "RAWG key missing or failed"}), 400
    results = []
    for g in data.get("results", []):
        platforms = [p["platform"]["name"] for p in g.get("platforms", [])]
        ps_plat = next((p for p in ["PS5", "PS4", "PS3", "PS2", "PS1"]
                        if any(p in pl for pl in platforms)), "PS5")
        results.append({
            "rawg_id": g["id"], "title": g["name"],
            "cover_url": g.get("background_image", ""),
            "release_date": g.get("released", ""), "metacritic": g.get("metacritic"),
            "genres": [gn["name"] for gn in g.get("genres", [])],
            "platform": ps_plat
        })
    return jsonify(results)


@metadata_bp.route("/api/rawg/game/<int:rawg_id>")
def rawg_game_detail(rawg_id):
    data = rawg_request(f"games/{rawg_id}")
    if not data: return jsonify({"error": "Not found"}), 404
    screenshots = rawg_request(f"games/{rawg_id}/screenshots", {"page_size": 5})
    banner_url  = (screenshots["results"][0].get("image", "")
                   if screenshots and screenshots.get("results") else "")
    platforms = [p["platform"]["name"] for p in data.get("platforms", [])]
    ps_plat   = next((p for p in ["PS5", "PS4", "PS3", "PS2", "PS1"]
                      if any(p in pl for pl in platforms)), "PS5")
    ps_code = ""
    stores_data = rawg_request(f"games/{rawg_id}/stores")
    if stores_data:
        for s in stores_data.get("results", []):
            if "store.playstation.com" in s.get("url", ""):
                ps_code = s["url"].rstrip("/").split("/")[-1]; break
    developer  = next((t["name"] for t in data.get("developers", [])), "")
    publisher  = next((t["name"] for t in data.get("publishers", [])), "")
    desc       = (data.get("description_raw", "") or "")[:1000]
    genres     = [g["name"] for g in data.get("genres", [])]
    return jsonify({
        "rawg_id": rawg_id, "title": data.get("name", ""),
        "cover_url": data.get("background_image", ""), "banner_url": banner_url,
        "description": desc, "ps_code": ps_code,
        "developer": developer, "publisher": publisher,
        "release_date": data.get("released", ""), "metacritic": data.get("metacritic"),
        "genre": ", ".join(genres[:3]), "platform": ps_plat
    })


@metadata_bp.route("/api/metadata/search")
def metadata_search():
    q = request.args.get("q", "").strip()
    if not q: return jsonify([])
    results = []
    # RAWG
    if RAWG_API_KEY:
        data = rawg_request("games", {"search": q, "page_size": 8})
        if data and data.get("results"):
            for g in data["results"]:
                platforms = [p["platform"]["name"] for p in g.get("platforms", [])]
                ps_plat = next((p for p in ["PS5", "PS4", "PS3", "PS2", "PS1", "PSP"]
                                if any(p in pl for pl in platforms)), "")
                if not ps_plat: continue
                results.append({
                    "source": "RAWG", "rawg_id": g["id"], "title": g["name"],
                    "cover_url": g.get("background_image", ""),
                    "release_date": g.get("released", ""), "metacritic": g.get("metacritic"),
                    "genres": [gn["name"] for gn in g.get("genres", [])],
                    "platform": ps_plat
                })
    # IGDB
    if IGDB_CLIENT_ID and IGDB_SECRET:
        ps_ids = ",".join(str(v) for v in IGDB_PLATFORM_MAP.values())
        body = (f'search "{q}"; fields name,cover.url,platforms.id,first_release_date,genres.name; '
                f'where platforms = ({ps_ids}); limit 5;')
        igdb_data = _igdb_request("games", body)
        if igdb_data:
            for g in igdb_data:
                cover = ""
                if g.get("cover") and g["cover"].get("url"):
                    cover = "https:" + g["cover"]["url"].replace("t_thumb", "t_cover_big")
                ps_plat = ""
                for p in g.get("platforms", []):
                    pid = p if isinstance(p, int) else p.get("id")
                    if pid in IGDB_PLATFORM_REV:
                        ps_plat = IGDB_PLATFORM_REV[pid]; break
                rd = ""
                if g.get("first_release_date"):
                    try: rd = time.strftime("%Y-%m-%d", time.gmtime(g["first_release_date"]))
                    except: pass
                if not any(r["title"] == g.get("name") for r in results):
                    results.append({
                        "source": "IGDB", "igdb_id": g.get("id"), "title": g.get("name", ""),
                        "cover_url": cover, "release_date": rd, "metacritic": None,
                        "genres": [gn["name"] for gn in g.get("genres", [])],
                        "platform": ps_plat
                    })
    # MobyGames
    if MOBY_API_KEY:
        import json, urllib.request, urllib.parse
        try:
            params = {"api_key": MOBY_API_KEY, "title": q, "format": "normal"}
            url = f"https://api.mobygames.com/v1/games?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={"User-Agent": "PSLibrary/3.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                moby_data = json.loads(resp.read().decode())
            for g in moby_data.get("games", [])[:5]:
                cover = g.get("sample_cover", {}).get("image", "") if g.get("sample_cover") else ""
                if not any(r["title"] == g.get("title") for r in results):
                    results.append({
                        "source": "MobyGames", "moby_id": g.get("game_id"),
                        "title": g.get("title", ""), "cover_url": cover,
                        "release_date": str(g.get("first_release_date", "")),
                        "metacritic": None,
                        "genres": [gn.get("genre_name", "") for gn in g.get("genres", [])],
                        "platform": ""
                    })
        except Exception as e:
            print(f"MobyGames search error: {e}")

    if not results:
        return jsonify({"error": "No results or no API configured"}), 400
    return jsonify(results)


@metadata_bp.route("/api/metadata/detail")
def metadata_detail():
    source  = request.args.get("source", "RAWG")
    game_id = request.args.get("id", "")
    title   = request.args.get("title", "")
    if source == "RAWG" and game_id:
        return rawg_game_detail(int(game_id))
    elif source == "IGDB" and (game_id or title):
        result = igdb_search(title or game_id)
        if result: return jsonify(result)
    elif source == "MobyGames" and title:
        result = moby_search(title)
        if result: return jsonify(result)
    result = search_metadata(title)
    if result: return jsonify(result)
    return jsonify({"error": "Not found"}), 404


@metadata_bp.route("/api/metadata/cache", methods=["GET"])
def get_cache_stats():
    return jsonify(cache_stats())


@metadata_bp.route("/api/metadata/cache", methods=["DELETE"])
def clear_cache():
    cache_clear()
    return jsonify({"ok": True, "message": "Cache cleared"})
