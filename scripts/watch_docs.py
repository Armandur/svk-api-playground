#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["watchfiles>=0.21"]
# ///
"""Watch docs/modules/ + scripts/build_docs.py, bygg om docs och synka till
/mnt/vmworkspace/svk-api-playground/ när nåt ändras.

Kör: `uv run scripts/watch_docs.py`. Avbryt med Ctrl+C.
"""

import subprocess
import sys
import time
from pathlib import Path

from watchfiles import watch

ROOT = Path(__file__).resolve().parent.parent
WATCH_PATHS = [
    ROOT / "docs" / "modules",
    ROOT / "scripts" / "build_docs.py",
    ROOT / "CLAUDE.md",
    ROOT / "README.md",
]
BUILD_CMD = ["uv", "run", str(ROOT / "scripts" / "build_docs.py")]
SYNC_DEST = Path("/mnt/vmworkspace/svk-api-playground")
# Spegla hela projektmappen utom secrets och lokala konfigfiler.
# `--filter=P` (Protect) gör att filer i docs-from-claude-code-chrome/
# på destinationen bevaras även om de inte finns i source - tänkt för
# rapporter som användaren laddar upp dit från andra enheter via
# Tailscale (Chrome-extension-flödet).
RSYNC_CMDS = [
    [
        "rsync", "-a", "--delete",
        "--exclude=.env", "--exclude=.env.local",
        "--exclude=.claude/",
        "--exclude=__pycache__/", "--exclude=.venv/",
        "--exclude=.git/",
        "--filter=P docs-from-claude-code-chrome/***",
        f"{ROOT}/", f"{SYNC_DEST}/",
    ],
]


def rebuild_and_sync() -> None:
    t0 = time.monotonic()
    r = subprocess.run(BUILD_CMD, cwd=ROOT)
    if r.returncode != 0:
        print(f"!! build misslyckades (exit {r.returncode})", flush=True)
        return
    SYNC_DEST.mkdir(parents=True, exist_ok=True)
    for cmd in RSYNC_CMDS:
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print(f"!! rsync misslyckades: {' '.join(cmd)} (exit {r.returncode})", flush=True)
            return
    print(f">> ok ({time.monotonic() - t0:.1f}s)", flush=True)


def main() -> None:
    print(f">> initial build + sync till {SYNC_DEST}", flush=True)
    rebuild_and_sync()
    print(f">> watchar: {', '.join(str(p.relative_to(ROOT)) for p in WATCH_PATHS)}", flush=True)
    for changes in watch(*WATCH_PATHS):
        for change, path in changes:
            print(f"   {change.name:>8}  {Path(path).relative_to(ROOT)}", flush=True)
        rebuild_and_sync()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n>> avslutar watcher", flush=True)
        sys.exit(0)
