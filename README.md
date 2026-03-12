# PS Library

![GitHub License](https://img.shields.io/github/license/Inoo5246/ps-library)
![GitHub stars](https://img.shields.io/github/stars/Inoo5246/ps-library)
![GitHub issues](https://img.shields.io/github/issues/Inoo5246/ps-library)

A self-hosted PlayStation game library manager with built-in file management, metadata lookup, and network streaming. Runs as a single Docker container.

This is a hobby project born out of a desire to have a clean, Jellyfin-like interface for managing a PlayStation game collection. Built for personal use and shared with the community in case others find it useful.

## Features

- **Game Library** — covers, banners, screenshots, descriptions, genres, ratings. Metadata from RAWG, IGDB, and MobyGames
- **File Manager** — manage ISO, PKG, BIN/CUE, CHD, PBP files + RAP/RIF/EDAT licenses, all from the browser
- **PKG Parser** — automatically extracts Content ID from PKG headers and links files to the correct game
- **Auto-scan** — watches mounted folders and detects PS3/PS4/PS5 game folder structures automatically
- **ps3netsrv** — built-in ps3netsrv server to stream PS3 games over the network (powered by [aldostools/webMAN-MOD](https://github.com/aldostools/webMAN-MOD))
- **Prowlarr Integration** — search indexers for game releases directly from the UI
- **Download Clients** — send downloads to qBittorrent or Transmission
- **Auto-monitor** — automatically searches for Wishlist games on indexers and downloads them when found
- **Redump Verification** — import Redump DAT files and verify disc dumps (MD5 + CRC32)
- **Save & DLC Management** — upload and organize save files and DLC per game
- **Upload & Download** — drag-and-drop upload with progress, download files directly from the browser
- **Multi-language** — English (default) and Romanian included, extensible
- **Platforms** — PS1, PS2, PS3, PS4, PS5, PSP

## Quick Start

```bash
docker compose up -d
```

Open http://localhost:5000, go to **File Manager** and click **Scan Folders**.

### Docker Compose

```yaml
services:
  ps-library:
    image: ghcr.io/inoo5246/ps-library:latest
    container_name: ps-library
    ports:
      - "5000:5000"       # Web UI
      - "38008:38008"     # ps3netsrv
    volumes:
      - ./ps-data:/data
      - /path/to/games:/games
      - /path/to/images:/images
      - /path/to/dlc:/dlc
      - /path/to/saves:/save
      - /path/to/downloads:/downloads
    environment:
      - RAWG_API_KEY=           # optional, for metadata
      - IGDB_CLIENT_ID=         # optional, for metadata
      - IGDB_SECRET=            # optional, for metadata
      - MOBY_API_KEY=           # optional, for metadata
      - MAX_UPLOAD_MB=50000
    restart: unless-stopped
```

### Recommended folder structure

```
/games/
  PS1/
    CoolGame.iso
  PS2/
    AnotherGame.iso
  PS3/
    UP0001-BCUS98174_00-EXAMPLE.pkg
  PS4/
    CUSA00001-something.pkg
  PS5/
    PPSA01234-something.pkg
```

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description | Required |
|----------|-------------|----------|
| `RAWG_API_KEY` | [RAWG](https://rawg.io/apidocs) API key (free, 20k req/month) | No |
| `IGDB_CLIENT_ID` | [IGDB/Twitch](https://dev.twitch.tv) client ID (free) | No |
| `IGDB_SECRET` | IGDB/Twitch client secret | No |
| `MOBY_API_KEY` | [MobyGames](https://www.mobygames.com/info/api) API key (free, 360 req/hour) | No |
| `GAMES_PATH` | Host path to game files | No (default: `./library/games`) |
| `IMAGES_PATH` | Host path to artwork | No (default: `./library/images`) |
| `DLC_PATH` | Host path to DLC files | No (default: `./library/dlc`) |
| `SAVES_PATH` | Host path to save files | No (default: `./library/save`) |
| `DOWNLOADS_PATH` | Host path for downloads | No (default: `./library/downloads`) |
| `MAX_UPLOAD_MB` | Max upload size in MB | No (default: `50000`) |

Prowlarr, download clients (qBittorrent/Transmission), and ps3netsrv are configured from the **Settings** page in the web UI.

## Supported Formats

| Format | Platforms | Notes |
|--------|-----------|-------|
| ISO | PS1, PS2, PS3 | Standard disc image |
| PKG | PS3, PS4, PS5 | Content ID auto-extracted |
| BIN/IMG/CUE | PS1, PS2 | Multi-track disc image |
| CHD | Any | Compressed disc image |
| PBP | PSP | PSP game format |
| RAP | PS3, PS4 | License key |
| RIF | PS3, PS4, PS5 | License file |
| EDAT/SDAT | PS3 | Encrypted data |

## Screenshots

*Coming soon*

## Tech Stack

- **Backend** — Python / Flask, SQLite
- **Frontend** — Vanilla JavaScript, Jinja2 templates
- **Containerization** — Docker (single container)
- **ps3netsrv** — built from [aldostools/webMAN-MOD](https://github.com/aldostools/webMAN-MOD)

## Contributing Translations

PS Library ships with English and Romanian. To add your own language:

1. Copy `lang/example.json` to `lang/xx.json` (where `xx` is your [ISO 639-1 code](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes))
2. Set the `lang_name` key to your language's native name (e.g. `"Deutsch"`, `"Français"`)
3. Translate all values (keep the keys unchanged)
4. Place the file in `./ps-data/lang/xx.json` on your host (this maps to `/data/lang/` inside the container)
5. Restart the container — your language will appear in the language selector

Pull requests with new language files are welcome.

## Support

If you find this project useful, you can support its development:

- [Buy Me a Coffee](https://buymeacoffee.com/inoo5246)
- [Ko-fi](https://ko-fi.com/inoo5246)

## Disclaimer

This project is a tool for managing your personal game library. It is intended for use with games you legally own. **Piracy is not supported or encouraged.** Please purchase and support the developers and publishers who create the games and software you enjoy.

## License

This project is licensed under the [MIT License](LICENSE).
