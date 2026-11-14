"""Refresh the Field Assessment data from the Artificial Analysis API v2.

The page reads field_data.json at load time. This script regenerates it (and
aa_cache.json) from the AA API so every chart auto-populates.

    AA_API_KEY=... python scripts/sync_aa.py

Without a key it leaves the existing files untouched and exits 0, so a
scheduled run never breaks the site.
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://artificialanalysis.ai/api/v2/language/models/free"


def get(url, key):
    req = urllib.request.Request(url, headers={"x-api-key": key, "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    key = os.environ.get("AA_API_KEY", "").strip()
    if not key:
        print("AA_API_KEY not set - leaving field_data.json as is")
        return 0

    pages, models, version = {}, {}, None
    page = 1
    while True:
        body = get(f"{API}?page={page}", key)
        version = version or body.get("intelligence_index_version")
        pages[str(page)] = body
        for m in body.get("data", []):
            ev = m.get("evaluations") or {}
            models[m.get("name") or m.get("slug")] = {
                "aa_name": m.get("name"),
                "slug": m.get("slug"),
                "index": ev.get("artificial_analysis_intelligence_index"),
                "coding_index": ev.get("artificial_analysis_coding_index"),
                "agentic_index": ev.get("artificial_analysis_agentic_index"),
                "cost_per_task": m.get("artificial_analysis_intelligence_index_cost"),
                "tps": (m.get("performance") or {}).get("median_output_tokens_per_second"),
            }
        if not (body.get("pagination") or {}).get("has_more"):
            break
        page += 1
        if page > 20:
            break

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    feed = {
        "source": "Artificial Analysis API v2",
        "endpoint": API,
        "fetched_at": now,
        "intelligence_index_version": version,
        "pages_cached": sorted(pages, key=int),
        "models": models,
    }
    (ROOT / "field_data.json").write_text(json.dumps(feed, indent=1), encoding="utf-8")
    (ROOT / "aa_cache.json").write_text(json.dumps({"pages": pages}, indent=1), encoding="utf-8")
    print(f"wrote {len(models)} models from {len(pages)} pages at {now}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
