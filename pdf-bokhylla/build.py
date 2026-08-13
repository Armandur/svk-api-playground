#!/usr/bin/env python3
"""Bygg och validera bokhyllas statiska PDF-export för GitHub Pages."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.json")
MIB = 1024 * 1024


def _las_json(sokvag: Path) -> dict:
    try:
        return json.loads(sokvag.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Kan inte läsa giltig JSON från {sokvag}: {exc}") from exc


def _storlek(katalog: Path) -> tuple[int, int]:
    filer = [fil for fil in katalog.rglob("*") if fil.is_file()]
    return sum(fil.stat().st_size for fil in filer), len(filer)


def _validera_manifest(bokhylla: Path, mal: Path, config: dict) -> None:
    grupper = _las_json(mal / "data" / "grupper.json").get("grupper", [])
    exporterade = {post.get("namn"): post for post in grupper}
    for grupp in config["grupper"]:
        namn = grupp["namn"]
        if namn not in exporterade:
            raise RuntimeError(f"PDF-exporten saknar gruppen {namn}")
        antal = exporterade[namn].get("antal", 0)
        if antal < grupp["minst_antal"]:
            raise RuntimeError(
                f"PDF-gruppen {namn} innehåller {antal} böcker, "
                f"minst {grupp['minst_antal']} krävs"
            )
        manifest = _las_json(
            bokhylla / "backend" / "pdfdata" / namn / "manifest.json"
        )
        saknade = set(manifest.get("saknade", []))
        tillatna = set(grupp.get("tillatet_saknade", []))
        ovantade = sorted(saknade - tillatna)
        aterkomna = sorted(tillatna - saknade)
        if ovantade:
            raise RuntimeError(
                f"PDF-gruppen {namn} har oväntat saknade dokument: "
                + ", ".join(ovantade)
            )
        if aterkomna:
            print(
                f"OBS: tidigare saknade dokument finns åter i {namn}: "
                + ", ".join(aterkomna),
                file=sys.stderr,
            )


def _skanna_hemlighet(mal: Path) -> None:
    hemlighet = os.environ.get("SVK_ODATA_API_KEY", "").encode()
    if not hemlighet:
        return
    for fil in (post for post in mal.rglob("*") if post.is_file()):
        data = fil.read_bytes()
        if hemlighet in data:
            raise RuntimeError(f"OData-nyckeln hittades i artefakten: {fil}")


def _validera_storlek(mal: Path, pages_rot: Path | None, config: dict) -> None:
    byte, filer = _storlek(mal)
    print(f"PDF-bokhylla: {byte / MIB:.1f} MiB i {filer} filer")
    if byte > config["max_pdf_mib"] * MIB:
        raise RuntimeError(
            f"PDF-exporten är {byte / MIB:.1f} MiB och överskrider "
            f"gränsen {config['max_pdf_mib']} MiB"
        )
    if pages_rot:
        pages_byte, pages_filer = _storlek(pages_rot)
        print(f"Hela Pages-artefakten: {pages_byte / MIB:.1f} MiB i {pages_filer} filer")
        if pages_byte > config["max_pages_mib"] * MIB:
            raise RuntimeError(
                f"Pages-artefakten är {pages_byte / MIB:.1f} MiB och "
                f"överskrider gränsen {config['max_pages_mib']} MiB"
            )


def _validera_ref(config: dict) -> None:
    ref = config["bokhylla"]["ref"]
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise RuntimeError("bokhylla.ref måste vara en fullständig commit-SHA")


def bygg(bokhylla: Path, mal: Path, pages_rot: Path | None) -> None:
    config = _las_json(CONFIG_PATH)
    _validera_ref(config)
    backend = bokhylla / "backend"
    frontend = bokhylla / "poc"
    if not (backend / "app" / "pdfexport.py").is_file() or not frontend.is_dir():
        raise RuntimeError(
            f"Pinnad bokhylla-checkout saknas eller saknar TASK-1198: {bokhylla}"
        )
    if mal.name != "pdf-bokhylla" or mal in {Path("/"), Path.home(), bokhylla}:
        raise RuntimeError(
            "Exportmålet måste vara en särskild katalog med namnet pdf-bokhylla"
        )
    if mal.exists():
        shutil.rmtree(mal)
    kommandot = ["uv", "run", "python", "-m", "app.pdfexport", "--mal", str(mal)]
    for grupp in config["grupper"]:
        kommandot.extend(("--grupp", grupp["namn"]))
    kommandot.extend(("--frontend", str(frontend)))
    print("Bygger statisk PDF-bokhylla från pinnad bokhylla-version", flush=True)
    subprocess.run(kommandot, cwd=backend, check=True)
    _validera_manifest(bokhylla, mal, config)
    _skanna_hemlighet(mal)
    _validera_storlek(mal, pages_rot, config)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bokhylla", required=True, type=Path)
    parser.add_argument("--mal", required=True, type=Path)
    parser.add_argument("--pages-rot", type=Path)
    args = parser.parse_args()
    try:
        bygg(args.bokhylla.resolve(), args.mal.resolve(), args.pages_rot.resolve() if args.pages_rot else None)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"PDF-exporten avbröts: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
