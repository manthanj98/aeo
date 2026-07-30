"""Renderers: Markdown, self-contained HTML, JSON, and a terminal summary.

Every renderer takes the same three inputs — dataset, computed metrics, detected
insights — plus a `Narrative`, and none of them recompute anything. That separation is
what lets the JSON output be trusted as the audit trail for the Markdown and HTML: all
three are views of one set of numbers.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from .dataset import Dataset
from .insights import Insight, summarize
from .metrics import Metrics, page_citation_stats
from .narrative import Narrative

# Categorical series palette. The prototype's own engine colours (two near-identical
# golds plus a near-black) fail colour-vision-deficiency separation as a chart palette
# — validated with the dataviz skill's checker, worst adjacent pair ΔE 4.4 deutan
# against a required 8. These five keep the brand's amber/violet/teal character and
# pass all six checks in both light and dark mode (worst adjacent ΔE 10.2 deutan,
# 30.2 normal vision). Assigned in fixed order and never cycled.
SERIES = ("#B45309", "#7C3AED", "#0D9488", "#E11D48", "#2563EB")

# Status colours are reserved for severity and never reused as series colours. Each is
# always accompanied by its text label, so severity is never conveyed by colour alone.
SEVERITY_COLORS = {"High": "#DC2626", "Medium": "#CA8A04", "Low": "#0F766E"}
SEVERITY_ICONS = {"High": "▲", "Medium": "◆", "Low": "▪"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def engine_series_colors(metrics: Metrics) -> dict[str, str]:
    """Map each engine to a fixed series colour, ordered by the dataset's engine order.

    Fixed by engine identity rather than by rank, so filtering or re-sorting never
    repaints a series.
    """
    return {
        row["engine"]: SERIES[index % len(SERIES)]
        for index, row in enumerate(metrics.engine_rows)
    }


# -- JSON ---------------------------------------------------------------------------

def render_json(dataset: Dataset, metrics: Metrics, insights: list[Insight],
                narrative: Narrative) -> str:
    payload = {
        "generated_at": _now(),
        "dataset": dataset.describe(),
        "brand": {
            "name": dataset.brand_name,
            "domain": dataset.brand_domain,
            "period": dataset.period_label,
            "prior_period": dataset.prior_period_label,
        },
        "narrative_source": narrative.source,
        "model": narrative.model,
        "warnings": narrative.warnings,
        "metrics": metrics.to_dict(),
        "pages": page_citation_stats(dataset),
        "insight_summary": summarize(insights),
        "insights": [
            {**insight.to_dict(),
             "note": (narrative.note_for(insight.id).to_dict()
                      if narrative.note_for(insight.id) else None)}
            for insight in insights
        ],
        "drafts": [draft.to_dict() for draft in narrative.drafts],
        "executive_summary": narrative.executive_summary,
    }
    return json.dumps(payload, indent=2) + "\n"


# -- Markdown -----------------------------------------------------------------------

def render_markdown(dataset: Dataset, metrics: Metrics, insights: list[Insight],
                    narrative: Narrative) -> str:
    counts = summarize(insights)
    out: list[str] = []
    add = out.append

    add(f"# {dataset.brand_name} — AI visibility report")
    add("")
    add(f"**Period** {dataset.period_label} (compared with {dataset.prior_period_label}) · "
        f"**Answers analysed** {metrics.answer_counts['current']:,} · "
        f"**Generated** {_now()}")
    add("")
    source_label = (
        f"Narrative written by the agent ({narrative.model})"
        if narrative.source == "agent" else
        "Narrative from deterministic templates (no model call)"
    )
    add(f"_{source_label}. All figures computed from "
        f"`{Path(dataset.path).name if dataset.path else 'dataset'}`; "
        f"see `insights.json` for the full evidence behind every number._")
    add("")
    for warning in narrative.warnings:
        add(f"> ⚠️ {warning}")
    if narrative.warnings:
        add("")

    add("## Executive summary")
    add("")
    add(narrative.executive_summary)
    add("")

    add("## Key metrics")
    add("")
    add("| Metric | Value | vs prior | |")
    add("|---|---|---|---|")
    arrow = {"up": "▲ improving", "down": "▼ declining", "flat": "— steady"}
    for kpi in metrics.kpis:
        add(f"| {kpi.label} | **{kpi.display}** | {kpi.trend_display} | "
            f"{arrow[kpi.direction]} |")
    add("")
    add("<details><summary>Metric definitions</summary>")
    add("")
    for kpi in metrics.kpis:
        add(f"- **{kpi.label}** — {kpi.definition}")
    add("")
    add("</details>")
    add("")

    add("## By engine")
    add("")
    add("| Engine | Answers | Citation share | Citations | Mention rate | "
        "Citation rate | Avg. position | Sentiment |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in metrics.engine_rows:
        add(f"| {row['engine']} | {row['answers']:,} | {row['citation_share']:.1f}% | "
            f"{row['brand_citations']} | {row['mention_rate']:.1f}% | "
            f"{row['citation_rate']:.1f}% | {row['avg_position']} | {row['sentiment']} |")
    add("")

    add("## Against competitors")
    add("")
    for board in metrics.leaderboards:
        ranked = " · ".join(
            f"**{r['name']} {r['display']}**" if r["is_you"] else f"{r['name']} {r['display']}"
            for r in board["rows"]
        )
        add(f"- **{board['label']}** — rank {board['brand_rank']} of "
            f"{board['field_size']}: {ranked}")
    add("")
    add("_The brand's own figures are computed from the answer set; competitor figures "
        "are carried over from the source tables, since the dataset holds no "
        "answer-level data for competitors._")
    add("")

    add("## By topic")
    add("")
    add("| Topic | Prompts | Monthly volume | Mention rate | Citation rate | "
        "vs prior | Share of voice |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    for row in metrics.topic_rows:
        add(f"| {row['topic']} | {row['prompts']} | {row['volume']:,} | "
            f"{row['mention_rate']:.1f}% | {row['citation_rate']:.1f}% | "
            f"{row['citation_trend']:+.1f} | {row['share_of_voice']:.1f}% |")
    add("")

    add(f"## Findings ({counts['total']})")
    add("")
    add(f"{counts['by_severity']['High']} High · {counts['by_severity']['Medium']} Medium · "
        f"{counts['by_severity']['Low']} Low — "
        f"{counts['by_action']['update']} targeting an existing page, "
        f"{counts['by_action']['draft']} calling for new content.")
    add("")
    add(f"Detection ran {len(counts['rules_available'])} rules, of which "
        f"{len(counts['rules_fired'])} fired. Severity is scored, not assigned: "
        f"`sqrt(magnitude × reach)`, where reach is the share of the portfolio affected.")
    add("")

    for insight in insights:
        note = narrative.note_for(insight.id)
        add(f"### {SEVERITY_ICONS[insight.severity]} {insight.id} — {insight.title}")
        add("")
        add(f"**{insight.severity}** (score {insight.score:.3f} = "
            f"magnitude {insight.magnitude:.2f} × reach {insight.reach:.3f}) · "
            f"rule `{insight.rule}` · action **{insight.action}**"
            + (f" · `{insight.target_url}`" if insight.target_url else ""))
        add("")
        add(f"**{insight.stat_value}** — {insight.stat_delta}")
        add("")
        add(f"**Root cause.** {insight.root_cause}")
        add("")
        if note:
            add(f"**Impact.** {note.impact}")
            add("")
            add(f"**Recommendation.** {note.recommendation}")
            add("")
        if insight.contributors:
            add("| Contributor | Value | Share | Detail |")
            add("|---|---|---:|---|")
            for contributor in insight.contributors:
                add(f"| {contributor['label']} | {contributor['value']} | "
                    f"{contributor['share_pct']}% | {contributor['detail']} |")
            add("")
        draft = narrative.draft_for(insight.id)
        if draft:
            kind = "update brief" if draft.is_update else "article draft"
            add(f"→ A {kind} was generated for this finding: **{draft.title}**")
            add("")

    if narrative.drafts:
        add("## Drafts produced")
        add("")
        for draft in narrative.drafts:
            kind = "Update brief" if draft.is_update else "Article draft"
            add(f"- **{kind}** for `{draft.insight_id}` — {draft.title}")
        add("")

    return "\n".join(out) + "\n"


def render_draft_markdown(dataset: Dataset, insight: Insight, draft) -> str:
    out: list[str] = []
    add = out.append

    kind = "Page update brief" if draft.is_update else "Article draft"
    add(f"# {draft.title}")
    add("")
    add(f"**{kind}** · finding `{insight.id}` ({insight.severity} severity) · "
        f"generated {_now()}")
    if draft.target_url:
        add("")
        add(f"**Target page** `{draft.target_url}`")
    add("")
    add("## Why this is on the list")
    add("")
    add(draft.rationale)
    add("")
    add(f"Headline number: **{insight.stat_value}** — {insight.stat_delta}")
    add("")

    if draft.changes:
        add("## Changes to make")
        add("")
        for change in draft.changes:
            add(f"- **{change.label}.** {change.detail}")
        add("")

    if draft.sections:
        add("## Draft")
        add("")
        for section in draft.sections:
            add(f"### {section.heading}")
            add("")
            add(section.body)
            add("")

    if draft.success_metric:
        add("## How to tell it worked")
        add("")
        add(draft.success_metric)
        add("")

    add("---")
    add("")
    add("_Draft for review — not published. Evidence for the underlying finding is in "
        "`insights.json`._")
    return "\n".join(out) + "\n"


# -- terminal ------------------------------------------------------------------------

def render_terminal(dataset: Dataset, metrics: Metrics, insights: list[Insight],
                    narrative: Narrative, limit: int = 6) -> str:
    counts = summarize(insights)
    lines: list[str] = []
    add = lines.append

    add(f"{dataset.brand_name} — AI visibility, {dataset.period_label} "
        f"({metrics.answer_counts['current']:,} answers)")
    add("─" * 78)
    for kpi in metrics.kpis:
        mark = {"up": "▲", "down": "▼", "flat": "—"}[kpi.direction]
        add(f"  {kpi.label:<16} {kpi.display:>8}   {kpi.trend_display:>10}  {mark}")
    add("")
    add(f"Findings: {counts['by_severity']['High']} High · "
        f"{counts['by_severity']['Medium']} Medium · {counts['by_severity']['Low']} Low "
        f"({len(counts['rules_fired'])}/{len(counts['rules_available'])} rules fired)")
    add("")
    for insight in insights[:limit]:
        add(f"  {SEVERITY_ICONS[insight.severity]} {insight.id} {insight.severity:<6} "
            f"{insight.title[:66]}")
    if len(insights) > limit:
        add(f"     … {len(insights) - limit} more in the report")
    if narrative.drafts:
        updates = sum(1 for d in narrative.drafts if d.is_update)
        articles = len(narrative.drafts) - updates
        parts = []
        if updates:
            parts.append(f"{updates} update brief{'s' if updates != 1 else ''}")
        if articles:
            parts.append(f"{articles} new article{'s' if articles != 1 else ''}")
        add("")
        add(f"Drafts: {len(narrative.drafts)} ({', '.join(parts)})")
    for warning in narrative.warnings:
        add(f"  ⚠️  {warning}")
    return "\n".join(lines)


# -- HTML ---------------------------------------------------------------------------

def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _bar_chart(metrics: Metrics) -> str:
    """Horizontal bars for citation share by engine.

    A horizontal bar is the right form here: magnitude compared across a handful of
    named entities, with labels long enough that vertical bars would need rotated text.
    Bars carry direct value labels, so the chart never depends on reading a colour
    against a legend, and a table view follows it for anyone who cannot use either.
    """
    colors = engine_series_colors(metrics)
    rows = sorted(metrics.engine_rows, key=lambda r: r["citation_share"], reverse=True)
    peak = max((r["citation_share"] for r in rows), default=1) or 1

    bars = []
    for row in rows:
        width = 100.0 * row["citation_share"] / peak
        bars.append(f"""
        <div class="bar-row" tabindex="0"
             data-tip="{_e(row['engine'])}: {row['citation_share']:.1f}% of citations · {row['brand_citations']} citations · {row['answers']:,} answers · citation rate {row['citation_rate']:.1f}%">
          <div class="bar-label">{_e(row['engine'])}</div>
          <div class="bar-track">
            <div class="bar-fill" style="width:{width:.1f}%;background:{colors[row['engine']]}"></div>
          </div>
          <div class="bar-value">{row['citation_share']:.1f}%</div>
        </div>""")

    legend = "".join(
        f'<span class="key"><i style="background:{colors[r["engine"]]}"></i>'
        f'{_e(r["engine"])}</span>'
        for r in metrics.engine_rows
    )

    table_rows = "".join(
        f"<tr><td>{_e(r['engine'])}</td><td>{r['citation_share']:.1f}%</td>"
        f"<td>{r['brand_citations']}</td><td>{r['answers']:,}</td>"
        f"<td>{r['mention_rate']:.1f}%</td><td>{r['citation_rate']:.1f}%</td>"
        f"<td>{r['avg_position']}</td></tr>"
        for r in rows
    )

    return f"""
    <section class="card">
      <h2>Citation share by engine</h2>
      <p class="sub">Each engine's slice of the {sum(r['brand_citations'] for r in rows)}
         brand citations recorded this period.</p>
      <div class="legend">{legend}</div>
      <div class="chart">{''.join(bars)}</div>
      <details>
        <summary>Table view</summary>
        <div class="scroll">
        <table>
          <thead><tr><th>Engine</th><th>Citation share</th><th>Citations</th>
            <th>Answers</th><th>Mention rate</th><th>Citation rate</th>
            <th>Avg. position</th></tr></thead>
          <tbody>{table_rows}</tbody>
        </table>
        </div>
      </details>
    </section>"""


def _kpi_tiles(metrics: Metrics) -> str:
    """Stat tiles, not a chart — six unrelated headline numbers have no shared scale."""
    tiles = []
    for kpi in metrics.kpis:
        mark = {"up": "▲", "down": "▼", "flat": "—"}[kpi.direction]
        tiles.append(f"""
        <div class="tile" tabindex="0" data-tip="{_e(kpi.definition)}">
          <div class="tile-label">{_e(kpi.label)}</div>
          <div class="tile-value">{_e(kpi.display)}</div>
          <div class="tile-trend dir-{kpi.direction}">{mark} {_e(kpi.trend_display)}</div>
        </div>""")
    return f'<div class="tiles">{"".join(tiles)}</div>'


def _leaderboards(metrics: Metrics) -> str:
    blocks = []
    for board in metrics.leaderboards:
        rows = "".join(
            f'<tr class="{"you" if r["is_you"] else ""}">'
            f"<td>{r['rank']}</td><td>{_e(r['name'])}</td><td>{_e(r['display'])}</td></tr>"
            for r in board["rows"]
        )
        blocks.append(f"""
        <div class="board">
          <h3>{_e(board['label'])}</h3>
          <table><tbody>{rows}</tbody></table>
        </div>""")
    return f'<div class="boards">{"".join(blocks)}</div>'


def _insight_cards(insights: list[Insight], narrative: Narrative) -> str:
    cards = []
    for insight in insights:
        note = narrative.note_for(insight.id)
        draft = narrative.draft_for(insight.id)
        color = SEVERITY_COLORS[insight.severity]

        contributors = "".join(
            f"<li><span>{_e(c['label'])}</span><strong>{_e(c['value'])}</strong>"
            f"<em>{c['share_pct']}% · {_e(c['detail'])}</em></li>"
            for c in insight.contributors
        )
        note_html = ""
        if note:
            note_html = (
                f"<p><strong>Impact.</strong> {_e(note.impact)}</p>"
                f"<p><strong>Recommendation.</strong> {_e(note.recommendation)}</p>"
            )
        draft_html = ""
        if draft:
            kind = "Update brief" if draft.is_update else "Article draft"
            draft_html = (
                f'<p class="draft-flag">{kind} generated: '
                f"<strong>{_e(draft.title)}</strong></p>"
            )

        cards.append(f"""
        <article class="insight">
          <header>
            <span class="sev" style="color:{color};border-color:{color}">
              {SEVERITY_ICONS[insight.severity]} {insight.severity}
            </span>
            <span class="iid">{_e(insight.id)}</span>
            <span class="rule">{_e(insight.rule)}</span>
            <span class="act act-{_e(insight.action)}">{_e(insight.action)}</span>
          </header>
          <h3>{_e(insight.title)}</h3>
          <div class="stat">
            <strong>{_e(insight.stat_value)}</strong>
            <span>{_e(insight.stat_delta)}</span>
          </div>
          <p><strong>Root cause.</strong> {_e(insight.root_cause)}</p>
          {note_html}
          {f"<ul class='contrib'>{contributors}</ul>" if contributors else ""}
          {draft_html}
          <footer>score {insight.score:.3f} = magnitude {insight.magnitude:.2f}
            × reach {insight.reach:.3f}
            {f"· <code>{_e(insight.target_url)}</code>" if insight.target_url else ""}
          </footer>
        </article>""")
    return "".join(cards)


CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#fcfcfb; --surface:#fff; --ink:#1a1a19; --ink-2:#4b4b47; --ink-3:#77776f;
  --line:#e4e3dd; --line-2:#efeeea; --accent:#4A2C7A; --accent-2:#B45309;
  --good:#0F766E; --bad:#DC2626; --warn:#CA8A04; --tip-bg:#1a1a19; --tip-ink:#fcfcfb;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#141317; --surface:#1c1b20; --ink:#f2f1ec; --ink-2:#c3c1b8; --ink-3:#8f8d84;
    --line:#2e2c33; --line-2:#26242b; --accent:#A78BFA; --accent-2:#F0A94A;
    --good:#2DD4BF; --bad:#F87171; --warn:#EAB308; --tip-bg:#f2f1ec; --tip-ink:#141317;
  }
}
:root[data-theme=dark]{
  --bg:#141317; --surface:#1c1b20; --ink:#f2f1ec; --ink-2:#c3c1b8; --ink-3:#8f8d84;
  --line:#2e2c33; --line-2:#26242b; --accent:#A78BFA; --accent-2:#F0A94A;
  --good:#2DD4BF; --bad:#F87171; --warn:#EAB308; --tip-bg:#f2f1ec; --tip-ink:#141317;
}
:root[data-theme=light]{
  --bg:#fcfcfb; --surface:#fff; --ink:#1a1a19; --ink-2:#4b4b47; --ink-3:#77776f;
  --line:#e4e3dd; --line-2:#efeeea; --accent:#4A2C7A; --accent-2:#B45309;
  --good:#0F766E; --bad:#DC2626; --warn:#CA8A04; --tip-bg:#1a1a19; --tip-ink:#fcfcfb;
}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.62 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:40px 22px 96px}
h1{font-size:1.85rem;line-height:1.2;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:1.12rem;margin:0 0 4px;letter-spacing:-.01em}
h3{font-size:1rem;margin:0 0 8px}
p{margin:0 0 12px;color:var(--ink-2)}
a{color:var(--accent)}
code{font:12.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;
  background:var(--line-2);padding:1px 5px;border-radius:4px;color:var(--ink-2)}
.meta{color:var(--ink-3);font-size:13px;margin-bottom:4px}
.provenance{color:var(--ink-3);font-size:12.5px;border-left:2px solid var(--line);
  padding-left:12px;margin:18px 0 30px}
.warn-box{border:1px solid var(--warn);border-radius:8px;padding:12px 14px;
  margin:0 0 22px;font-size:13.5px;color:var(--ink-2)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;
  padding:22px;margin:0 0 20px}
.sub{color:var(--ink-3);font-size:13px;margin:0 0 16px}
.tiles{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  margin:0 0 20px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:12px;
  padding:16px 18px}
.tile:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.tile-label{font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--ink-3);margin-bottom:8px}
.tile-value{font-size:1.75rem;font-weight:650;letter-spacing:-.02em;line-height:1}
.tile-trend{font-size:12.5px;margin-top:7px;font-weight:550}
.dir-up{color:var(--good)} .dir-down{color:var(--bad)} .dir-flat{color:var(--ink-3)}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 16px}
.key{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;color:var(--ink-2)}
.key i{width:10px;height:10px;border-radius:3px;display:inline-block}
.chart{display:flex;flex-direction:column;gap:9px}
.bar-row{display:grid;grid-template-columns:168px 1fr 54px;align-items:center;gap:12px}
.bar-row:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:4px}
.bar-label{font-size:13px;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.bar-track{background:var(--line-2);border-radius:4px;height:15px;overflow:hidden}
.bar-fill{height:100%;border-radius:0 4px 4px 0;transition:width .3s ease}
.bar-value{font-size:13px;font-weight:600;text-align:right;
  font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:13px;margin-top:10px}
th,td{text-align:left;padding:7px 11px;border-bottom:1px solid var(--line-2);
  white-space:nowrap}
th{font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink-3);
  font-weight:600}
td{color:var(--ink-2);font-variant-numeric:tabular-nums}
tr.you td{background:var(--line-2);color:var(--ink);font-weight:600}
.boards{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(196px,1fr))}
.board h3{font-size:12px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--ink-3);margin-bottom:2px}
.board td:first-child{width:22px;color:var(--ink-3)}
details{margin-top:14px}
summary{cursor:pointer;font-size:12.5px;color:var(--ink-3);
  padding:5px 0;user-select:none}
summary:hover{color:var(--ink-2)}
.insight{background:var(--surface);border:1px solid var(--line);border-radius:12px;
  padding:20px 22px;margin:0 0 14px}
.insight header{display:flex;flex-wrap:wrap;align-items:center;gap:9px;
  margin-bottom:11px}
.sev{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  border:1px solid;border-radius:5px;padding:2px 8px}
.iid{font:11.5px ui-monospace,Menlo,monospace;color:var(--ink-3)}
.rule{font:11.5px ui-monospace,Menlo,monospace;color:var(--ink-3);
  background:var(--line-2);padding:2px 7px;border-radius:4px}
.act{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;
  padding:2px 8px;border-radius:5px;background:var(--line-2);color:var(--ink-2)}
.insight h3{font-size:1.02rem;line-height:1.4;margin:0 0 12px;color:var(--ink)}
.stat{display:flex;align-items:baseline;gap:11px;margin:0 0 14px;flex-wrap:wrap}
.stat strong{font-size:1.55rem;font-weight:650;letter-spacing:-.02em}
.stat span{font-size:13px;color:var(--ink-3)}
.insight p{font-size:13.8px;margin:0 0 11px}
.contrib{list-style:none;padding:0;margin:14px 0 4px;display:grid;gap:8px;
  grid-template-columns:repeat(auto-fit,minmax(184px,1fr))}
.contrib li{border:1px solid var(--line);border-radius:8px;padding:9px 11px;
  display:flex;flex-direction:column;gap:2px}
.contrib span{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--ink-3)}
.contrib strong{font-size:13.5px}
.contrib em{font-size:11.5px;color:var(--ink-3);font-style:normal}
.draft-flag{font-size:13px;border-left:2px solid var(--accent);padding-left:11px;
  margin-top:14px}
.insight footer{font-size:11.5px;color:var(--ink-3);margin-top:13px;
  padding-top:11px;border-top:1px solid var(--line-2)}
#tip{position:fixed;z-index:50;max-width:300px;background:var(--tip-bg);
  color:var(--tip-ink);font-size:12.5px;line-height:1.5;padding:8px 11px;
  border-radius:7px;pointer-events:none;opacity:0;transition:opacity .12s;
  box-shadow:0 6px 22px rgba(0,0,0,.24)}
#tip.on{opacity:1}
.toggle{position:fixed;top:14px;right:14px;background:var(--surface);
  border:1px solid var(--line);color:var(--ink-2);border-radius:8px;
  padding:6px 12px;font-size:12.5px;cursor:pointer;z-index:40}
@media (max-width:620px){
  .bar-row{grid-template-columns:112px 1fr 48px;gap:9px}
  .wrap{padding:26px 15px 70px}
  h1{font-size:1.5rem}
}
@media print{.toggle,#tip{display:none}}
"""

