"""Refresh coding score history for the Field Assessment coding line chart.

Source: aistupidlevel.info history API (free, keyed) - the board= coding series.
Falls back to TensorFeed's benchmark series API when TENSORFEED_KEY is set.

    AISTUPIDLEVEL_KEY=... python scripts/sync_coding.py

Writes coding_history.json in the shape the page reads:

    {"generated": "...", "source": "...", "models": {"<slug>": [{"date": "YYYY-MM-DD", "score": 62.1}]}}

Without a key it exits 0 and leaves the file untouched, so the daily job never
breaks the site.
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "coding_history.json"
SLUGS = ["claude-opus-5", "claude-sonnet-5-5", "gpt-6-astra", "gemini-4-argon",
         "grok-4-7", "kimi-k3", "deepseek-v4-1", "glm-5-3", "qwen3-8", "minimax-m3"]


def get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def aistupidlevel(slug, key, period="1m"):
    url = ("https://aistupidlevel.info/api/v1/models/"
           + urllib.parse.quote(slug) + "/history?period=" + period + "&sortBy=coding")
    body = get(url, {"x-api-key": key, "accept": "application/json"})
    points = body.get("history") or body.get("points") or body.get("data") or []
    out = []
    for p in points:
        d, sc = p.get("date") or p.get("day") or p.get("timestamp"), p.get("score") or p.get("value")
        if d and sc is not None:
            out.append({"date": str(d)[:10], "score": sc})
    return sorted(out, key=lambda p: p["date"])


def main():
    key = os.environ.get("AISTUPIDLEVEL_KEY", "").strip()
    tf = os.environ.get("TENSORFEED_KEY", "").strip()
    if not key and not tf:
        print("no coding-history API key set - leaving coding_history.json untouched")
        return 0

    models, source = {}, None
    for slug in SLUGS:
        try:
            if key:
                pts = aistupidlevel(slug, key)
                source = source or "aistupidlevel.info"
            else:
                url = ("https://api.tensorfeed.io/api/premium/history/benchmarks/series?swe_bench="
                       + urllib.parse.quote(slug) + "&from=2026-01-01")
                body = get(url, {"Authorization": "Bearer " + tf, "accept": "application/json"})
                pts = [{"date": str(p.get("date"))[:10], "score": p.get("score")}
                       for p in (body.get("points") or []) if p.get("date") and p.get("score") is not None]
                source = source or "tensorfeed"
            if pts:
                models[slug] = pts
        except Exception as exc:
            print(f"  {slug}: {exc}")

    if not models:
        print("no coding history returned - keeping the old file")
        return 0

    OUT.write_text(json.dumps({
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": source,
        "models": models,
    }, indent=1), encoding="utf-8")
    print(f"wrote coding history for {len(models)} models from {source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
