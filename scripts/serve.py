#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["markdown>=3.5"]
# ///
"""Gemensam dev-server för svk-api-playground.

Auto-detekterar pilot-projekt (undermappar med index.html på rotnivå)
och dokumentationen i docs/, och listar dem på en startsida på /.

Kör: `uv run scripts/serve.py` -> http://localhost:8088/
"""

from __future__ import annotations

import html as html_lib
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import markdown

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("SVK_PORT", "8088"))
HOST = os.environ.get("SVK_HOST", "0.0.0.0")

# Rebuild-state för osm-konsistenscheck
REBUILD_LOCK = threading.Lock()
REBUILD_STATE = {
    "status": "idle",
    "step": None,
    "step_index": 0,
    "step_total": 4,
    "started_at": None,
    "finished_at": None,
    "message": "",
    "last_error": None,
    "exit_code": None,
}


def run_rebuild() -> None:
    """Bakgrundstråd som kör rebuild-stegen i ordning."""
    steps = [
        ("svk", "osm-konsistenscheck/build_svk.py", "Hämtar SVK Platser..."),
        ("osm", "osm-konsistenscheck/build_osm.py", "Hämtar OSM via Overpass..."),
        ("wikidata", "osm-konsistenscheck/build_wikidata.py", "Hämtar SvK-stift från Wikidata..."),
        ("diff", "osm-konsistenscheck/build_diff.py", "Bygger matchning..."),
    ]

    for i, (step_id, script_path, msg) in enumerate(steps, 1):
        with REBUILD_LOCK:
            REBUILD_STATE["step"] = step_id
            REBUILD_STATE["step_index"] = i
            REBUILD_STATE["message"] = msg
        
        print(f">> rebuild [{i}/{len(steps)}]: {msg}", flush=True)
        try:
            # Vi använder sys.executable (python) och 'uv run' enligt instruktion.
            # Eftersom vi redan kör under uv kan vi antingen köra 'uv run' eller 
            # bara köra skriptet med sys.executable om vi litar på env.
            # Instruktionen sa: 'uv run osm-konsistenscheck/build_svk.py' etc.
            cmd = ["uv", "run", script_path]
            result = subprocess.run(
                cmd,
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                with REBUILD_LOCK:
                    REBUILD_STATE["status"] = "error"
                    REBUILD_STATE["exit_code"] = result.returncode
                    REBUILD_STATE["last_error"] = (result.stderr or result.stdout)[-1000:].strip()
                    REBUILD_STATE["finished_at"] = datetime.now().isoformat()
                print(f"!! rebuild misslyckades i steg {step_id} (exit {result.returncode})", flush=True)
                return
                
        except Exception as e:
            with REBUILD_LOCK:
                REBUILD_STATE["status"] = "error"
                REBUILD_STATE["last_error"] = str(e)
                REBUILD_STATE["finished_at"] = datetime.now().isoformat()
            print(f"!! rebuild kraschade: {e}", flush=True)
            return

    with REBUILD_LOCK:
        REBUILD_STATE["status"] = "done"
        REBUILD_STATE["step"] = None
        REBUILD_STATE["message"] = "Klar"
        REBUILD_STATE["finished_at"] = datetime.now().isoformat()
    print(">> rebuild slutförd utan fel", flush=True)

# Mappar som inte ska listas som pilot-projekt även om de har index.html.
EXCLUDE_DIRS = {"docs", "scripts", "tmp", ".git", ".claude", ".venv",
                "__pycache__"}

# CORS-kringgående proxies. svenskakyrkan.se/webapi/api-v2/churchcalendar
# är ett internt webb-API som inte sätter CORS-headers - vi proxar det
# här så pilot-projekt kan hämta data från samma origin som dev-servern.
CHURCHCALENDAR_API_KEY = "139ff33b-4451-4f0f-b397-1f4ec9307a87"
PROXY_PREFIX = "/api/churchcalendar"
PROXY_UPSTREAM = "https://www.svenskakyrkan.se/webapi/api-v2/churchcalendar"

# Generic SVK-API-proxy för pilot-projekt som behöver skrivåtkomst eller
# undkomma CORS. Nyckeln läses från env (APIKEY_PROD eller APIKEY_TEST
# beroende på SVK_ENV - prod är default).
SVK_ENV = os.environ.get("SVK_ENV", "prod").lower()
SVK_API_KEY = os.environ.get(
    f"APIKEY_{SVK_ENV.upper()}",
    os.environ.get("APIKEY_PROD") or os.environ.get("APIKEY_TEST", ""),
)
SVK_UPSTREAM = (
    "https://api.svenskakyrkan.se" if SVK_ENV == "prod"
    else "https://api-t.svenskakyrkan.se"
)
SVK_PROXY_ROUTES = {
    "/api/platser/": "/platser/v4/",
    "/api/units/": "/externwebb/api-v2/odata/units",
}

# Admin-proxy mot CMS:ets interna /webapi/api-v2/. Auth = sessionscookie
# CS_UserSessionId från en inloggad browser. Server-till-server kringgår
# CORS. Stödjer skrivande operationer (PUT med full replace) som den
# publika gatewayen inte tillåter med vår nyckel.
# Se docs-from-claude-code-chrome/platser-edit-flow-2026-05-01.md.
ADMIN_PROXY_PREFIX = "/api/admin/"
ADMIN_UPSTREAM = "https://admin.svenskakyrkan.se/webapi/api-v2/"
ADMIN_KEEPALIVE_URL = "https://admin.svenskakyrkan.se/churchcontext"
KEEPALIVE_INTERVAL = int(os.environ.get("ADMIN_KEEPALIVE_MIN", "30")) * 60
CS_SESSION = os.environ.get("CS_SESSION", "")
CS_SESSION_UPDATED_AT = 0.0    # unix timestamp för senast lyckad refresh
CS_SESSION_LAST_PING_AT = 0.0  # senaste keep-alive-ping eller manuell
CS_SESSION_LAST_PING_STATUS = ""  # "HTTP 200", "HTTP 401", "error: ..."
CS_SESSION_LAST_ROTATED_AT = 0.0  # senaste Set-Cookie-rotation från upstream
CS_SESSION_LOCK = threading.Lock()


def update_cs_session(new_value: str, source: str) -> bool:
    """Uppdatera global CS_SESSION om värdet är giltigt och nytt.
    Returnerar True om något ändrades."""
    global CS_SESSION, CS_SESSION_UPDATED_AT, CS_SESSION_LAST_ROTATED_AT
    if not new_value or len(new_value) < 50:
        return False
    with CS_SESSION_LOCK:
        if new_value == CS_SESSION:
            CS_SESSION_UPDATED_AT = time.time()
            return False
        CS_SESSION = new_value
        CS_SESSION_UPDATED_AT = time.time()
        CS_SESSION_LAST_ROTATED_AT = time.time()
    print(f">> CS_SESSION uppdaterad från {source} ({len(new_value)} tecken)",
          flush=True)
    return True


def admin_ping(source: str) -> tuple[int, str]:
    """Gör en GET mot ADMIN_KEEPALIVE_URL för att verifiera/förlänga
    sessionen. Uppdaterar CS_SESSION_LAST_PING_AT/_STATUS. Returnerar
    (http-status, status-text)."""
    global CS_SESSION_LAST_PING_AT, CS_SESSION_LAST_PING_STATUS
    if not CS_SESSION:
        return 0, "no-session"
    cookie_header = (
        CS_SESSION if "=" in CS_SESSION and ";" in CS_SESSION
        else f"CS_UserSessionId={CS_SESSION}"
    )
    req = Request(ADMIN_KEEPALIVE_URL, headers={
        "Cookie": cookie_header,
        "User-Agent": "svk-api-playground/keepalive",
    })
    try:
        with urlopen(req, timeout=15) as resp:
            data = resp.read()
            sc_list = resp.headers.get_all("Set-Cookie") or []
            new_session = apply_set_cookies(CS_SESSION, sc_list)
            if new_session:
                update_cs_session(new_session, f"{source} Set-Cookie")
            CS_SESSION_LAST_PING_AT = time.time()
            CS_SESSION_LAST_PING_STATUS = f"HTTP {resp.status}"
            log_admin_response(f"GET (ping/{source})", ADMIN_KEEPALIVE_URL,
                               resp.status, resp.headers, len(data))
            return resp.status, CS_SESSION_LAST_PING_STATUS
    except HTTPError as e:
        CS_SESSION_LAST_PING_AT = time.time()
        CS_SESSION_LAST_PING_STATUS = f"HTTP {e.code}"
        print(f"!! session ping ({source}): HTTP {e.code} - sessionen "
              f"kan ha löpt ut", flush=True)
        return e.code, CS_SESSION_LAST_PING_STATUS
    except Exception as e:
        CS_SESSION_LAST_PING_AT = time.time()
        CS_SESSION_LAST_PING_STATUS = f"error: {e}"
        print(f"!! session ping ({source}) misslyckades: {e}", flush=True)
        return 0, CS_SESSION_LAST_PING_STATUS


def _extract_first_json_object(text: str) -> str | None:
    """Hitta första balanserade {...}-objektet i en JS/JSON-sträng.
    Hanterar nästlade objekt och strängar (ignorerar { och } inuti dem).
    Returnerar substring inkl klamrar, eller None om inget hittas."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def parse_cookie_header(s: str) -> dict[str, str]:
    """Parsar 'name1=v1; name2=v2; ...' till en dict, bevarar ordning."""
    out: dict[str, str] = {}
    if not s:
        return out
    for pair in s.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        name, _, value = pair.partition("=")
        out[name.strip()] = value
    return out


def apply_set_cookies(current: str, set_cookie_headers: list[str]) -> str | None:
    """Applicera ev. Set-Cookie-headers på current cookie-header.

    Två lägen beroende på vad current är:
    - Full header ("name1=v1; name2=v2; ..."): merge ALL Set-Cookie:s
      som matchar cookies vi redan hade. Returnerar uppdaterad header
      om något ändrades.
    - Bara CS_UserSessionId-värde: returnera nytt CS_UserSessionId-
      värde om servern roterat det.

    Returnerar None om inget relevant ändrades.
    """
    if not set_cookie_headers:
        return None
    if "=" in current and ";" in current:
        # Full header-läge: merga
        cookies = parse_cookie_header(current)
        changed = False
        for raw in set_cookie_headers:
            first = raw.split(";", 1)[0].strip()
            name, _, value = first.partition("=")
            name = name.strip()
            if not name or name not in cookies:
                continue  # ignorera cookies vi inte hade från början
            if cookies[name] != value:
                cookies[name] = value
                changed = True
        if not changed:
            return None
        return "; ".join(f"{k}={v}" for k, v in cookies.items())
    # Enkel-värdes-läge: bara CS_UserSessionId
    for raw in set_cookie_headers:
        first = raw.split(";", 1)[0].strip()
        if first.startswith("CS_UserSessionId="):
            return first.split("=", 1)[1]
    return None


def log_admin_response(method: str, url: str, status: int, headers,
                       body_size: int) -> None:
    """Detaljerad logg av admin-svar för att fånga ev. cookie-rotation
    eller andra header-mönster. Vid Set-Cookie i svaret loggar vi varje
    cookie-rad med dess attribut (expires/max-age/path/samesite).
    Skip körlåt logging om allt är trivialt (200 utan Set-Cookie)."""
    set_cookies = headers.get_all("Set-Cookie") if hasattr(headers, "get_all") else []
    interesting_headers = ["Location", "WWW-Authenticate",
                           "X-Proxy-Destination", "Cache-Control",
                           "api-supported-versions", "Expires"]
    has_set_cookie = bool(set_cookies)
    is_error = status >= 400
    if not has_set_cookie and not is_error and status != 200:
        return  # tyst för 304 etc utan intressant info
    if not has_set_cookie and not is_error:
        # 200 OK utan Set-Cookie - en kort rad räcker
        print(f">> admin {method} {url} -> {status} ({body_size}b)",
              flush=True)
        return
    # Annars utförlig dump
    print(f">> admin {method} {url} -> {status} ({body_size}b)", flush=True)
    for h in interesting_headers:
        v = headers.get(h) if hasattr(headers, "get") else None
        if v:
            print(f"   {h}: {v}", flush=True)
    for sc in set_cookies or []:
        # Maskera värdet (visa bara namn + attribut), så loggen kan delas
        first, _, attrs = sc.partition(";")
        name, _, value = first.partition("=")
        masked = (value[:6] + "..." + value[-4:]) if len(value) > 12 else "(kort)"
        print(f"   Set-Cookie: {name}={masked};{attrs}", flush=True)


def keep_session_alive() -> None:
    """Bakgrundsloop som pingar admin-domänen var KEEPALIVE_INTERVAL
    sekund för att hålla sessionen vid liv (90 min idle timeout).
    Skip om sessionen är tom."""
    while True:
        time.sleep(KEEPALIVE_INTERVAL)
        if CS_SESSION:
            admin_ping("keepalive")


def discover_links() -> list[dict]:
    """Bygg lista av länkar för startsidan. Spec:ar och deras Swagger UI
    är inte med här - de länkas från relevanta modul-filer i docs/svk-apis.html
    istället för att skräpa ner portalen."""
    links = []

    if (ROOT / "docs" / "svk-apis.html").exists():
        links.append({
            "title": "API-dokumentation",
            "subtitle": "Modul-uppdelad referens för alla SVK-API:er",
            "url": "/docs/svk-apis.html",
            "kind": "docs",
        })

    # Pilot-projekt: undermappar med index.html på rotnivå.
    for entry in sorted(ROOT.iterdir()):
        if not entry.is_dir() or entry.name in EXCLUDE_DIRS or entry.name.startswith("."):
            continue
        if not (entry / "index.html").exists():
            continue
        readme = entry / "README.md"
        subtitle = ""
        readme_url = None
        if readme.exists():
            for line in readme.read_text(encoding="utf-8").splitlines()[:20]:
                line = line.strip()
                if line and not line.startswith("#"):
                    subtitle = line
                    break
            readme_url = f"/{entry.name}/README"
        links.append({
            "title": entry.name,
            "subtitle": subtitle or "Pilot-projekt",
            "url": f"/{entry.name}/",
            "readme_url": readme_url,
            "kind": "project",
        })

    return links


def render_index(links: list[dict]) -> bytes:
    parts = []
    for l in links:
        if l.get("readme_url"):
            # Pilot-projekt med README: använd div som container med
            # absolutpositionerad huvudlänk + en separat README-länk
            # ovanpå (a-i-a är inte giltig HTML).
            parts.append(
                f"""<div class="card card-{l['kind']}">
                      <a class="card-main" href="{l['url']}" aria-label="Öppna {l['title']}"></a>
                      <h2>{l['title']}</h2>
                      <p>{l['subtitle']}</p>
                      <span class="url">{l['url']}</span>
                      <a class="card-readme" href="{l['readme_url']}">README →</a>
                    </div>""")
        else:
            parts.append(
                f"""<a class="card card-{l['kind']}" href="{l['url']}">
                      <h2>{l['title']}</h2>
                      <p>{l['subtitle']}</p>
                      <span class="url">{l['url']}</span>
                    </a>""")
    html = TEMPLATE.replace("__CARDS__", "\n".join(parts))
    return html.encode("utf-8")


_README_CACHE: dict[str, tuple[float, bytes]] = {}


def render_readme(project: str) -> bytes | None:
    """Renderar <project>/README.md till en self-contained HTML-sida.
    Cachar på (mtime, html_bytes) så vi slipper bygga om vid varje request."""
    readme = ROOT / project / "README.md"
    if not readme.is_file():
        return None
    # Hindra path traversal: vi tillåter bara mappar direkt under ROOT.
    try:
        readme.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return None
    mtime = readme.stat().st_mtime
    cached = _README_CACHE.get(project)
    if cached and cached[0] == mtime:
        return cached[1]
    md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])
    body_html = md.convert(readme.read_text(encoding="utf-8"))
    title = f"{project} - README"
    page = README_TEMPLATE.replace("__TITLE__", html_lib.escape(title)) \
                          .replace("__PROJECT__", html_lib.escape(project)) \
                          .replace("__BODY__", body_html)
    out = page.encode("utf-8")
    _README_CACHE[project] = (mtime, out)
    return out


README_TEMPLATE = """<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Spectral:ital,wght@0,400;1,400&display=swap" rel="stylesheet">
<style>
:root { --beige: #FFEBE1; --black: #000; --wine: #7D0037; --gold: #BC8E4C;
        --muted: #6b5f5a; --line: rgba(125,0,55,0.2); }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "DM Sans", Arial, sans-serif; background: var(--beige);
       color: var(--black); line-height: 1.55;
       padding: clamp(20px, 4vw, 48px); }
.wrap { max-width: 760px; margin: 0 auto; }
.crumbs { font-size: 13px; color: var(--muted); margin-bottom: 24px; }
.crumbs a { color: var(--wine); text-decoration: none; }
.crumbs a:hover { text-decoration: underline; }
.actions { float: right; font-size: 13px; }
.actions a { color: var(--gold); text-decoration: none; margin-left: 12px;
             font-family: ui-monospace, monospace; }
.actions a:hover { color: var(--wine); }
h1, h2, h3, h4 { color: var(--wine); margin: 1.5em 0 0.5em; line-height: 1.2;
                 font-weight: 500; letter-spacing: -0.01em; }
h1 { font-size: clamp(28px, 4vw, 40px); margin-top: 0; }
h2 { font-size: 22px; padding-top: 0.5em; border-top: 1px solid var(--line); }
h3 { font-size: 17px; }
p, ul, ol, blockquote, table { margin: 0.75em 0; }
ul, ol { padding-left: 1.5em; }
li { margin: 0.25em 0; }
a { color: var(--wine); }
code { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 0.9em;
       background: rgba(125,0,55,0.08); padding: 1px 5px; border-radius: 2px; }
pre { background: #2b1418; color: #f5e6d8; padding: 12px 16px;
      border-radius: 4px; overflow-x: auto; font-size: 13px; line-height: 1.45; }
pre code { background: none; padding: 0; color: inherit; font-size: inherit; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--line); }
th { font-weight: 600; color: var(--wine); }
blockquote { border-left: 3px solid var(--wine); padding-left: 12px;
             color: var(--muted); }
