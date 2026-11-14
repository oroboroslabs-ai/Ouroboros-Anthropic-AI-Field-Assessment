"""Refresh the coding score history for the Field Assessment coding line chart.

Source: aistupidlevel.info history API (keyed, 10 requests/day).

    X-API-Key: $ASL_DATA_KEY  ->  /api/v1/models/:id/history?period=7d

The page reads coding_history.json in this shape:

    {"generated": "...", "source": "aistupidlevel.info", "period": "7d",
     "models": {"<display name>": [{"date": "YYYY-MM-DD", "score": 94}, ...]}}

Only the models already published on the dashboard are requested - the chart
never introduces a model that is not on the list. The daily quota is 10, so the
request set is deliberately small; raw responses are cached for 6 hours under
.cache/asl/ so a re-run does not burn quota.

Without ASL_DATA_KEY the file is left untouched and the command exits 0.
"""
import datetime
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "coding_history.json"
CACHE = ROOT / ".cache" / "asl"
BASE = "https://aistupidlevel.info/api/v1/models"
PERIOD = "7d"
PAUSE = 62          # seconds between calls - the feed rate-limits at ~60s
CACHE_HOURS = 6

# (aistupidlevel model id, display name used on the dashboard)
MODELS = [
    ("281", "Claude Opus 5"),
    ("286", "Claude Fable 5.1"),
    ("289", "GPT-6 Astra"),
    ("297", "GPT-6.1 Sol"),
    ("287", "Gemini 3.8 Flash"),
]


def fetch(url, key):
    req = urllib.request.Request(url, headers={"X-API-Key": key, "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def cached(mid):
    p = CACHE / f"{mid}.json"
    if not p.exists():
        return None
    age = time.time() - p.stat().st_mtime
    if age > CACHE_HOURS * 3600:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def daily(points):
    """Collapse the 4-hourly series to one score per calendar day (last wins)."""
    by_day = {}
    for p in points:
        ts = str(p.get("timestamp") or "")
        score = p.get("score")
        if len(ts) < 10 or score is None:
            continue
        by_day[ts[:10]] = score
    return [{"date": d, "score": by_day[d]} for d in sorted(by_day)]


def main():
    key = (os.environ.get("ASL_DATA_KEY") or os.environ.get("AISTUPIDLEVEL_KEY") or "").strip()
    if not key:
        print("ASL_DATA_KEY not set - leaving coding_history.json untouched")
        return 0

    CACHE.mkdir(parents=True, exist_ok=True)
    models, calls, attempts = {}, 0, 0
    for mid, name in MODELS:
        body = cached(mid)
        if body is None:
            # the feed rate-limits at roughly one request per minute and counts
            # every attempt, so pause before each call, including after a 429
            if attempts:
                time.sleep(PAUSE)
            attempts += 1
            try:
                body = fetch(f"{BASE}/{mid}/history?period={PERIOD}", key)
                calls += 1
                (CACHE / f"{mid}.json").write_text(json.dumps(body), encoding="utf-8")
            except urllib.error.HTTPError as exc:
                print(f"  {name} ({mid}): HTTP {exc.code}")
                continue
            except Exception as exc:
                print(f"  {name} ({mid}): {exc}")
                continue
        pts = daily(body.get("data") or [])
        if pts:
            models[name] = pts

    if not models:
        print("no coding history returned - keeping the old file")
        return 0

    OUT.write_text(json.dumps({
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "aistupidlevel.info",
        "period": PERIOD,
        "models": models,
    }, indent=1), encoding="utf-8")
    print(f"wrote {len(models)} coding series ({calls} live calls, {len(MODELS) - calls} cached)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
