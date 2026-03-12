import sqlite3, os, json
from config import DB_PATH, GAMES_DIR, LICENSES_DIR, IMAGES_DIR, LANG_DIR, BUNDLED_LANG_DIR, SETTINGS_PATH


def get_db():
    os.makedirs("/data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    for d in [GAMES_DIR, LICENSES_DIR,
              f"{IMAGES_DIR}/cover", f"{IMAGES_DIR}/banner",
              f"{IMAGES_DIR}/screenshot", f"{IMAGES_DIR}/other",
              LANG_DIR]:
        os.makedirs(d, exist_ok=True)
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, genre TEXT, platform TEXT DEFAULT 'PS5',
        rating INTEGER DEFAULT 0, status TEXT DEFAULT 'Wishlist',
        cover_url TEXT, banner_url TEXT, description TEXT, ps_code TEXT,
        developer TEXT, publisher TEXT, release_date TEXT,
        metacritic INTEGER, rawg_id INTEGER,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS game_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER REFERENCES games(id) ON DELETE SET NULL,
        filename TEXT NOT NULL, filepath TEXT NOT NULL,
        file_type TEXT, platform TEXT, content_id TEXT,
        file_size INTEGER, file_size_str TEXT, pkg_type TEXT,
        is_uploaded INTEGER DEFAULT 0,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER REFERENCES games(id) ON DELETE SET NULL,
        filename TEXT NOT NULL, filepath TEXT NOT NULL,
        license_type TEXT, content_id TEXT,
        file_size INTEGER, is_uploaded INTEGER DEFAULT 0,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    for col in ["banner_url TEXT", "description TEXT", "ps_code TEXT", "developer TEXT",
                "publisher TEXT", "release_date TEXT", "metacritic INTEGER", "rawg_id INTEGER",
                "media_type TEXT DEFAULT 'Digital'", "physical_edition TEXT",
                "physical_condition TEXT", "physical_notes TEXT", "physical_barcode TEXT",
                "metadata_source TEXT", "video_links TEXT"]:
        try: conn.execute(f"ALTER TABLE games ADD COLUMN {col}")
        except: pass
    conn.execute("""CREATE TABLE IF NOT EXISTS redump_dats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        filename TEXT NOT NULL,
        game_count INTEGER DEFAULT 0,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS redump_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dat_id INTEGER REFERENCES redump_dats(id) ON DELETE CASCADE,
        game_name TEXT NOT NULL,
        disc_name TEXT NOT NULL,
        file_size INTEGER DEFAULT 0,
        crc32 TEXT, md5 TEXT, sha1 TEXT)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rdump_md5   ON redump_entries(md5)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rdump_crc32 ON redump_entries(crc32)")
    conn.execute("""CREATE TABLE IF NOT EXISTS game_saves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER REFERENCES games(id) ON DELETE SET NULL,
        filename TEXT NOT NULL, filepath TEXT NOT NULL,
        file_size INTEGER, file_size_str TEXT,
        platform TEXT, is_uploaded INTEGER DEFAULT 0,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS game_dlc (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER REFERENCES games(id) ON DELETE SET NULL,
        filename TEXT NOT NULL, filepath TEXT NOT NULL,
        file_type TEXT, content_id TEXT,
        file_size INTEGER, file_size_str TEXT,
        platform TEXT, is_uploaded INTEGER DEFAULT 0,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    for col in ["notes TEXT", "detected_title TEXT", "md5_hash TEXT"]:
        try: conn.execute(f"ALTER TABLE game_files ADD COLUMN {col}")
        except: pass
    for col in ["notes TEXT"]:
        try: conn.execute(f"ALTER TABLE licenses ADD COLUMN {col}")
        except: pass
    # Downloads table for Prowlarr/torrent integration
    conn.execute("""CREATE TABLE IF NOT EXISTS downloads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER REFERENCES games(id) ON DELETE SET NULL,
        title TEXT NOT NULL,
        indexer TEXT,
        download_url TEXT,
        info_hash TEXT,
        download_client TEXT,
        client_id TEXT,
        size INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        progress REAL DEFAULT 0,
        download_speed INTEGER DEFAULT 0,
        seeders INTEGER DEFAULT 0,
        leechers INTEGER DEFAULT 0,
        save_path TEXT,
        error_message TEXT,
        auto_grabbed INTEGER DEFAULT 0,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP)""")
    for col in ["monitored INTEGER DEFAULT 0"]:
        try: conn.execute(f"ALTER TABLE games ADD COLUMN {col}")
        except: pass
    conn.commit()
    conn.close()
    _init_default_langs()


def _init_default_langs():
    """Copy bundled language files to the runtime lang directory, always updating bundled langs."""
    import shutil
    if os.path.isdir(BUNDLED_LANG_DIR):
        for fname in os.listdir(BUNDLED_LANG_DIR):
            if fname.endswith('.json') and fname != 'example.json':
                shutil.copy2(os.path.join(BUNDLED_LANG_DIR, fname), os.path.join(LANG_DIR, fname))


def _default_settings():
    return {
        "language": "en",
        "custom_folders": [],
        "theme": "dark",
        "auto_scan_interval_hours": 0,
        "last_auto_scan": 0,
        "images_dir": "",   # empty = use env var IMAGES_DIR
        "saves_dir": "",    # empty = use env var SAVES_DIR
        "dlc_dir": "",      # empty = use env var DLC_DIR
        "prowlarr": {
            "url": "",
            "api_key": ""
        },
        "download_clients": {
            "default_client": "qbittorrent",
            "qbittorrent": {
                "enabled": False,
                "url": "",
                "username": "admin",
                "password": "",
                "category": "ps-library",
                "save_path": "/downloads"
            },
            "transmission": {
                "enabled": False,
                "url": "",
                "username": "",
                "password": "",
                "save_path": "/downloads"
            }
        },
        "auto_monitor": {
            "enabled": False,
            "interval_minutes": 30
        }
    }


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                s = json.load(f)
            d = _default_settings()
            d.update(s)
            return d
        except:
            pass
    return _default_settings()


def save_settings(data):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
