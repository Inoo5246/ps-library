"""Redump.org DAT integration — import DAT files and verify disc images locally."""
import os, hashlib, binascii, xml.etree.ElementTree as ET
from pathlib import Path
from db import get_db


# ─── DAT import ───────────────────────────────────────────────────────────────

def import_dat(dat_filepath):
    """Parse a Redump XML DAT file and store its entries in the local DB.

    If a DAT with the same filename already exists, it is replaced.
    Returns {"platform", "game_count", "dat_id"}.
    """
    tree = ET.parse(dat_filepath)
    root = tree.getroot()

    header   = root.find("header")
    platform = (header.findtext("name") if header is not None else None) or Path(dat_filepath).stem
    dat_name = Path(dat_filepath).name

    conn = get_db()
    # Replace the existing DAT with the same name
    existing = conn.execute("SELECT id FROM redump_dats WHERE filename=?",
                            (dat_name,)).fetchone()
    if existing:
        conn.execute("DELETE FROM redump_entries WHERE dat_id=?", (existing["id"],))
        conn.execute("DELETE FROM redump_dats WHERE id=?",        (existing["id"],))

    cur = conn.execute(
        "INSERT INTO redump_dats (platform, filename, game_count) VALUES (?,?,0)",
        (platform, dat_name))
    dat_id = cur.lastrowid

    count = 0
    for game in root.findall("game"):
        game_name = game.get("name", "")
        for rom in game.findall("rom"):
            conn.execute("""INSERT INTO redump_entries
                (dat_id, game_name, disc_name, file_size, crc32, md5, sha1)
                VALUES (?,?,?,?,?,?,?)""",
                (dat_id,
                 game_name,
                 rom.get("name", ""),
                 int(rom.get("size") or 0),
                 (rom.get("crc")  or "").lower(),
                 (rom.get("md5")  or "").lower(),
                 (rom.get("sha1") or "").lower()))
            count += 1

    conn.execute("UPDATE redump_dats SET game_count=? WHERE id=?", (count, dat_id))
    conn.commit()
    conn.close()
    return {"platform": platform, "game_count": count, "dat_id": dat_id}


# ─── Hashing ──────────────────────────────────────────────────────────────────

def hash_file(filepath, chunk_size=1024 * 1024):
    """Calculate MD5 + CRC32 of a file by reading it in 1 MB chunks.
    Returns (md5_hex, crc32_hex) — lowercase.
    """
    md5 = hashlib.md5()
    crc = 0
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            md5.update(chunk)
            crc = binascii.crc32(chunk, crc) & 0xFFFFFFFF
    return md5.hexdigest(), f"{crc:08x}"


# ─── Lookup ───────────────────────────────────────────────────────────────────

def lookup(md5_hex=None, crc32_hex=None):
    """Look up a disc in the local Redump DB by MD5 or CRC32.
    Returns dict or None.
    """
    conn = get_db()
    row = None
    if md5_hex:
        row = conn.execute("""
            SELECT e.game_name, e.disc_name, e.file_size, e.crc32, e.md5, d.platform
            FROM redump_entries e
            JOIN redump_dats d ON e.dat_id = d.id
            WHERE e.md5 = ?""", (md5_hex.lower(),)).fetchone()
    if not row and crc32_hex:
        row = conn.execute("""
            SELECT e.game_name, e.disc_name, e.file_size, e.crc32, e.md5, d.platform
            FROM redump_entries e
            JOIN redump_dats d ON e.dat_id = d.id
            WHERE e.crc32 = ?""", (crc32_hex.lower(),)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Identify ─────────────────────────────────────────────────────────────────

def identify_file(filepath):
    """Hash a disc file and look it up in the Redump DB.
    Returns {"md5", "crc32", "match": {...} | None} or {"error": "..."}.
    """
    try:
        md5, crc32 = hash_file(filepath)
        match = lookup(md5_hex=md5, crc32_hex=crc32)
        return {"md5": md5, "crc32": crc32, "match": match}
    except Exception as e:
        return {"error": str(e)}
