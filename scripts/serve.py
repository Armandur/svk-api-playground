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

import json
import os
import sys
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("SVK_PORT", "8088"))
HOST = os.environ.get("SVK_HOST", "0.0.0.0")

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
            new_session = extract_session_from_headers(resp.headers)
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


def extract_session_from_headers(headers) -> str | None:
    """Plocka ut CS_UserSessionId från ev. Set-Cookie-headers."""
    cookies = headers.get_all("Set-Cookie") if hasattr(headers, "get_all") else []
    for raw in cookies or []:
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

    # OpenAPI-specs i docs/specs/. Föredra HTML-wrapper (Swagger UI) framför
    # rå JSON eftersom det ger en användbar interaktiv vy.
    specs_dir = ROOT / "docs" / "specs"
    if specs_dir.is_dir():
        html_wrappers = {p.stem for p in specs_dir.glob("*.html")}
        for spec in sorted(specs_dir.glob("*.json")):
            base = spec.stem.replace(".openapi", "")
            size_kb = spec.stat().st_size // 1024
            if base in html_wrappers:
                links.append({
                    "title": base,
                    "subtitle": f"OpenAPI-spec via Swagger UI ({size_kb} KB)",
                    "url": f"/docs/specs/{base}.html",
                    "kind": "spec",
                })
            else:
                links.append({
                    "title": spec.stem,
                    "subtitle": f"OpenAPI-spec ({size_kb} KB) - rå JSON",
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
        if self.path == "/api/admin/_session":
            self._get_admin_session_status()
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
        self.send_error(405, "Method not allowed")

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
                rotated = extract_session_from_headers(resp.headers)
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
