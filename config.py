import os

DB_PATH        = "/data/games.db"
GAMES_DIR      = "/games"
LICENSES_DIR   = "/games/_licenses"
IMAGES_DIR     = os.environ.get("IMAGES_DIR", "/images")
SAVES_DIR      = os.environ.get("SAVES_DIR",  "/save")
DLC_DIR        = os.environ.get("DLC_DIR",    "/dlc")
LANG_DIR       = "/data/lang"
BUNDLED_LANG_DIR = os.path.join(os.path.dirname(__file__), "lang")
SETTINGS_PATH  = "/data/settings.json"

RAWG_API_KEY   = os.environ.get("RAWG_API_KEY", "")
IGDB_CLIENT_ID = os.environ.get("IGDB_CLIENT_ID", "")
IGDB_SECRET    = os.environ.get("IGDB_SECRET", "")
MOBY_API_KEY   = os.environ.get("MOBY_API_KEY", "")
MAX_UPLOAD_MB  = int(os.environ.get("MAX_UPLOAD_MB", "50000"))

PROWLARR_URL   = os.environ.get("PROWLARR_URL", "")
PROWLARR_KEY   = os.environ.get("PROWLARR_API_KEY", "")
DOWNLOADS_DIR  = os.environ.get("DOWNLOADS_DIR", "/downloads")

ALLOWED_GAME_EXTS    = {'.iso', '.pkg', '.apk', '.bin', '.img', '.cue', '.chd', '.pbp',
                         '.rar', '.zip'}
ALLOWED_LICENSE_EXTS = {'.rap', '.rif', '.edat', '.sdat'}
ALLOWED_IMAGE_EXTS   = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
PLATFORMS            = ["PS5", "PS4", "PS3", "PS2", "PS1", "PSP"]

PLATFORM_PATTERNS = {
    r'^PPSA': 'PS5',
    r'^CUSA': 'PS4',
    r'^BCUS|^BLES|^BLAS|^BLJM|^BCJS|^BCAS|^NPUA|^NPUB|^NPEB|^NPHA|^NPJA': 'PS3',
    r'^UCUS|^UCES|^UCAS|^UCJS|^NPUG|^NPEG': 'PSP',
    r'^SLUS|^SCUS|^SLES|^SCES|^SLPS|^SCPS|^SLPM|^SLKA|^SLAJ|^PBPX': 'PS2',
}
