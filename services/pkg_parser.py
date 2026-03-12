import os, re, struct, json
from pathlib import Path
from config import PLATFORMS, PLATFORM_PATTERNS


def detect_platform_from_id(content_id):
    if not content_id: return None
    for pattern, platform in PLATFORM_PATTERNS.items():
        if re.match(pattern, content_id.upper()): return platform
    return None


def safe_folder_name(name):
    name = re.sub(r'[\\/:*?"<>|]', '_', name).strip().strip('.')
    return name[:80] or "Unknown"


def get_game_dir(platform, title):
    from config import GAMES_DIR
    return os.path.join(GAMES_DIR, platform, safe_folder_name(title))


def get_file_size_str(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024: return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def parse_pkg(filepath):
    info = {"content_id": None, "platform": None, "pkg_type": None}
    try:
        with open(filepath, 'rb') as f:
            header = f.read(0x200)
            if len(header) < 0x40: return info
            magic = header[:4]
            if magic == b'\x7f\x50\x4b\x47':
                pkg_type = struct.unpack('>I', header[0x04:0x08])[0]
                info['pkg_type'] = 'PSP' if pkg_type == 0x80000002 else 'PS3'
                raw_id = header[0x30:0x30+36].rstrip(b'\x00').decode('ascii', errors='ignore').strip()
                if raw_id:
                    info['content_id'] = raw_id
                    info['platform'] = detect_platform_from_id(raw_id) or info['pkg_type']
            elif magic == b'\x7f\x43\x4e\x54':
                info['pkg_type'] = 'PS4/PS5'
                chunk = header + f.read(0x1000 - len(header))
                m = re.search(rb'(PPSA|CUSA)\d{5}[-_]\w+', chunk)
                if m:
                    cid = m.group(0).decode('ascii', errors='ignore')[:36]
                    info['content_id'] = cid
                    info['platform'] = detect_platform_from_id(cid) or 'PS4'
            else:
                m = re.search(rb'(PPSA|CUSA|BCUS|BLES|BLAS|BLJM|BCJS|BCAS|NPUA|NPUB|NPEB)\d{4,5}', header)
                if m:
                    cid = m.group(0).decode('ascii', errors='ignore')
                    info['content_id'] = cid
                    info['platform'] = detect_platform_from_id(cid)
    except Exception as e:
        print(f"PKG parse error {filepath}: {e}")
    return info


def parse_license(filepath):
    info = {"content_id": None}
    try:
        with open(filepath, 'rb') as f:
            data = f.read(0x200)
        ext = Path(filepath).suffix.lower()
        if ext == '.rap':
            m = re.search(rb'[A-Z]{4}\d{5}', data)
            if m: info['content_id'] = m.group(0).decode('ascii', errors='ignore')
        elif ext == '.rif':
            raw = data[0x10:0x10+36].rstrip(b'\x00').decode('ascii', errors='ignore').strip()
            if re.match(r'[A-Z]{4}\d{4}', raw): info['content_id'] = raw
        if not info['content_id']:
            name = Path(filepath).stem.upper()
            m = re.search(r'(PPSA|CUSA|BCUS|BLES|BLAS|BLJM|NPUA|NPUB|NPEB)\d{4,5}', name)
            if m: info['content_id'] = m.group(0)
    except Exception as e:
        print(f"License parse error: {e}")
    return info


# ─── Disc Image Parsing ───────────────────────────────────────────────────────

def _detect_sector_size(f):
    for sector_size, data_offset in [(2048, 0), (2352, 16), (2352, 24)]:
        try:
            f.seek(16 * sector_size + data_offset)
            chunk = f.read(6)
            if len(chunk) >= 6 and chunk[0:1] == b'\x01' and chunk[1:6] == b'CD001':
                return sector_size, data_offset
        except:
            pass
    return None, None


def _read_iso_sector(f, sector_num, sector_size, data_offset):
    f.seek(sector_num * sector_size + data_offset)
    return f.read(2048)


def _read_iso_file(filepath, target_path):
    try:
        with open(filepath, 'rb') as f:
            sector_size, data_offset = _detect_sector_size(f)
            if sector_size is None:
                return None
            pvd = _read_iso_sector(f, 16, sector_size, data_offset)
            if not pvd or pvd[0:1] != b'\x01' or pvd[1:6] != b'CD001':
                return None
            root_lba  = struct.unpack_from('<I', pvd, 156 + 2)[0]
            root_size = struct.unpack_from('<I', pvd, 156 + 10)[0]
            parts = [p for p in target_path.strip('/').split('/') if p]
            cur_lba, cur_size = root_lba, root_size
            for depth, part in enumerate(parts):
                dir_data = b''
                for s in range((cur_size + 2047) // 2048):
                    dir_data += _read_iso_sector(f, cur_lba + s, sector_size, data_offset)
                found = False
                offset = 0
                while offset < cur_size:
                    rec_len = dir_data[offset]
                    if rec_len == 0:
                        next_s = ((offset // 2048) + 1) * 2048
                        if next_s >= cur_size: break
                        offset = next_s; continue
                    if offset + 33 > len(dir_data): break
                    name_len = dir_data[offset + 32]
                    raw_name = dir_data[offset + 33:offset + 33 + name_len]
                    try:
                        name = raw_name.decode('ascii', errors='ignore')
                    except:
                        offset += rec_len; continue
                    if ';' in name: name = name.split(';')[0]
                    name = name.rstrip('.')
                    flags  = dir_data[offset + 25]
                    is_dir = bool(flags & 0x02)
                    e_lba  = struct.unpack_from('<I', dir_data, offset + 2)[0]
                    e_size = struct.unpack_from('<I', dir_data, offset + 10)[0]
                    if name.upper() == part.upper():
                        if depth == len(parts) - 1 and not is_dir:
                            file_data = b''
                            for s in range((e_size + 2047) // 2048):
                                file_data += _read_iso_sector(f, e_lba + s, sector_size, data_offset)
                            return file_data[:e_size]
                        elif is_dir:
                            cur_lba, cur_size = e_lba, e_size
                            found = True; break
                    offset += rec_len
                if not found: return None
            return None
    except Exception as e:
        print(f"ISO read error {filepath}: {e}")
        return None


def _parse_system_cnf(data):
    info = {"content_id": None, "platform": None}
    if not data: return info
    try:
        text = data.decode('ascii', errors='ignore')
        if 'BOOT2' in text.upper():
            info['platform'] = 'PS2'
        elif 'BOOT' in text.upper():
            info['platform'] = 'PS1'
        m = re.search(r'([A-Z]{4})[_-](\d{3})\.(\d{2})', text)
        if m:
            info['content_id'] = f"{m.group(1)}-{m.group(2)}{m.group(3)}"
        else:
            m = re.search(r'([A-Z]{4})[_-](\d{5})', text)
            if m: info['content_id'] = f"{m.group(1)}-{m.group(2)}"
    except Exception as e:
        print(f"SYSTEM.CNF parse error: {e}")
    return info


def _parse_sfo(data):
    result = {}
    if not data or len(data) < 20 or data[:4] != b'\x00PSF':
        return result
    try:
        key_tbl   = struct.unpack_from('<I', data, 8)[0]
        data_tbl  = struct.unpack_from('<I', data, 12)[0]
        n_entries = struct.unpack_from('<I', data, 16)[0]
        for i in range(min(n_entries, 100)):
            eo = 20 + i * 16
            if eo + 16 > len(data): break
            k_off = struct.unpack_from('<H', data, eo)[0]
            d_fmt = struct.unpack_from('<H', data, eo + 2)[0]
            d_len = struct.unpack_from('<I', data, eo + 4)[0]
            d_off = struct.unpack_from('<I', data, eo + 12)[0]
            ks = key_tbl + k_off
            ke = data.index(b'\x00', ks) if b'\x00' in data[ks:ks+64] else ks + 64
            key = data[ks:ke].decode('utf-8', errors='ignore')
            vs = data_tbl + d_off
            if d_fmt == 0x0204:
                val = data[vs:vs + d_len].rstrip(b'\x00').decode('utf-8', errors='ignore')
            elif d_fmt == 0x0404:
                val = struct.unpack_from('<I', data, vs)[0] if vs + 4 <= len(data) else 0
            else:
                continue
            result[key] = val
    except Exception as e:
        print(f"SFO parse error: {e}")
    return result


def parse_disc_image(filepath):
    info = {"content_id": None, "platform": None, "detected_title": None}
    ext = Path(filepath).suffix.lower()
    if ext == '.pbp':
        try:
            with open(filepath, 'rb') as f:
                header = f.read(0x28)
                if len(header) >= 0x28 and header[:4] == b'\x00PBP':
                    sfo_off  = struct.unpack_from('<I', header, 0x08)[0]
                    icon_off = struct.unpack_from('<I', header, 0x0C)[0]
                    sfo_size = icon_off - sfo_off
                    if sfo_size > 0 and sfo_size < 0x10000:
                        f.seek(sfo_off)
                        sfo_data = f.read(sfo_size)
                        sfo = _parse_sfo(sfo_data)
                        info['content_id'] = sfo.get('DISC_ID') or sfo.get('TITLE_ID', '')
                        info['platform'] = 'PSP'
                        info['detected_title'] = sfo.get('TITLE', '')
        except Exception as e:
            print(f"PBP parse error {filepath}: {e}")
        return info

    if ext not in ('.iso', '.bin', '.img'): return info

    sfo_data = _read_iso_file(filepath, "/PS3_GAME/PARAM.SFO")
    if sfo_data:
        sfo = _parse_sfo(sfo_data)
        if sfo.get("TITLE_ID"):
            info['content_id'] = sfo['TITLE_ID']
            info['platform'] = 'PS3'
            info['detected_title'] = sfo.get('TITLE', '')
            return info

    sfo_data = _read_iso_file(filepath, "/PSP_GAME/PARAM.SFO")
    if sfo_data:
        sfo = _parse_sfo(sfo_data)
        disc_id = sfo.get('DISC_ID') or sfo.get('TITLE_ID', '')
        if disc_id:
            info['content_id'] = disc_id
            info['platform'] = 'PSP'
            info['detected_title'] = sfo.get('TITLE', '')
            return info

    cnf_data = _read_iso_file(filepath, "/SYSTEM.CNF")
    if cnf_data:
        cnf = _parse_system_cnf(cnf_data)
        if cnf.get('content_id'):
            info['content_id'] = cnf['content_id']
            info['platform'] = cnf.get('platform')
            return info

    return info


def _title_from_path(filepath):
    parts = Path(filepath).parts
    fname_stem = Path(filepath).stem
    clean = re.sub(r'\(.*?\)|\[.*?\]', '', fname_stem)
    clean = re.sub(r'(SLUS|SCUS|SLES|SCES|SLPS|SCPS|SLPM|BCUS|BLES|CUSA|PPSA|UCUS|UCES)[_-]?\d{4,5}', '', clean, flags=re.I)
    clean = re.sub(r'[_\.]+', ' ', clean).strip()
    clean = re.sub(r'\s+', ' ', clean).strip()
    if len(parts) >= 3:
        folder = parts[-2]
        if folder.upper() not in PLATFORMS and folder.lower() not in ("games", "licenses", "images", "screenshots", "data"):
            folder_clean = re.sub(r'\(.*?\)|\[.*?\]', '', folder)
            folder_clean = re.sub(r'[_\.]+', ' ', folder_clean).strip()
            folder_clean = re.sub(r'\s+', ' ', folder_clean).strip()
            if len(folder_clean) > 2:
                return folder_clean
    if len(clean) > 2:
        return clean
    return None


def _detect_platform_from_path(fpath):
    for part in Path(fpath).parts:
        if part.upper() in PLATFORMS: return part.upper()
    return None


# ─── PS3 / PS5 Folder-Game Detection ─────────────────────────────────────────

def is_ps3_game_root(dirpath):
    """True if the directory contains PS3_GAME subfolders — PS3 folder-type backup."""
    return os.path.isdir(os.path.join(dirpath, "PS3_GAME"))


def is_ps4_game_root(dirpath):
    """True if the directory contains sce_sys/param.sfo (but NOT param.json) — PS4 folder-type backup."""
    sce = os.path.join(dirpath, "sce_sys")
    return (os.path.isfile(os.path.join(sce, "param.sfo")) and
            not os.path.isfile(os.path.join(sce, "param.json")))


def is_ps5_game_root(dirpath):
    """True if the directory contains sce_sys/param.json — PS5 folder-type backup."""
    return os.path.isfile(os.path.join(dirpath, "sce_sys", "param.json"))


def parse_ps3_folder(dirpath):
    """Reads PS3_GAME/PARAM.SFO and returns {content_id, title, platform}."""
    info = {"content_id": None, "title": None, "platform": "PS3"}
    sfo_path = os.path.join(dirpath, "PS3_GAME", "PARAM.SFO")
    try:
        with open(sfo_path, "rb") as f:
            sfo_data = f.read()
        sfo = _parse_sfo(sfo_data)
        info["content_id"] = sfo.get("TITLE_ID") or sfo.get("TITLE_ID_TEMP")
        info["title"] = sfo.get("TITLE") or Path(dirpath).name
    except Exception as e:
        print(f"[PS3 folder] parse error {dirpath}: {e}")
        info["title"] = Path(dirpath).name
    return info


def parse_ps4_folder(dirpath):
    """Reads sce_sys/param.sfo (binary) and returns {content_id, title, platform}."""
    info = {"content_id": None, "title": None, "platform": "PS4"}
    sfo_path = os.path.join(dirpath, "sce_sys", "param.sfo")
    try:
        with open(sfo_path, "rb") as f:
            sfo_data = f.read()
        sfo = _parse_sfo(sfo_data)
        info["content_id"] = sfo.get("TITLE_ID")
        info["title"] = sfo.get("TITLE") or Path(dirpath).name
    except Exception as e:
        print(f"[PS4 folder] parse error {dirpath}: {e}")
        info["title"] = Path(dirpath).name
    return info


def parse_ps5_folder(dirpath):
    """Reads sce_sys/param.json and returns {content_id, title, platform}."""
    info = {"content_id": None, "title": None, "platform": "PS5"}
    json_path = os.path.join(dirpath, "sce_sys", "param.json")
    try:
        with open(json_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        # Content ID
        cid = (data.get("contentId") or data.get("content_id") or
               data.get("titleId") or data.get("title_id") or "")
        info["content_id"] = cid or None
        # Title from localizedParameters or simple fields
        title = None
        lp = data.get("localizedParameters") or {}
        if isinstance(lp, dict):
            for lang_data in lp.values():
                if isinstance(lang_data, dict):
                    title = lang_data.get("titleName") or lang_data.get("title")
                    if title:
                        break
        info["title"] = (title or data.get("name") or data.get("title") or
                         Path(dirpath).name)
    except Exception as e:
        print(f"[PS5 folder] parse error {dirpath}: {e}")
        info["title"] = Path(dirpath).name
    return info


def get_folder_size(dirpath):
    """Calculate the total size (recursively) of a folder."""
    total = 0
    for root, _dirs, files in os.walk(dirpath):
        for fname in files:
            try:
                total += os.path.getsize(os.path.join(root, fname))
            except OSError:
                pass
    return total


def _auto_link_game(conn, content_id, filepath):
    if content_id:
        row = conn.execute("SELECT id FROM games WHERE ps_code LIKE ?",
                           (f"%{content_id[:9]}%",)).fetchone()
        if row: return row["id"]
    parts = Path(filepath).parts
    if len(parts) >= 3:
        folder_name = parts[-2]
        if folder_name not in PLATFORMS and folder_name.lower() not in ("licenses", "images", "screenshots"):
            row = conn.execute("SELECT id FROM games WHERE title LIKE ? LIMIT 1",
                               (f"%{folder_name}%",)).fetchone()
            if row: return row["id"]
    return None
