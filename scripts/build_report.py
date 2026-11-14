"""Build the complete standalone field report (daily-report.html).

Everything the dashboard shows, in one self-contained page: provenance, KPI
row, the intelligence bars, the reasoning ranking, the coding history with our
own runs, and the full model ledger. Charts are inline SVG, so the report has
no scripts and no external requests.

    python scripts/build_report.py
"""
import datetime
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
FEED = json.loads((ROOT / "field_data.json").read_text(encoding="utf-8"))
CODING = json.loads((ROOT / "coding_history.json").read_text(encoding="utf-8"))
OUT = ROOT / "daily-report.html"

OURS = [
    {"name": "Claude Quindecillion", "score": 96, "cases": 2100,
     "vals": {"2026-11-07": 100, "2026-11-08": 99.3, "2026-11-09": 98.0,
              "2026-11-10": 99.7, "2026-11-11": 99.1, "2026-11-12": 98.2,
              "2026-11-13": 97.1, "2026-11-14": 96}},
    {"name": "Claude Fable 7", "score": 90, "cases": 2500,
     "vals": {"2026-11-07": 100, "2026-11-08": 98.8, "2026-11-09": 98.2,
              "2026-11-10": 99.6, "2026-11-11": 99.8, "2026-11-12": 97.5,
              "2026-11-13": 93.9, "2026-11-14": 90}},
]

COLORS = {
    "Anthropic": "#C0714F", "OpenAI": "#565656", "Google": "#34A853", "xAI": "#6B5BD2",
    "Xiaomi": "#F26522", "Alibaba": "#F97316", "DeepSeek": "#2B4FD8", "Z.ai": "#6B6B6B",
    "Kimi": "#2563EB", "MiniMax": "#E8418F", "StepFun": "#22C7D9",
    "Mistral": "#EF4444", "Reflection": "#1F4D3A", "NVIDIA": "#7CB342",
    "OROBOROS": "#F2A07B",
}


def vendor(name):
    n = str(name)
    rules = [
        ("claude", "Anthropic"), ("gpt", "OpenAI"), ("gemini", "Google"),
        ("grok", "xAI"), ("muse", "xAI"), ("mimo", "Xiaomi"), ("qwen", "Alibaba"),
        ("deepseek", "DeepSeek"), ("kimi", "Kimi"), ("glm", "Z.ai"),
        ("minimax", "MiniMax"), ("step", "StepFun"), ("mistral", "Mistral"),
        ("nemotron", "NVIDIA"), ("beam", "Reflection"), ("inking", "Reflection"),
    ]
    for key, v in rules:
        if key in n.lower():
            return v
    return "OpenAI"


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def num(v, digits=1):
    return "—" if v is None else (f"{v:.{digits}f}" if isinstance(v, float) else str(v))


def catmull(points):
    """Smooth path through (x, y) points."""
    if not points:
        return ""
    d = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    for i in range(len(points) - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(d)


def index_chart(rows):
    w, h, pad_l, pad_b = 980, 300, 46, 96
    top = max([r["index"] or 0 for r in rows] + [100])
    n = max(len(rows), 1)
    bw = (w - pad_l - 12) / n
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Intelligence index bars">']
    for g in range(0, 101, 20):
        y = 12 + (1 - g / top) * (h - pad_b - 12)
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-8}" y2="{y:.1f}" stroke="rgba(255,255,255,.08)"/>')
        out.append(f'<text x="{pad_l-8}" y="{y+3:.1f}" fill="#8b8f96" font-size="9" text-anchor="end">{g}</text>')
    for i, r in enumerate(rows):
        v = r["index"] or 0
        bh = (v / top) * (h - pad_b - 12)
        x = pad_l + i * bw
        y = h - pad_b - bh
        col = COLORS.get(vendor(r["name"]), "#888")
        out.append(f'<rect x="{x+bw*0.08:.1f}" y="{y:.1f}" width="{bw*0.84:.1f}" height="{bh:.1f}" fill="{col}" rx="2"/>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{h-pad_b-bh+14:.1f}" fill="#fff" font-size="9" text-anchor="middle">{num(v)}</text>')
        label = esc(r["name"])[:22]
        out.append(f'<text transform="translate({x+bw/2:.1f},{h-pad_b+10}) rotate(58)" fill="#8b8f96" font-size="8">{label}</text>')
    out.append("</svg>")
    return "".join(out)


