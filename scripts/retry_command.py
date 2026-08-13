#!/usr/bin/env python3
"""Kör om ett nätverksberoende kommando med tydlig stegdiagnostik."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namn", required=True)
    parser.add_argument("--forsok", type=int, default=3)
    parser.add_argument("--vantetid", type=float, default=15)
    parser.add_argument("kommando", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    kommando = args.kommando[1:] if args.kommando[:1] == ["--"] else args.kommando
    if not kommando or args.forsok < 1:
        parser.error("ett kommando och minst ett försök krävs")
    for nummer in range(1, args.forsok + 1):
        print(f"[{args.namn}] försök {nummer}/{args.forsok}", flush=True)
        resultat = subprocess.run(kommando, check=False)
        if resultat.returncode == 0:
            return
        if nummer == args.forsok:
            print(
                f"[{args.namn}] misslyckades efter {args.forsok} försök "
                f"(exit {resultat.returncode})",
                file=sys.stderr,
            )
            raise SystemExit(resultat.returncode)
        vantetid = args.vantetid * nummer
        print(f"[{args.namn}] väntar {vantetid:g} sekunder före nytt försök", flush=True)
        time.sleep(vantetid)


if __name__ == "__main__":
    main()
