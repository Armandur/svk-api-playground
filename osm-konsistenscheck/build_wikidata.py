#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Hämtar alla Wikidata-Q-IDs som tillhör Svenska kyrkans stift via P708
(diocese) och skriver som data/wikidata_svk_set.json.

build_diff.py berikar sedan osm_only-features vars wikidata-tagg finns i
setet med properties.likely_svk_miss = true. Det flyttar troliga SVK-
missar från "annan denomination"-bucket till "kanske saknas i SVK Platser".

En enda SPARQL-query räcker (~2 s) eftersom SvK-stiften är 13 fasta
Q-IDs - vi hämtar alla items som pekar mot dem, inte tvärtom.

Kör: uv run osm-konsistenscheck/build_wikidata.py
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "wikidata_svk_set.json"
SPARQL_URL = "https://query.wikidata.org/sparql"

# 13 nuvarande Svenska kyrkans stift (Q-IDs från Wikidata).
# Borgå (finskt) och Kalmar (avskaffat 1915) ingår inte.
SVK_DIOCESE_QIDS = [
    "Q869379",   # Göteborgs stift
    "Q869583",   # Härnösands stift
    "Q870351",   # Karlstads stift
    "Q871289",   # Linköpings stift
    "Q871517",   # Luleå stift
    "Q871533",   # Lunds stift
    "Q876632",   # Skara stift
    "Q876775",   # Stockholms stift
    "Q876816",   # Strängnäs stift
    "Q877677",   # Uppsala stift
    "Q877946",   # Visby stift
    "Q877972",   # Västerås stift
    "Q877980",   # Växjö stift
]


def fetch_svk_items() -> list[dict]:
    diocese_values = " ".join(f"wd:{q}" for q in SVK_DIOCESE_QIDS)
    query = f"""
    SELECT ?item ?diocese ?dioceseLabel WHERE {{
      VALUES ?diocese {{ {diocese_values} }}
      ?item wdt:P708 ?diocese.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language 'sv,en'. }}
    }}
    """
    url = f"{SPARQL_URL}?{urllib.parse.urlencode({'query': query, 'format': 'json'})}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "svk-api-playground/0.1 (rasmus.pettersson.vik@gmail.com)",
        "Accept": "application/sparql-results+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["results"]["bindings"]
    except HTTPError as e:
        raise SystemExit(f"Wikidata SPARQL HTTP {e.code}: {e.reason}")
    except URLError as e:
        raise SystemExit(f"Wikidata SPARQL nätverksfel: {e.reason}")


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    print("Hämtar SvK-stiftens kyrkor från Wikidata SPARQL...", flush=True)
    bindings = fetch_svk_items()
    items: dict[str, str] = {}
    for b in bindings:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        diocese_label = b.get("dioceseLabel", {}).get("value", "")
        # Om samma item taggat med flera stift (sällsynt), behåll första.
        items.setdefault(qid, diocese_label)
    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "diocese_qids": SVK_DIOCESE_QIDS,
        "count": len(items),
        "items": items,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"Skrev {OUT.relative_to(ROOT)} ({len(items)} Q-IDs i SvK-stift)",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