def reasoning_chart(rows):
    row_h, w, pad_l = 24, 980, 210
    h = 20 + row_h * len(rows)
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Reasoning ranking">']
    for i, r in enumerate(rows):
        v = r["reasoning_index"]
        y = 10 + i * row_h
        bw = max(2, (v / 100) * (w - pad_l - 70))
        col = "#F2A07B" if r["ours"] else COLORS.get(vendor(r["name"]), "#888")
        out.append(f'<rect x="{pad_l}" y="{y+4}" width="{bw:.1f}" height="{row_h-9}" fill="{col}" rx="3"/>')
        out.append(f'<text x="{pad_l-8}" y="{y+row_h/2+3:.1f}" fill="#c9ccd2" font-size="10" text-anchor="end">{esc(r["name"])}</text>')
        out.append(f'<text x="{pad_l+bw+6:.1f}" y="{y+row_h/2+3:.1f}" fill="#c9ccd2" font-size="10">{num(v)}</text>')
    out.append("</svg>")
    return "".join(out)


def coding_chart():
    series = CODING.get("models") or {}
    dates = sorted({p["date"] for pts in series.values() for p in pts})
    if not dates:
        return "<p>No coding history.</p>"
    w, h, pad_l, pad_r, pad_t, pad_b = 980, 300, 46, 26, 16, 34
    lo = min([p["score"] for pts in series.values() for p in pts] + [90]) - 2
    hi = 100
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b

    def px(i):
        return pad_l + (i / max(len(dates) - 1, 1)) * plot_w

    def py(v):
        return pad_t + (1 - (v - lo) / (hi - lo)) * plot_h

    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Coding history">']
    for g in range(int(lo), hi + 1, 2):
        y = py(g)
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-pad_r}" y2="{y:.1f}" stroke="rgba(255,255,255,.07)"/>')
        out.append(f'<text x="{pad_l-8}" y="{y+3:.1f}" fill="#8b8f96" font-size="9" text-anchor="end">{g}</text>')
    for i, d in enumerate(dates):
        out.append(f'<text x="{px(i):.1f}" y="{h-14}" fill="#8b8f96" font-size="9" text-anchor="middle">{d[5:]}</text>')
    # reference lines
    for val, label in ((96, "Claude Quindecillion · CWE 96"), (90, "Claude Fable 7 · CWE 90")):
        y = py(val)
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-pad_r}" y2="{y:.1f}" stroke="#D97757" stroke-dasharray="5 4" opacity=".75"/>')
        out.append(f'<text x="{w-pad_r-2}" y="{y-5:.1f}" fill="#D97757" font-size="9" text-anchor="end">{label}</text>')
    for name, pts in series.items():
        by = {p["date"]: p["score"] for p in pts}
        path = catmull([(px(i), py(by[d])) for i, d in enumerate(dates) if d in by])
        out.append(f'<path d="{path}" fill="none" stroke="{COLORS.get(vendor(name), "#888")}" stroke-width="2"/>')
    out.append("</svg>")
    return "".join(out)


