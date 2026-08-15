#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Slå upp varje KBR-kyrkas identitetRAA mot K-samsök (raa/bbr/{id})
och klassificera om namnen stämmer överens.

Output: data/report.json med summary, results och duplicates.

Kör (efter fetch_kbr.py):
  uv run kbr-raa/check_ksamsok.py
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KBR_FILE = ROOT / "data" / "kbr.json"
OUT_FILE = ROOT / "data" / "report.json"
KSAMSOK_BASE = "https://kulturarvsdata.se/raa/bbr"
WORKERS = 20
MATCH_THRESHOLD = 0.80


def normalize(name: str) -> str:
    """Normalisera namn för jämförelse: uppercase, expandera 'S:T'/'S:A',
    'och' -> '&', strippa allt utom bokstäver/siffror/mellanslag."""
    if not name:
        return ""
    n = name.upper().strip()
    n = n.replace("S:T ", "SANKT ").replace("S:TA ", "SANKTA ")
    n = n.replace("ST. ", "SANKT ").replace("STA. ", "SANKTA ")
    n = n.replace(" OCH ", " & ")
    n = re.sub(r"[^\w\s]", " ", n, flags=re.UNICODE)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def fetch_bbr(bbr_id: str) -> dict:
    url = f"{KSAMSOK_BASE}/{bbr_id}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"status": "not_found"}
        return {"status": "error", "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

    entity = None
    target_id = f"http://kulturarvsdata.se/raa/bbr/{bbr_id}"
    for node in data.get("@graph", []):
        if node.get("@id") == target_id:
            entity = node
            break
    if not entity:
        return {"status": "error", "error": "no entity node"}

    label = entity.get("ns5:itemLabel") or entity.get("ns5:itemTitle")
    if isinstance(label, dict):
        label = label.get("@value")
    elif isinstance(label, list):
        for v in label:
            if isinstance(v, str):
                label = v
                break
            if isinstance(v, dict) and v.get("@value"):
                label = v["@value"]
                break

    return {"status": "ok", "label": label or ""}


def check_one(row: dict) -> dict:
    bbr_id = row.get("identitetRAA")
    if not bbr_id:
        return {
            "kbr_id": row["id"],
            "kbr_namn": row.get("namn"),
            "identitetRAA": None,
            "status": "missing_id",
        }

    result = fetch_bbr(bbr_id)
    base = {
        "kbr_id": row["id"],
        "kbr_namn": row.get("namn"),
        "identitetRAA": bbr_id,
        "stift": row.get("stift"),
        "agandeEnhet": row.get("agandeEnhet"),
    }

    if result["status"] != "ok":
        return {**base, **result}

    ksamsok_namn = result["label"]
    sim = similarity(row.get("namn", ""), ksamsok_namn)
    base["ksamsok_namn"] = ksamsok_namn
    base["similarity"] = round(sim, 3)
    base["status"] = "match" if sim >= MATCH_THRESHOLD else "mismatch"
    return base


def main() -> None:
    if not KBR_FILE.exists():
        sys.exit(f"Kör fetch_kbr.py först - {KBR_FILE} saknas.")

    kbr = json.loads(KBR_FILE.read_text(encoding="utf-8"))
    rows = kbr["kyrkor"]
    print(f"Kollar {len(rows)} kyrkor mot K-samsök med {WORKERS} workers...", flush=True)

    raa_to_kbr: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        rid = row.get("identitetRAA")
        if rid:
            raa_to_kbr[rid].append(row["id"])
    duplicates = [
        {"identitetRAA": rid, "kbr_ids": ids}
        for rid, ids in raa_to_kbr.items() if len(ids) > 1
    ]

    results: list[dict] = []
    start = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(check_one, r): r for r in rows}
        for fut in as_completed(futures):
            results.append(fut.result())
            done += 1
            if done % 100 == 0 or done == len(rows):
                elapsed = time.time() - start
                rate = done / elapsed if elapsed else 0
                eta = (len(rows) - done) / rate if rate else 0
                print(f"  {done:4d}/{len(rows)}  {rate:.1f}/s  ETA {eta:.0f}s", flush=True)

    summary = defaultdict(int)
    for r in results:
        summary[r["status"]] += 1
    summary["duplicate_groups"] = len(duplicates)

    results.sort(key=lambda r: (r["status"], r.get("similarity", 1.0), r["kbr_id"]))

    payload = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "match_threshold": MATCH_THRESHOLD,
        "summary": dict(summary),
        "duplicates": duplicates,
        "results": results,
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSkrev {OUT_FILE.relative_to(ROOT.parent)}")
    print("Summary:")
    for k, v in sorted(summary.items()):
        print(f"  {k:20s} {v}")


if __name__ == "__main__":
    main()
