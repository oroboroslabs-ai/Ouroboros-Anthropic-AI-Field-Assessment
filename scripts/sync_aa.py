"""Merge the Artificial Analysis API v2 feed into field_data.json.

The page reads field_data.json at load time. This script refreshes the numbers
for the models already on the dashboard - index, coding index, cost per task,
tokens/s - and never adds or removes a model. The curated list is the product;
the feed only updates it.

    AA_API_KEY=... python scripts/sync_aa.py

Without a key it leaves the existing files untouched and exits 0, so a
scheduled run never breaks the site.
"""
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "field_data.json"
CACHE = ROOT / "aa_cache.json"
API = "https://artificialanalysis.ai/api/v2/language/models/free"

FIELDS = [
    ("index", "artificial_analysis_intelligence_index"),
    ("coding_index", "artificial_analysis_coding_index"),
    ("agentic_index", "artificial_analysis_agentic_index"),
]


def get(url, key):
    req = urllib.request.Request(url, headers={"x-api-key": key, "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def norm(t):
    return re.sub(r"[^a-z0-9.]", "", re.sub(r"\(.*?\)", "", str(t).lower()))


def main():
    key = os.environ.get("AA_API_KEY", "").strip()
    if not key:
        print("AA_API_KEY not set - leaving field_data.json as is")
        return 0

    pages, api_models, version = {}, [], None
    page = 1
    while True:
        body = get(f"{API}?page={page}", key)
        version = version or body.get("intelligence_index_version")
        pages[str(page)] = body
        for m in body.get("data", []):
            ev = m.get("evaluations") or {}
            api_models.append({
                "name": m.get("name"),
                "slug": m.get("slug"),
                "evaluations": ev,
                "cost": m.get("artificial_analysis_intelligence_index_cost"),
                "tps": (m.get("performance") or {}).get("median_output_tokens_per_second"),
            })
        if not (body.get("pagination") or {}).get("has_more"):
            break
        page += 1
        if page > 20:
            break

    by_slug = {m["slug"]: m for m in api_models if m.get("slug")}
    by_name = {}
    for m in api_models:
        by_name.setdefault(norm(m.get("name")), m)

    feed = json.loads(OUT.read_text(encoding="utf-8"))
    touched = 0
    for name, rec in feed["models"].items():
        hit = by_slug.get(rec.get("slug")) or by_name.get(norm(rec.get("aa_name") or name))
        if not hit:
            print(f"  {name}: not in the feed - kept as is")
            continue
        for local, ev in FIELDS:
            v = hit["evaluations"].get(ev)
            if v is not None:
                rec[local] = v
        if hit.get("cost") is not None:
            rec["cost_per_task"] = hit["cost"]
        if hit.get("tps") is not None:
            rec["tps"] = hit["tps"]
        rec["slug"] = rec.get("slug") or hit.get("slug")
        touched += 1

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    feed["source"] = "Artificial Analysis API v2 + public model pages"
    feed["endpoint"] = API
    feed["fetched_at"] = now
    if version:
        feed["intelligence_index_version"] = version
    feed["pages_cached"] = sorted(pages, key=int)

    OUT.write_text(json.dumps(feed, indent=1), encoding="utf-8")
    CACHE.write_text(json.dumps({"pages": pages}, indent=1), encoding="utf-8")
    print(f"updated {touched}/{len(feed['models'])} curated models from {len(pages)} pages at {now}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