JS = """
(function(){
  var root=document.documentElement, tip=document.getElementById('tip');
  document.querySelector('.toggle').addEventListener('click',function(){
    var dark=(root.getAttribute('data-theme')||
      (matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'))==='dark';
    root.setAttribute('data-theme',dark?'light':'dark');
  });
  function show(el,e){
    var text=el.getAttribute('data-tip'); if(!text) return;
    tip.textContent=text; tip.classList.add('on');
    var pad=14, r=el.getBoundingClientRect();
    var x=(e&&e.clientX!=null?e.clientX:r.left+r.width/2)+pad;
    var y=(e&&e.clientY!=null?e.clientY:r.top)+pad;
    tip.style.left='0px'; tip.style.top='0px';
    var w=tip.offsetWidth, h=tip.offsetHeight;
    if(x+w>innerWidth-8) x=innerWidth-w-8;
    if(y+h>innerHeight-8) y=y-h-2*pad;
    tip.style.left=Math.max(8,x)+'px'; tip.style.top=Math.max(8,y)+'px';
  }
  function hide(){ tip.classList.remove('on'); }
  document.querySelectorAll('[data-tip]').forEach(function(el){
    el.addEventListener('mouseenter',function(e){show(el,e)});
    el.addEventListener('mousemove',function(e){show(el,e)});
    el.addEventListener('mouseleave',hide);
    el.addEventListener('focus',function(){show(el,null)});
    el.addEventListener('blur',hide);
  });
})();
"""


