#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Fristående statisk filserver för ls-visualize.

Lyssnar på 0.0.0.0:8989 och servar mappen där skriptet ligger.
Sätt SVK_PORT/SVK_HOST i miljön för att övrida.
"""

from __future__ import annotations

import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("SVK_PORT", "8989"))
HOST = os.environ.get("SVK_HOST", "0.0.0.0")


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> int:
    os.chdir(ROOT)
    server = HTTPServer((HOST, PORT), Handler)
    print(f">> ls-visualize servar på http://{HOST}:{PORT}/")
    print(f">> root: {ROOT}")
    print(f">> Ctrl+C för att avsluta")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n>> avslutar")
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
