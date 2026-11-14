"""Free AA connection: read the public Artificial Analysis leaderboard page.

The models leaderboard ships the full model table inside the page's Next.js
payload (no key, no paid tier). This script extracts it and rewrites
field_data.json, so every chart on the Field Assessment page auto-populates.

    python scripts/sync_aa_public.py

Fields written per model:
    index           artificial-analysis intelligence index
    reasoning_index gpqa-diamond score x100 (a reasoning evaluation)
    coding_index    terminalbench-hard score x100 (a coding/agentic evaluation)
    cost_per_task   intelligenceIndexCostPerTask when the page carries it
    tps             outputSpeed when the page carries it
"""
import datetime
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = "https://artificialanalysis.ai/leaderboards/models"
OUT = ROOT / "field_data.json"


def payload(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "accept": "text/html"})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", "replace")
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    return "".join(c.encode().decode("unicode_escape", errors="ignore") for c in chunks)


def _num(obj, key):
    v = obj.get(key)
    return v if isinstance(v, (int, float)) else None


def models_from(joined):
    out = {}
    for m in re.finditer(r'\{"slug":"[^"]+","name":"(?:[^"\\]|\\.)*"', joined):
        start = m.start()
        # take a generous slice, then trim to the matching closing brace of this object
        depth, end = 0, None
        for i in range(start, min(len(joined), start + 4000)):
            if joined[i] == "{":
                depth += 1
            elif joined[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if not end:
            continue
        try:
            obj = json.loads(joined[start:end])
        except Exception:
            continue
        name = obj.get("name") or obj.get("shortName")
        if not name:
            continue
        scores = obj.get("scores") or {}
        gpqa = scores.get("gpqa-diamond")
        tbench = scores.get("terminalbench-hard")
        rec = {
            "aa_name": name,
            "slug": obj.get("slug"),
            "index": _num(obj, "intelligenceIndex"),
            "reasoning_index": round(gpqa * 100, 1) if isinstance(gpqa, (int, float)) else None,
            "coding_index": round(tbench * 100, 1) if isinstance(tbench, (int, float)) else None,
            "cost_per_task": _num(obj, "intelligenceIndexCostPerTask"),
            "tps": _num(obj, "outputSpeed"),
        }
        if any(rec[k] is not None for k in ("index", "reasoning_index", "coding_index")):
            out[name] = rec
    return out


def main():
    try:
        joined = payload(PAGE)
    except Exception as exc:
        print(f"fetch failed: {exc}")
        return 1
    models = models_from(joined)
    if not models:
        print("no models found in the page payload - leaving field_data.json untouched")
        return 1
    feed = {
        "source": "Artificial Analysis public leaderboard (free, no key)",
        "endpoint": PAGE,
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "intelligence_index_version": "public",
        "pages_cached": ["models"],
        "models": models,
    }
    OUT.write_text(json.dumps(feed, indent=1), encoding="utf-8")
    print(f"wrote {len(models)} models from the public page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
