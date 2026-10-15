#!/usr/bin/env python3
"""Local HIBP Pwned Passwords database — offline breach checking.

Downloads the full corpus from HIBP's official k-anonymity API
(1,048,576 range requests, ~35 GB) into ./hibp/ as 256 sorted text files
(one per 2-hex-char prefix group; lines: <40-hex-SHA1>:<breach-count>).
Resumable — re-run `download` to continue where it left off.

The app uses this automatically: if the group file for a password's hash
prefix exists, the breach check runs fully offline; otherwise it falls
back to the online k-anonymity API.

Usage:
  python3 hibp_db.py download [PREFIX ...]   download all groups (or merge
                                             specific 5-char hex prefixes)
  python3 hibp_db.py check <password>        offline lookup
  python3 hibp_db.py status                  show database state

Standard library only. Disk: ~35 GB. Time: ~30-90 min one-time, network
bound. A complete database is needed for accurate results.
"""
import bisect
import hashlib
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API_URL = "https://api.pwnedpasswords.com/range/{}"
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hibp")
GROUPS = [a + b for a in "0123456789ABCDEF" for b in "0123456789ABCDEF"]
WORKERS = 16


def _fetch_range(prefix, retries=3):
    """Fetch one 5-char prefix range; returns lines as '<full-hash>:<count>\\n'."""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(API_URL.format(prefix), timeout=30) as r:
                body = r.read().decode()
            if not body:
                return ""
            return "".join(f"{prefix}{line}" for line in body.splitlines(keepends=True))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def _download_group(group):
    """Download all 4096 prefixes of one group; write its file atomically."""
    path = os.path.join(DB_DIR, group + ".txt")
    prefixes = [f"{group}{i:03X}" for i in range(0x1000)]
    chunks = list(ThreadPoolExecutor(WORKERS).map(_fetch_range, prefixes))
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("".join(chunks))
    os.replace(tmp, path)


def cmd_download(extra_prefixes):
    os.makedirs(DB_DIR, exist_ok=True)
    if extra_prefixes:
        by_group = {}
        for p in extra_prefixes:
            p = p.upper()
            if len(p) != 5:
                sys.exit(f"bad prefix {p!r} (need 5 hex chars, e.g. 5BAA6)")
            by_group.setdefault(p[:2], []).append(p)
        for group, prefixes in by_group.items():
            path = os.path.join(DB_DIR, group + ".txt")
            lines = set()
            if os.path.exists(path):
                with open(path) as f:
                    lines.update(f.read().splitlines())
            for p in prefixes:
                lines.update(_fetch_range(p).splitlines())
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                f.write("".join(l + "\n" for l in sorted(lines)))
            os.replace(tmp, path)
            print(f"{group}: merged {len(prefixes)} prefix(es)")
        return
    todo = [g for g in GROUPS if not os.path.exists(os.path.join(DB_DIR, g + ".txt"))]
    gb = 35 * len(todo) / len(GROUPS)
    print(f"Downloading {len(todo)}/{len(GROUPS)} groups "
          f"({len(todo) * 0x1000:,} range requests, ~{gb:.0f} GB) into {DB_DIR} ...")
    t0 = time.time()
    for n, group in enumerate(todo, 1):
        g0 = time.time()
        _download_group(group)
        rate = (n * 0x1000) / (time.time() - t0)
        eta = (len(todo) - n) * 0x1000 / rate if rate else 0
        print(f"[{n}/{len(todo)}] {group}.txt ({time.time() - g0:.0f}s, "
              f"{rate:.0f} req/s, ETA {eta / 60:.0f} min)", flush=True)
    print(f"Download complete: {DB_DIR}")


_group_cache = {}


def _group_lines(group):
    """Cached sorted lines for one prefix group (None if the file is missing)."""
    if group not in _group_cache:
        if len(_group_cache) >= 2:  # keep RAM bounded (~350 MB per group)
            _group_cache.pop(next(iter(_group_cache)))
        path = os.path.join(DB_DIR, group + ".txt")
        if not os.path.exists(path):
            _group_cache[group] = None
        else:
            with open(path) as f:
                _group_cache[group] = f.read().splitlines()
    return _group_cache[group]


def local_breach_count(password):
    """Offline breach count: None = no local DB available, 0..N = count."""
    h = hashlib.sha1(password.encode()).hexdigest().upper()
    lines = _group_lines(h[:2])
    if lines is None:
        return None
    i = bisect.bisect_left(lines, h)
    if i < len(lines) and lines[i].startswith(h + ":"):
        return int(lines[i].rsplit(":", 1)[1])
    return 0


def cmd_check(password):
    count = local_breach_count(password)
    if count is None:
        print(f"No local HIBP database for this password's prefix group "
              f"(run: python3 {sys.argv[0]} download).")
    elif count:
        print(f"BREACHED: found in {count:,} data breaches (local database).")
    else:
        print("Not found in local HIBP database.")


def cmd_status():
    if not os.path.isdir(DB_DIR):
        print("No local HIBP database yet (run: python3 hibp_db.py download).")
        return
    files = [f for f in os.listdir(DB_DIR) if f.endswith(".txt")]
    size = sum(os.path.getsize(os.path.join(DB_DIR, f)) for f in files)
    print(f"{len(files)}/{len(GROUPS)} groups, {size / 2 ** 30:.1f} GB in {DB_DIR}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("download", "check", "status"):
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "download":
        cmd_download(sys.argv[2:])
    elif cmd == "check":
        cmd_check(sys.argv[2])
    else:
        cmd_status()