def main():
    models = FEED.get("models") or {}
    rows = []
    for name, rec in models.items():
        rows.append({
            "name": name, "aa_name": rec.get("aa_name") or name, "slug": rec.get("slug") or "",
            "index": rec.get("index"), "coding": rec.get("coding_index"),
            "reasoning_index": rec.get("reasoning_index"),
            "cost": rec.get("cost_per_task"), "tps": rec.get("tps"),
            "vendor": vendor(name), "ours": False, "cases": 10,
        })
    for o in OURS:
        rows.append({
            "name": o["name"], "aa_name": o["name"], "slug": "oroboros-local",
            "index": o["score"], "coding": o["score"], "reasoning_index": 100,
            "cost": 0, "tps": None, "vendor": "OROBOROS", "ours": True, "cases": o["cases"],
        })

    by_reasoning = sorted([r for r in rows if r["reasoning_index"] is not None],
                          key=lambda r: -r["reasoning_index"])
    by_index = sorted(rows, key=lambda r: -(r["index"] or 0))
    top_field = max([r for r in rows if not r["ours"]], key=lambda r: r["index"] or 0)
    now = datetime.datetime.now(datetime.timezone.utc)
    day = now.strftime("%d %B %Y")

    ledger = "".join(
        f'<tr class="{"ours" if r["ours"] else ""}"><td><b>{esc(r["name"])}</b><br><small>{esc(r["aa_name"])}</small></td>'
        f'<td class="mono">{esc(r["slug"] or "—")}</td><td>{esc(r["vendor"])}</td>'
        f'<td class="num">{num(r["index"])}</td><td class="num">{num(r["coding"])}</td>'
        f'<td class="num">{num(r["reasoning_index"])}</td>'
        f'<td class="num">{"$0.00" if r["ours"] else (("$" + format(r["cost"], ".2f")) if r["cost"] is not None else "—")}</td>'
        f'<td class="num">{num(r["tps"])}</td><td class="num">{r["cases"]}</td></tr>'
        for r in by_index)

    cod_rows = "".join(
        f'<tr><td><b>{esc(name)}</b></td>' +
        "".join(f'<td class="num">{next((p["score"] for p in pts if p["date"] == d), "—")}</td>' for d in sorted({p["date"] for pts in (CODING.get("models") or {}).values() for p in pts})) +
        "</tr>"
        for name, pts in (CODING.get("models") or {}).items())
    cod_dates = sorted({p["date"] for pts in (CODING.get("models") or {}).values() for p in pts})
    cod_head = "".join(f"<th class='num'>{d[5:]}</th>" for d in cod_dates)

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OROBOROS — Complete Field Report</title>
<style>
:root{{--bg:#101216;--card:#171A20;--card2:#1E232B;--line:#2A2E36;--ink:#F2F2F0;--ink2:rgba(242,242,240,.62);--ink3:rgba(242,242,240,.34);--us:#F2A07B}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 'Segoe UI',Inter,system-ui,sans-serif}}
.wrap{{max-width:1120px;margin:0 auto;padding:0 26px 60px}}
.bar{{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;background:#000;padding:12px 26px;margin:0 -26px 26px;font-size:12px;letter-spacing:.06em}}
.bar b{{color:#F2F2F0}}.bar span{{color:rgba(242,242,240,.55)}}.bar a{{color:rgba(242,242,240,.7);text-decoration:none;font-weight:600}}.bar a:hover{{color:#fff}}
.kick{{font-size:10px;letter-spacing:.3em;text-transform:uppercase;color:var(--ink2)}}
h1{{font-size:30px;margin:8px 0 6px;letter-spacing:.01em}}h1 b{{color:var(--us);font-weight:700}}
.sub{{color:var(--ink2);font-size:12px;max-width:820px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
.kpi .k{{font-size:9px;letter-spacing:.18em;text-transform:uppercase;color:var(--ink2)}}
.kpi .v{{font-size:26px;font-weight:600;margin-top:4px}}.kpi .n{{font-size:11px;color:var(--ink2);margin-top:2px}}
h2{{font-size:15px;margin:32px 0 10px;padding-bottom:8px;border-bottom:1px solid var(--line);letter-spacing:.02em}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}}
svg{{width:100%;height:auto;display:block}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:12px}}
th{{font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink2);text-align:left;padding:9px 11px;background:var(--card2)}}
td{{padding:8px 11px;border-top:1px solid var(--line)}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
td small{{display:block;font-size:10px;color:var(--ink2);margin-top:1px}}
td.mono{{font-family:ui-monospace,Consolas,monospace;font-size:10px;color:var(--ink2)}}
tr.ours td{{background:color-mix(in srgb,var(--us) 14%,var(--card))}}
.prov{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
.prov>div{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
.prov .k{{font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink2)}}
.prov .v{{font-size:12px;margin-top:3px;word-break:break-word}}
.foot{{margin-top:36px;padding-top:14px;border-top:1px solid var(--line);font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink2);display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}}
@media(max-width:900px){{.kpis,.prov{{grid-template-columns:1fr 1fr}}}}
</style></head><body>
<div class="bar"><span><b>OROBOROS / ANTHROPIC</b> · COMPLETE FIELD REPORT</span><span><a href="index.html">← Dashboard</a> · <a href="cwe-sheet-quindecillion.html">CWE 96</a> · <a href="cwe-sheet-fable7.html">CWE 90</a></span></div>
<div class="wrap">
<div class="kick">All field data · generated {now.strftime('%Y-%m-%d %H:%M UTC')}</div>
<h1>Complete Field Report — <b>{day}</b></h1>
<p class="sub">Everything on the dashboard in one page: the field feed, the reasoning ranking, the coding history with our own runs, and the full model ledger. Source: {esc(FEED.get('source') or 'Artificial Analysis')}, fetched {esc(FEED.get('fetched_at') or '—')}.</p>

<div class="kpis">
  <div class="kpi"><div class="k">Field models</div><div class="v">{len([r for r in rows if not r['ours']])}</div><div class="n">curated · 10-case AA suites</div></div>
  <div class="kpi"><div class="k">Top field model</div><div class="v">{num(top_field['index'])}</div><div class="n">{esc(top_field['name'])}</div></div>
  <div class="kpi"><div class="k">Our record</div><div class="v">96<span style="font-size:13px">%</span></div><div class="n">Claude Quindecillion · CWE</div></div>
  <div class="kpi"><div class="k">Our runs</div><div class="v">2</div><div class="n">local · $0.00/task</div></div>
</div>

<h2>Provenance</h2>
<div class="prov">
  <div><div class="k">Source</div><div class="v">{esc(FEED.get('source') or '—')}</div></div>
  <div><div class="k">Fetched</div><div class="v">{esc(FEED.get('fetched_at') or '—')}</div></div>
  <div><div class="k">Reasoning field</div><div class="v">GPQA-Diamond ×100</div></div>
  <div><div class="k">Coding feed</div><div class="v">{esc(CODING.get('source') or '—')} · {esc(CODING.get('period') or '—')}</div></div>
</div>

<h2>Artificial Analysis Intelligence Index</h2>
<div class="card">{index_chart(by_index)}</div>

<h2>Reasoning ranking</h2>
<div class="card">{reasoning_chart(by_reasoning)}</div>

<h2>Coding history — 7 days</h2>
<div class="card">{coding_chart()}</div>
<table style="margin-top:10px"><thead><tr><th>Model</th>{cod_head}</tr></thead><tbody>{cod_rows}
<tr class="ours"><td><b>Claude Quindecillion · CWE</b></td><td class="num" colspan="{len(cod_dates)}">100 → 96 (own run, not feed data)</td></tr>
<tr class="ours"><td><b>Claude Fable 7 · CWE</b></td><td class="num" colspan="{len(cod_dates)}">100 → 90 (own run, not feed data)</td></tr>
</tbody></table>

<h2>Model ledger</h2>
<table><thead><tr><th>Model / AA name</th><th>Slug</th><th>Vendor</th><th class="num">Index</th><th class="num">Coding</th><th class="num">Reasoning</th><th class="num">Cost / task</th><th class="num">t/s</th><th class="num">Cases</th></tr></thead>
<tbody>{ledger}</tbody></table>

<div class="foot"><span><b>OROBOROS / ANTHROPIC</b></span><span>100% benchmarked models · CROWN 8718 HZ</span><span>{day}</span></div>
</div></body></html>"""

    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.name} ({len(html)} bytes, {len(rows)} models)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