hr { border: none; border-top: 1px solid var(--line); margin: 2em 0; }
</style>
</head>
<body>
<div class="wrap">
<div class="crumbs">
  <span class="actions"><a href="/__PROJECT__/">Öppna projekt →</a></span>
  <a href="/">← portalen</a> / <code>__PROJECT__/README.md</code>
</div>
__BODY__
</div>
</body>
</html>
"""


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
  position: relative;
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
.card-project h2::before { content: "🧪 "; }
/* Project-kort med README-länk: huvudlänken täcker hela kortet
   (z-index 0), README-länken ligger ovanpå (z-index 2). */
.card-main { position: absolute; inset: 0; z-index: 0;
             text-decoration: none; color: inherit; }
.card > h2, .card > p, .card > .url { position: relative; z-index: 1;
                                       pointer-events: none; }
.card-readme {
  position: absolute; bottom: 12px; right: 16px; z-index: 2;
  font-size: 12px; color: var(--gold); text-decoration: none;
  font-family: ui-monospace, monospace; letter-spacing: 0.02em;
  padding: 2px 6px; border-radius: 2px;
}
.card-readme:hover { background: var(--beige); color: var(--wine); }
.card:hover .card-readme { color: var(--beige); }
.card:hover .card-readme:hover { background: var(--beige); color: var(--wine); }
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
    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            body = render_index(discover_links())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            return
        # /<projekt>/README -> renderad README.md för pilot-projektet.
        if self.path.endswith("/README") or self.path.endswith("/README/"):
            project = self.path.strip("/").rsplit("/", 1)[0]
            if project and "/" not in project and project not in EXCLUDE_DIRS:
                body = render_readme(project)
                if body is not None:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_error(404, "README saknas för projektet")
                return
        if self.path == "/api/admin/_session":
            self._get_admin_session_status()
            return
        if self.path == "/api/admin/_churchcontext":
            self._proxy_churchcontext()
            return
        if self.path == "/osm-konsistenscheck/api/rebuild/status":
            self._get_rebuild_status()
            return
        if self.path.startswith(PROXY_PREFIX):
            self._proxy_churchcalendar()
            return
        if self.path.startswith(ADMIN_PROXY_PREFIX):
            self._proxy_admin("GET")
            return
        if self._svk_proxy_match():
            self._proxy_svk("GET")
            return
        super().do_GET()

    def do_PATCH(self) -> None:  # noqa: N802
        if self.path.startswith(ADMIN_PROXY_PREFIX):
            self._proxy_admin("PATCH")
            return
        if self._svk_proxy_match():
            self._proxy_svk("PATCH")
            return
        self.send_error(405, "Method not allowed")

    def do_PUT(self) -> None:  # noqa: N802
        if self.path.startswith(ADMIN_PROXY_PREFIX):
            self._proxy_admin("PUT")
            return
        if self._svk_proxy_match():
            self._proxy_svk("PUT")
            return
        self.send_error(405, "Method not allowed")

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path.startswith(ADMIN_PROXY_PREFIX):
            self._proxy_admin("DELETE")
            return
        if self._svk_proxy_match():
            self._proxy_svk("DELETE")
            return
        self.send_error(405, "Method not allowed")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/admin/_session":
            self._set_admin_session()
            return
        if self.path == "/api/admin/_session/ping":
            self._manual_ping()
            return
        if self.path == "/osm-konsistenscheck/api/rebuild":
            self._trigger_rebuild()
            return
        self.send_error(405, "Method not allowed")

    def _get_rebuild_status(self) -> None:
        with REBUILD_LOCK:
            body = json.dumps(REBUILD_STATE).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _trigger_rebuild(self) -> None:
        with REBUILD_LOCK:
            if REBUILD_STATE["status"] == "running":
                body = json.dumps(REBUILD_STATE).encode("utf-8")
                self.send_response(409)  # Conflict
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return

            # Nollställ och starta
            REBUILD_STATE.update({
                "status": "running",
                "step": "init",
                "step_index": 0,
                "started_at": datetime.now().isoformat(),
                "finished_at": None,
                "message": "Startar rebuild...",
                "last_error": None,
                "exit_code": None,
            })
            body = json.dumps(REBUILD_STATE).encode("utf-8")
            threading.Thread(target=run_rebuild, daemon=True).start()

        self.send_response(202)  # Accepted
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _manual_ping(self) -> None:
        status, text = admin_ping("manual")
        body = json.dumps({"status": status, "text": text}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _svk_proxy_match(self) -> bool:
        return any(self.path.startswith(p) for p in SVK_PROXY_ROUTES)

    def _proxy_churchcalendar(self) -> None:
        suffix = self.path[len(PROXY_PREFIX):].split("?", 1)[0]
        upstream = f"{PROXY_UPSTREAM}{suffix}?{urlencode({'apiKey': CHURCHCALENDAR_API_KEY})}"
        req = Request(upstream, headers={"User-Agent": "svk-api-playground"})
        try:
            with urlopen(req, timeout=15) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type", "application/json")
        except HTTPError as e:
            self.send_error(e.code, f"Upstream HTTP {e.code}: {e.reason}")
            return
        except URLError as e:
            self.send_error(502, f"Upstream error: {e.reason}")
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=600")
        self.end_headers()
        self.wfile.write(data)

    def _get_admin_session_status(self) -> None:
        body = json.dumps({
            "set": bool(CS_SESSION),
            "length": len(CS_SESSION),
            "preview": (CS_SESSION[:6] + "..." + CS_SESSION[-4:]) if CS_SESSION else "",
            "updated_at": CS_SESSION_UPDATED_AT or None,
            "last_pinged_at": CS_SESSION_LAST_PING_AT or None,
            "last_ping_status": CS_SESSION_LAST_PING_STATUS or None,
            "last_rotated_at": CS_SESSION_LAST_ROTATED_AT or None,
            "keepalive_interval_min": KEEPALIVE_INTERVAL // 60,
            "now": time.time(),
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _set_admin_session(self) -> None:
        global CS_SESSION
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length).decode("utf-8") if content_length else ""
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            self.send_error(400, "Ogiltig JSON")
            return
        new_session = (data.get("session") or "").strip()
        # Sanera: filtrera bort icke-printable ASCII (smyger sig in vid
        # copy-paste från terminaler med emoji-prompts som "🌐 ubuntu-ai").
        # HTTP-headers tillåter bara latin-1; vi tillåter bara printable
        # ASCII för säkerhets skull. Cookie-värden ska aldrig innehålla
        # specialtecken.
        new_session = "".join(c for c in new_session if 32 <= ord(c) < 127)
        if not new_session:
            CS_SESSION = ""
            body = b'{"ok":true,"cleared":true}'
        elif len(new_session) < 30:
            self.send_error(400, "För kort - antingen CS_UserSessionId-värdet "
                                 "eller en full cookie-header")
            return
        else:
            CS_SESSION = new_session
            body = json.dumps({"ok": True, "length": len(new_session)}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _proxy_churchcontext(self) -> None:
        # Specialfall: /churchcontext ligger utanför /webapi/api-v2/-prefixet
        # men är samma admin-domän + samma session-cookie.
        if not CS_SESSION:
            self.send_error(500, "Sätt CS_SESSION i .env eller via UI:t")
            return
        cookie_header = (
            CS_SESSION if "=" in CS_SESSION and ";" in CS_SESSION
            else f"CS_UserSessionId={CS_SESSION}"
        )
        req = Request("https://admin.svenskakyrkan.se/churchcontext", headers={
            "Cookie": cookie_header,
            "Origin": "https://admin.svenskakyrkan.se",
            "Referer": "https://admin.svenskakyrkan.se/",
            "User-Agent": "svk-api-playground",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/plain, */*",
        })
        try:
            with urlopen(req, timeout=15) as resp:
                data = resp.read()
                status = resp.status
        except HTTPError as e:
            err = e.read() if hasattr(e, "read") else b""
            self.send_response(e.code)
            self.send_header("Content-Type",
                             e.headers.get("Content-Type", "text/plain"))
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)
            return
        except URLError as e:
            self.send_error(502, f"Upstream error: {e.reason}")
            return
        # /churchcontext returnerar en JS-fil som börjar med
        # "var churchContext={...};" följt av annan JS-kod (funktioner
        # m.m.). Plocka ut första balanserade {...}-objektet och returnera
        # bara det som JSON.
        text = data.decode("utf-8", errors="replace")
        json_str = _extract_first_json_object(text)
        if json_str is None:
            self.send_error(502, "Kunde inte extrahera churchContext-objekt "
                                 "från upstream-svar")
            return
        data = json_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _proxy_admin(self, method: str) -> None:
        if not CS_SESSION:
            self.send_error(
                500,
                "Sätt CS_SESSION i .env (CS_UserSessionId från admin.svenskakyrkan.se)",
            )
            return
        rest = self.path[len(ADMIN_PROXY_PREFIX):]
        upstream_url = f"{ADMIN_UPSTREAM}{rest}"
        body = None
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length:
            body = self.rfile.read(content_length)
        # CS_SESSION kan vara antingen bara värdet av CS_UserSessionId
        # eller en fullständig cookie-header med flera cookies
        # ("name1=v1; name2=v2; ..."). Det senare behövs när auth-
        # cookien är HttpOnly och måste kopieras manuellt från DevTools.
        cookie_header = (
            CS_SESSION if "=" in CS_SESSION and ";" in CS_SESSION
            else f"CS_UserSessionId={CS_SESSION}"
        )
        headers = {
            "Cookie": cookie_header,
            "Origin": "https://admin.svenskakyrkan.se",
            "Referer": "https://admin.svenskakyrkan.se/",
            "User-Agent": "svk-api-playground",
            # ASP.NET avvisar ofta icke-XHR-requests för auth-skyddade
            # endpoints med generell 401. Browser-flödet sätter detta
            # automatiskt; vi måste explicit.
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/plain, */*",
        }
        if method in ("PUT", "POST", "PATCH"):
            headers["Prefer"] = "return=representation"
            if self.headers.get("Content-Type"):
                headers["Content-Type"] = self.headers["Content-Type"]
        req = Request(upstream_url, data=body, method=method, headers=headers)
        try:
            with urlopen(req, timeout=20) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type", "application/json")
                status = resp.status
                sc_list = resp.headers.get_all("Set-Cookie") or []
                rotated = apply_set_cookies(CS_SESSION, sc_list)
                if rotated:
                    update_cs_session(rotated, f"admin-proxy {method}")
                log_admin_response(method, upstream_url, status,
                                   resp.headers, len(data))
        except HTTPError as e:
            err_body = e.read() if hasattr(e, "read") else b""
            cookie_names = [c.split("=", 1)[0].strip() for c in cookie_header.split(";") if c.strip()]
            print(
                f"!! admin-proxy {method} {upstream_url} -> "
                f"HTTP {e.code} ({len(err_body)}b body, "
                f"cookies skickade: {cookie_names})",
                flush=True,
            )
            preview = err_body[:500].decode("utf-8", errors="replace")
            print(f"   body: {preview!r}", flush=True)
            # Logga relevanta upstream-headers för diagnostik
            for h in ("Location", "WWW-Authenticate", "Set-Cookie",
                      "X-Proxy-Destination"):
                v = e.headers.get(h) if e.headers else None
                if v:
                    print(f"   {h}: {v}", flush=True)
            self.send_response(e.code)
            self.send_header(
                "Content-Type", e.headers.get("Content-Type", "text/plain"),
            )
            self.send_header("Content-Length", str(len(err_body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(err_body)
            return
        except URLError as e:
            print(f"!! admin-proxy upstream-fel mot {upstream_url}: {e.reason}",
                  flush=True)
            self.send_error(502, f"Upstream error: {e.reason}")
            return
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _proxy_svk(self, method: str) -> None:
        if not SVK_API_KEY:
            self.send_error(500, "Sätt APIKEY_PROD i .env för SVK-proxy")
            return
        # Hitta matchande prefix
        for prefix, upstream_path in SVK_PROXY_ROUTES.items():
            if self.path.startswith(prefix):
                rest = self.path[len(prefix):]
                break
        else:
            self.send_error(404, "Okänd proxy-route")
            return
        # Behåll klientens query verbatim (redan URL-encodad) och appendera
        # vår apikey. Att decoda + re-encoda skulle dubbel-encoda värden.
        path_part, _, query_part = rest.partition("?")
        upstream_url = f"{SVK_UPSTREAM}{upstream_path}{path_part}"
        sep = "?"
        if query_part:
            upstream_url += f"?{query_part}"
            sep = "&"
        upstream_url += f"{sep}{urlencode({'apikey': SVK_API_KEY})}"

        body = None
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length:
            body = self.rfile.read(content_length)
        headers = {"User-Agent": "svk-api-playground"}
        if body and self.headers.get("Content-Type"):
            headers["Content-Type"] = self.headers["Content-Type"]
        req = Request(upstream_url, data=body, method=method, headers=headers)
        try:
            with urlopen(req, timeout=20) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type", "application/json")
                status = resp.status
                location = resp.headers.get("Location")
        except HTTPError as e:
            err_body = e.read() if hasattr(e, "read") else b""
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "text/plain"))
            self.send_header("Content-Length", str(len(err_body)))
            self.end_headers()
            self.wfile.write(err_body)
            return
        except URLError as e:
            self.send_error(502, f"Upstream error: {e.reason}")
            return
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        # Aldrig cacha SVK-API-svar - vi vill alltid se senaste data
        # under utveckling. Upstream sätter ev. egna cache-headers,
        # men vi överrider dem här.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        if location:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        # Mer kompakt loggning
        sys.stderr.write(f"{self.address_string()} {fmt % args}\n")


def main() -> int:
    os.chdir(ROOT)
    server = HTTPServer((HOST, PORT), Handler)
    url = f"http://localhost:{PORT}/"
    print(f">> svk-api-playground servar på {url}", flush=True)
    print(f">> root: {ROOT}", flush=True)
    print(f">> session keep-alive var {KEEPALIVE_INTERVAL // 60} min "
          f"mot {ADMIN_KEEPALIVE_URL}", flush=True)
    print(f">> Ctrl+C för att avsluta", flush=True)
    threading.Thread(target=keep_session_alive, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n>> avslutar", flush=True)
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
