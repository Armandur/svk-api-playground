#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["markdown>=3.5", "pygments>=2.17"]
# ///
"""Bygg ett self-contained HTML-dokument från docs/modules/*.md med sidebar-nav.

Kör: `uv run scripts/build_docs.py` -> skapar docs/svk-apis.html.
"""

import re
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "docs" / "modules"
OUTPUT = ROOT / "docs" / "svk-apis.html"

ORDER = [
    "_readme",
    "_claude",
    "_overview",
    "_quickref",
    "_brand",
    "CALENDARAPI",
    "CHURCHCALENDAR",
    "ENHETSINFORMATION",
    "FORSAMLINGSKARTOR",
    "FORSAMLINGSSOK",
    "KBR",
    "PLATSER",
    "UNITAPI",
    "AMNESOMRADEN",
    "_deprecated",
    "_todo",
]

# Sektioner som ligger utanför docs/modules/. Mappar sektions-id till
# filsökväg (relativt ROOT) och en sökväg-etikett som visas i meta-raden.
EXTRA_SOURCES = {
    "_readme": (ROOT / "README.md", "README.md"),
    "_claude": (ROOT / "CLAUDE.md", "CLAUDE.md"),
}

LABELS = {
    "_readme": "README",
    "_claude": "CLAUDE.md",
    "_overview": "Översikt",
    "_quickref": "Quickref",
    "_brand": "Grafisk profil",
    "CALENDARAPI": "CalendarAPI",
    "CHURCHCALENDAR": "Kyrkoåret + bibeltexter",
    "ENHETSINFORMATION": "Enhetsinformation",
    "FORSAMLINGSKARTOR": "Församlingskartor",
    "FORSAMLINGSSOK": "Församlingssök (Flax)",
    "KBR": "Kyrkobyggnadsregistret",
    "PLATSER": "Platser",
    "UNITAPI": "UnitAPI (Enheter v2)",
    "AMNESOMRADEN": "Ämnesområden",
    "_deprecated": "Ersatt / saknas publikt",
    "_todo": "TODO + projektidéer",
}

MD_EXTENSIONS = ["fenced_code", "tables", "codehilite"]
MD_CONFIG = {"codehilite": {"guess_lang": False, "css_class": "highlight"}}


def section_source(name: str) -> tuple[Path, str]:
    if name in EXTRA_SOURCES:
        return EXTRA_SOURCES[name]
    path = MODULES / f"{name}.md"
    return path, f"docs/modules/{name}.md"


def render_section(name: str) -> tuple[str, str, str]:
    path, meta = section_source(name)
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = m.group(1).strip() if m else name
    # Konvertera md-länkar mellan moduler till in-page anchors. Drop fragment;
    # alla länkar går till toppen av respektive modul-sektion.
    text = re.sub(r"\]\((\w+)\.md(?:#[^)]*)?\)", r"](#\1)", text)
    # Rotfiler refererar till CLAUDE.md/README.md utan path - rewrite till
    # respektive ankare så in-page-länkar fortsätter funka.
    text = re.sub(r"\]\(CLAUDE\.md\)", r"](#_claude)", text)
    text = re.sub(r"\]\(README\.md\)", r"](#_readme)", text)
    md = markdown.Markdown(extensions=MD_EXTENSIONS, extension_configs=MD_CONFIG)
    return title, md.convert(text), meta


def main() -> None:
    sections = [(n, *render_section(n)) for n in ORDER]
    nav = "\n".join(
        f'<li><a href="#{n}"><span class="lbl">{LABELS.get(n, n)}</span>'
        f'<span class="t">{title}</span></a></li>'
        for n, title, _, _ in sections
    )
    article = "\n".join(
        f'<section id="{n}"><div class="meta">{meta}</div>{html}</section>'
        for n, _, html, meta in sections
    )
    pygments_css = HtmlFormatter(style="default").get_style_defs(".highlight")

    out = (
        TEMPLATE.replace("__NAV__", nav)
        .replace("__ARTICLE__", article)
        .replace("__PYGMENTS_CSS__", pygments_css)
    )
    OUTPUT.write_text(out, encoding="utf-8")
    print(f"Skrev {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size // 1024} KB)")


TEMPLATE = """<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<title>Svenska kyrkans API:er — dokumentation</title>
<style>
:root {
  --bg:#fafafa; --fg:#222; --muted:#777; --accent:#0066cc;
  --border:#e2e2e2; --code-bg:#f4f4f4;
}
* { box-sizing:border-box; }
html,body { margin:0; padding:0; height:100%; background:var(--bg); color:var(--fg);
            font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
.layout { display:flex; min-height:100vh; }
nav { width:280px; background:#fff; border-right:1px solid var(--border);
      padding:16px 0; position:sticky; top:0; height:100vh; overflow-y:auto;
      flex-shrink:0; }
nav h1 { font-size:13px; margin:0 16px 12px; color:var(--muted);
         text-transform:uppercase; letter-spacing:0.5px; }
nav ul { list-style:none; margin:0; padding:0; }
nav li a { display:block; padding:10px 16px; color:var(--fg); text-decoration:none;
           border-left:3px solid transparent; }
nav li a:hover, nav li a.active { background:#eef5ff; border-left-color:var(--accent);
                                  color:var(--accent); }
nav .lbl { display:block; font-weight:500; }
nav .t { display:block; font-size:11px; color:var(--muted); margin-top:2px;
         white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
main { flex:1; padding:32px 48px; max-width:980px; }
section { margin-bottom:64px; padding-bottom:32px; border-bottom:1px solid var(--border); }
section:last-child { border-bottom:none; }
section .meta { font-size:11px; color:var(--muted); font-family:ui-monospace,monospace;
                margin-bottom:8px; }
h1 { font-size:28px; margin:0 0 16px; }
h2 { font-size:21px; margin:32px 0 12px; padding-top:8px; }
h3 { font-size:16px; margin:24px 0 8px; }
h1, h2, h3 { font-weight:600; }
table { border-collapse:collapse; margin:12px 0; }
th, td { padding:6px 12px; border:1px solid var(--border); text-align:left;
         vertical-align:top; }
th { background:#f5f5f5; }
code { background:var(--code-bg); padding:2px 5px; border-radius:3px; font-size:13px;
       font-family:ui-monospace,SFMono-Regular,monospace; }
pre { background:#fdfdfd; border:1px solid var(--border); padding:12px 16px;
      border-radius:4px; overflow-x:auto; font-size:13px; }
pre code { background:none; padding:0; }
blockquote { border-left:4px solid var(--accent); margin:12px 0; padding:8px 16px;
             background:#eef5ff; color:#333; }
blockquote p:first-child { margin-top:0; }
blockquote p:last-child { margin-bottom:0; }
a { color:var(--accent); }
hr { border:none; border-top:1px solid var(--border); margin:24px 0; }
__PYGMENTS_CSS__
</style>
</head>
<body>
<div class="layout">
<nav>
<h1>Svenska kyrkans API:er</h1>
<ul>
__NAV__
</ul>
</nav>
<main>
__ARTICLE__
</main>
</div>
<script>
// Markera aktiv sidebar-länk vid scroll (scrollspy)
const sections = document.querySelectorAll('section');
const links = document.querySelectorAll('nav li a');
const obs = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      links.forEach(l => l.classList.toggle(
        'active', l.getAttribute('href') === '#' + e.target.id));
    }
  });
}, { rootMargin: '-20% 0px -70% 0px' });
sections.forEach(s => obs.observe(s));
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