def render_html(dataset: Dataset, metrics: Metrics, insights: list[Insight],
                narrative: Narrative) -> str:
    counts = summarize(insights)
    source_label = (
        f"Narrative written by the agent ({narrative.model})"
        if narrative.source == "agent"
        else "Narrative from deterministic templates (no model call)"
    )
    warnings = "".join(
        f'<div class="warn-box">⚠️ {_e(w)}</div>' for w in narrative.warnings
    )

    topic_rows = "".join(
        f"<tr><td>{_e(r['topic'])}</td><td>{r['prompts']}</td>"
        f"<td>{r['volume']:,}</td><td>{r['mention_rate']:.1f}%</td>"
        f"<td>{r['citation_rate']:.1f}%</td><td>{r['citation_trend']:+.1f}</td>"
        f"<td>{r['share_of_voice']:.1f}%</td></tr>"
        for r in metrics.topic_rows
    )
    definitions = "".join(
        f"<li><strong>{_e(k.label)}</strong> — {_e(k.definition)}</li>"
        for k in metrics.kpis
    )

    return f"""<title>{_e(dataset.brand_name)} — AI visibility report</title>
<style>{CSS}</style>
<button class="toggle" type="button">◐ theme</button>
<div id="tip" role="tooltip"></div>
<div class="wrap">
  <h1>{_e(dataset.brand_name)} — AI visibility report</h1>
  <p class="meta">{_e(dataset.period_label)} compared with
    {_e(dataset.prior_period_label)} ·
    {metrics.answer_counts['current']:,} AI answers analysed · generated {_now()}</p>
  <p class="provenance">{_e(source_label)}. Every figure is computed from the answer-level
    dataset; the full evidence behind each finding is in <code>insights.json</code>.
    Severity is scored as <code>sqrt(magnitude × reach)</code>, not assigned by hand.</p>
  {warnings}

  <section class="card">
    <h2>Executive summary</h2>
    <p>{_e(narrative.executive_summary)}</p>
  </section>

  {_kpi_tiles(metrics)}

  <section class="card">
    <h2>Metric definitions</h2>
    <p class="sub">Hover any tile above for the same text.</p>
    <ul style="margin:0;padding-left:18px;color:var(--ink-2);font-size:13.5px">
      {definitions}
    </ul>
  </section>

  {_bar_chart(metrics)}

  <section class="card">
    <h2>Against tracked competitors</h2>
    <p class="sub">The brand's row is computed from the answer set; competitor rows are
      carried over from the source tables, which hold no answer-level competitor data.</p>
    {_leaderboards(metrics)}
  </section>

  <section class="card">
    <h2>By topic</h2>
    <div class="scroll">
    <table>
      <thead><tr><th>Topic</th><th>Prompts</th><th>Volume</th><th>Mention rate</th>
        <th>Citation rate</th><th>vs prior</th><th>Share of voice</th></tr></thead>
      <tbody>{topic_rows}</tbody>
    </table>
    </div>
  </section>

  <h2 style="margin:32px 0 6px">Findings ({counts['total']})</h2>
  <p class="meta" style="margin-bottom:18px">
    {counts['by_severity']['High']} High · {counts['by_severity']['Medium']} Medium ·
    {counts['by_severity']['Low']} Low —
    {counts['by_action']['update']} targeting an existing page,
    {counts['by_action']['draft']} calling for new content.
    {len(counts['rules_fired'])} of {len(counts['rules_available'])} detection rules fired.</p>
  {_insight_cards(insights, narrative)}
</div>
<script>{JS}</script>
"""


# -- writing -------------------------------------------------------------------------

def write_all(out_dir: Path, dataset: Dataset, metrics: Metrics,
              insights: list[Insight], narrative: Narrative) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    report_md = out_dir / "aeo-report.md"
    report_md.write_text(render_markdown(dataset, metrics, insights, narrative))
    written.append(report_md)

    report_html = out_dir / "aeo-report.html"
    report_html.write_text(render_html(dataset, metrics, insights, narrative))
    written.append(report_html)

    insights_json = out_dir / "insights.json"
    insights_json.write_text(render_json(dataset, metrics, insights, narrative))
    written.append(insights_json)

    if narrative.drafts:
        drafts_dir = out_dir / "drafts"
        drafts_dir.mkdir(exist_ok=True)
        by_id = {i.id: i for i in insights}
        for draft in narrative.drafts:
            insight = by_id.get(draft.insight_id)
            if not insight:
                continue
            path = drafts_dir / f"{draft.insight_id}-{draft.slug}.md"
            path.write_text(render_draft_markdown(dataset, insight, draft))
            written.append(path)

    return written
