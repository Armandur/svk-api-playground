#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Gemensam dev-server för svk-api-playground.

Auto-detekterar pilot-projekt (undermappar med index.html på rotnivå)
och dokumentationen i docs/, och listar dem på en startsida på /.

Kör: `uv run scripts/serve.py` -> http://localhost:8088/
"""

from __future__ import annotations

import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("SVK_PORT", "8088"))
HOST = os.environ.get("SVK_HOST", "0.0.0.0")

# Mappar som inte ska listas som pilot-projekt även om de har index.html.
EXCLUDE_DIRS = {"docs", "scripts", "tmp", ".git", ".claude", ".venv",
                "__pycache__"}


def discover_links() -> list[dict]:
    """Bygg lista av länkar för startsidan."""
    links = []

    # Dokumentationen ligger på en specifik plats.
    if (ROOT / "docs" / "svk-apis.html").exists():
        links.append({
            "title": "API-dokumentation",
            "subtitle": "Modul-uppdelad referens för alla SVK-API:er",
            "url": "/docs/svk-apis.html",
            "kind": "docs",
        })

    # OpenAPI-specs i docs/specs/.
    specs_dir = ROOT / "docs" / "specs"
    if specs_dir.is_dir():
        for spec in sorted(specs_dir.glob("*.json")):
            links.append({
                "title": spec.stem,
                "subtitle": f"OpenAPI-spec ({spec.stat().st_size // 1024} KB)",
                "url": f"/docs/specs/{spec.name}",
                "kind": "spec",
            })

    # Pilot-projekt: undermappar med index.html på rotnivå.
    for entry in sorted(ROOT.iterdir()):
        if not entry.is_dir() or entry.name in EXCLUDE_DIRS or entry.name.startswith("."):
            continue
        if not (entry / "index.html").exists():
            continue
        readme = entry / "README.md"
        subtitle = ""
        if readme.exists():
            for line in readme.read_text(encoding="utf-8").splitlines()[:20]:
                line = line.strip()
                if line and not line.startswith("#"):
                    subtitle = line
                    break
        links.append({
            "title": entry.name,
            "subtitle": subtitle or "Pilot-projekt",
            "url": f"/{entry.name}/",
            "kind": "project",
        })

    return links


def render_index(links: list[dict]) -> bytes:
    cards = "\n".join(
        f"""<a class="card card-{l['kind']}" href="{l['url']}">
              <h2>{l['title']}</h2>
              <p>{l['subtitle']}</p>
              <span class="url">{l['url']}</span>
            </a>"""
        for l in links
    )
    html = TEMPLATE.replace("__CARDS__", cards)
    return html.encode("utf-8")


TEMPLATE = """<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>svk-api-playground</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Spectral:ital,wght@0,400;1,400&display=swap" rel="stylesheet">
<style>
:root {
  --beige: #FFEBE1;
  --black: #000;
  --wine: #7D0037;
  --gold: #BC8E4C;
  --green: #00554B;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: "DM Sans", Arial, sans-serif;
  background: var(--beige); color: var(--black);
  min-height: 100vh; padding: clamp(24px, 5vw, 64px);
  line-height: 1.4;
}
header { max-width: 960px; margin: 0 auto clamp(24px, 4vw, 48px); }
h1 {
  font-size: clamp(32px, 5vw, 56px); font-weight: 500;
  letter-spacing: -0.02em; line-height: 1.0;
  color: var(--wine);
}
h1 em {
  font-family: "Spectral", "Times New Roman", serif;
  font-style: italic; font-weight: 400; color: var(--black);
}
.lead { font-size: clamp(16px, 2vw, 20px); margin-top: 12px;
        max-width: 640px; }
main { max-width: 960px; margin: 0 auto;
       display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
       gap: 16px; }
.card {
  display: block; padding: 20px 24px;
  border: 2px solid var(--black); border-radius: 4px;
  background: #fff; text-decoration: none; color: inherit;
  transition: transform 0.1s, background 0.1s;
}
.card:hover { transform: translateY(-2px); background: var(--wine); color: var(--beige); }
.card:hover .url { color: var(--beige); opacity: 0.8; }
.card h2 { font-size: 20px; font-weight: 500; margin-bottom: 6px; }
.card p { font-size: 15px; min-height: 2.8em; }
.card .url { display: block; margin-top: 12px; font-size: 12px;
             font-family: ui-monospace, monospace; color: var(--gold);
             letter-spacing: 0.02em; }
.card-docs { border-color: var(--wine); }
.card-docs h2::before { content: "📚 "; }
.card-spec h2::before { content: "📋 "; }
.card-project h2::before { content: "🧪 "; }
footer { max-width: 960px; margin: clamp(32px, 5vw, 64px) auto 0;
         padding-top: 16px; border-top: 1px solid var(--black);
         font-size: 13px; color: #555; display: flex;
         justify-content: space-between; }
</style>
</head>
<body>
<header>
  <h1>svk-api-playground</h1>
  <p class="lead">Lekplats för Svenska kyrkans publika API:er. <em>Välj
  vad du vill kika på.</em></p>
</header>
<main>
__CARDS__
</main>
<footer>
  <span>Lokal dev-server</span>
  <span>Tryck <kbd>Ctrl+C</kbd> för att avsluta</span>
</footer>
</body>
</html>
"""


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - http.server konvention
        # Auto-genererad startsida på /
        if self.path in ("/", "/index.html"):
            body = render_index(discover_links())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, fmt: str, *args) -> None:
        # Mer kompakt loggning
        sys.stderr.write(f"{self.address_string()} {fmt % args}\n")


def main() -> int:
    os.chdir(ROOT)
    server = HTTPServer((HOST, PORT), Handler)
    url = f"http://localhost:{PORT}/"
    print(f">> svk-api-playground servar på {url}", flush=True)
    print(f">> root: {ROOT}", flush=True)
    print(f">> Ctrl+C för att avsluta", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n>> avslutar", flush=True)
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
