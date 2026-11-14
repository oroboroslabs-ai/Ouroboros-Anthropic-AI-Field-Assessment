"""Refresh the reasoning column used by the second chart (Model Leaderboard).

Artificial Analysis publishes GPQA-Diamond per model inside each model page's
Next.js payload, including for models whose row on the public leaderboard ships
no scores. We read one model page (it embeds the whole comparison table), map
every slug to its GPQA-Diamond score and write `reasoning_index` (score x100)
back into field_data.json.

Rules:
  * existing models only - the model list is never extended
  * only `reasoning_index` is written; index/cost/tps/coding are untouched
  * a model whose slug is not published keeps its previous value

    python scripts/sync_reasoning.py
"""
import datetime
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "field_data.json"
PAGE = "https://artificialanalysis.ai/models/claude-opus-5"


def payload(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "accept": "text/html"})
    with urllib.request.urlopen(req, timeout=90) as r:
        html = r.read().decode("utf-8", "replace")
    return html.encode().decode("unicode_escape", errors="ignore")


def gpqa_by_slug(txt):
    out = {}
    for m in re.finditer(r'"slug":"([a-z0-9.\-]+)"', txt):
        slug = m.group(1)
        if slug in out:
            continue
        g = re.search(r'"gpqa":([0-9.]+)', txt[m.end():m.end() + 4000])
        if g:
            v = float(g.group(1))
            if 0 < v <= 1:
                out[slug] = v
    return out


def main():
    try:
        txt = payload(PAGE)
    except Exception as exc:
        print(f"fetch failed: {exc}")
        return 1
    table = gpqa_by_slug(txt)
    if not table:
        print("no GPQA values found - leaving field_data.json untouched")
        return 1

    feed = json.loads(OUT.read_text(encoding="utf-8"))
    filled, kept = 0, 0
    for name, rec in feed["models"].items():
        slug = rec.get("slug") or ""
        v = table.get(slug)
        if v is None:
            # fall back to the family slug (strip the effort suffix)
            base = re.sub(r"-(xhigh|high|medium|low|max|non-reasoning)$", "", slug)
            v = table.get(base)
        if v is None:
            kept += 1
            continue
        rec["reasoning_index"] = round(v * 100, 1)
        filled += 1

    feed["reasoning_source"] = {
        "source": "Artificial Analysis model pages",
        "evaluation": "GPQA-Diamond (x100)",
        "endpoint": PAGE,
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    OUT.write_text(json.dumps(feed, indent=1), encoding="utf-8")
    print(f"reasoning_index written for {filled} models ({kept} kept as-is)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
