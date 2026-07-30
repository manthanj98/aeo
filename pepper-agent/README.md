# Pepper AEO Agent

An agent that reads AI-visibility data for a brand, computes its KPIs, detects what
changed and why, and writes the content that responds to it — a report plus real
content drafts on disk.

Built from `prototype/pepperproject.standalone.html`, a 5,459-line React prototype of an
"AI Visibility Dashboard". The prototype is a UI mock: every number, insight, severity,
and article draft in it is a hardcoded literal inside one
`class Component extends DCLogic`. Nothing is computed and nothing is generated. This
turns that idea into a program that actually does the work.

```
pip install -r requirements.txt
python -m pepper_agent run --top 3
```

Output lands in `out/`:

| File | What it is |
|---|---|
| `aeo-report.md` | Executive summary, KPI table, engine and topic breakdowns, competitor leaderboards, every ranked finding with root cause, impact, and recommendation |
| `aeo-report.html` | The same report, self-contained and theme-aware, with a citation-share chart |
| `insights.json` | Machine-readable: every finding with the evidence rows that triggered it and its severity arithmetic |
| `drafts/*.md` | One file per selected finding — a new article draft, or a change brief against a specific URL |

## How it works

Deterministic core, agent on top. The split is the point.

```
data/source_tables.json   literals extracted from the prototype
        │  tools/materialize.py  (once, seeded — expands aggregates into facts)
        ▼
data/visibility.json      4,000 answer-level records over two periods
        │
        ├── metrics.py     six KPIs, engine / topic / competitor breakdowns
        ├── insights.py    12 detection rules, scored severity
        │        │
        │        ▼
        │   tools.py       the above, exposed as read-only agent tools
        │        │
        │        ▼
        │   agent.py       Claude Agent SDK: ranks, explains, drafts
        │   fallback.py    the same shapes from templates, when no model is reachable
        │        │
        ▼        ▼
     render.py            markdown · HTML · JSON · terminal
```

**Metrics and detection never call a model.** They are reproducible and auditable, so a
finding is a fact about the data rather than a model's impression of it. Run it twice on
the same dataset and you get the same 18 findings in the same order.

**The agent does the judgment work** — why a finding matters commercially, what to do
about it, and the actual draft copy. It reaches the data *only* through the tools in
`tools.py` and is told that every number it states must come from a tool call. That is
checkable: diff any figure in `aeo-report.md` against `insights.json`.

**The model is optional.** If the SDK can't start — no CLI, no credentials, a transport
failure — the run still writes a complete report from `fallback.py` and says so in the
output and in a banner at the top of the report. A report that fails to render because a
subprocess didn't launch is not a working agent.

### Commands

```
python -m pepper_agent inspect                  what the dataset holds, what fired
python -m pepper_agent report                   metrics + findings, no drafts
python -m pepper_agent run --top 3              report + drafts for the top 3 findings
python -m pepper_agent run --insight ins_04 --insight ins_09    specific findings
python -m pepper_agent draft --insight ins_08   one draft
python -m pepper_agent run --top 3 --offline    no model call at all
python -m pepper_agent run --data other.json --out /tmp/report
```

`--model` defaults to `claude-opus-5`.

## Detection rules

Twelve rules, each deriving a finding the prototype hardcodes. On the seed data eleven
fire and produce 18 findings; `sentiment_divergence` finds nothing, which is the correct
answer for this dataset rather than a gap.

| Rule | Fires when | Action |
|---|---|---|
| `citation_decline` | a page loses citation share faster than the portfolio | update |
| `topic_citation_gap` | a topic is cited well below portfolio rate while rivals appear | draft |
| `rising_page` | citations and impressions climb together | update |
| `high_impressions_low_ctr` | real demand, weak clickthrough, solid citations | update |
| `seo_strong_low_citations` | ranks well organically, rarely cited | update |
| `competitor_prompt_gap` | high-volume prompt where rivals are named and the brand isn't | draft |
| `sentiment_divergence` | mentions up while sentiment falls | draft |
| `engine_concentration` | one engine carries a disproportionate citation share | draft |
| `underindexed_engine` | an engine where the brand barely appears | draft |
| `stale_high_value` | well-cited page, unrefreshed, position slipping | update |
| `unlinked_mentions` | high-authority domains name the brand without linking | draft |
| `community_gap` | active threads discuss the brand with no official presence | draft |

`action` decides the deliverable: `update` yields a change brief against a specific URL,
`draft` yields a new article. This mirrors the prototype's `articleAction`, except it is
derived from whether a finding implicates an existing page.

### Severity is scored, not assigned

```
score = sqrt(magnitude × reach)      High ≥ 0.45, Medium ≥ 0.22, else Low
```

- **magnitude** — how far the metric deviates, against a per-rule reference deviation.
- **reach** — the share of the portfolio affected, always a true fraction of a portfolio
  total: citations over all citations, impressions over all impressions, search volume
  over all volume. Never an arbitrary divisor, so severities stay comparable between
  rules. Units still differ between families, so cross-family comparison is approximate.

The geometric mean means neither axis alone carries a finding: a catastrophic drop on a
page nobody reads stays Low, and a mild dip across half the portfolio does not.

This is the clearest thing the prototype cannot do — its severities are string literals,
so `severity: 'High'` sits next to a stat that never determined it.

## Dataset provenance

`data/source_tables.json` holds the prototype's literal tables, carried over unchanged,
with the source line number for each. `tools/materialize.py` expands them once
(deterministically, seeded) into `data/visibility.json`: 4,000 answer-level records —
one per prompt × engine × run × period — which is the arrangement the aggregates would
have been rolled up from, and what lets `metrics.py` genuinely compute.

Rerun after editing the source tables:

```
python tools/materialize.py --report        # --report prints marginal-fit residuals
```

Three modelling decisions worth knowing about:

**Quota allocation, not coin flips.** Independent Bernoulli draws at 20 runs per cell
carry enough binomial noise to swamp the deviations the rules read. Each cell gets
exactly `round(runs × p)` hits, shuffled. Mean absolute residual against the stated
per-prompt rates: **0.70 points** on mention rate, **0.50** on citation rate.

**Engines are sampled unequally.** The prototype gives both a citation *rate* per engine
(52% → 36%, narrow) and a citation *share* (34% → 8%, wide). Those only reconcile if
engines contribute different numbers of answers, since `share = runs × rate`. So runs
are split proportional to `share / rate`, which recovers the stated shares almost
exactly:

| Engine | Computed share | Prototype states |
|---|---:|---:|
| ChatGPT | 35.4% | 34% |
| Perplexity | 26.4% | 27% |
| Google AI Overviews | 18.2% | 18% |
| Microsoft Co-Pilot | 12.3% | 13% |
| Claude | 7.7% | 8% |

Sampling engines equally would flatten every share to ~20% and hide the concentration
risk the data actually carries — which is the highest-severity finding on this dataset.

**Fields the prototype never defines** are marked `synthetic: true` or listed in a row's
`synthetic_fields`: `months_since_update`, `unlinked_mentions`, `community_threads`, and
most Search Console rows. The prototype's own `gscPages` are leftovers from a Search
Console demo — paths like `/docs/url-inspection` that don't exist in its citation table —
so cross-source rules had nothing to join on. `search_console[]` is keyed to the same
URLs as the cited pages, using the two figures the prototype states in its own insight
text verbatim (`/blog-post/citation-rate-benchmarks` at 22,300 impressions / 4.6% CTR,
`/report/competitor-share-of-voice` at 19,700 / 4.4%) and filling the rest consistently
with each page's citation volume.

## KPI reconciliation

Two of the prototype's stated figures cannot be reproduced, and one of its definitions
is arithmetically impossible. Rather than tune constants to match a mock, here is what
diverges and why.

| KPI | Computed | Prototype | Note |
|---|---:|---:|---|
| Mention rate | 44.1% | 58% | see below |
| Citation rate | 29.5% | 46% | see below |
| Share of voice | 26.8% | 21% | definition changed — see below |
| Sentiment | 86.2 | 82 | close; follows from per-prompt `positive_rate` |
| Avg. position | 2.5 | 2.4 | close |
| Visibility | 24.1% | 34% | no formula given — see below |

**Mention and citation rate.** The prototype's two tables disagree about the overall
level: `trackedPrompts` averages 44.4% mention rate while `engineData` averages 53.8%. No
joint distribution has both as marginals. The finer-grained prompt table (20 rows, with
volumes) is treated as authoritative for level and the engine table for relative ordering
between engines, so computed engine rates come out uniformly scaled by ≈0.82 while
preserving the stated ranking. The prototype's headline 58% and 46% come from
`brandMetricsData`, a separate hardcoded table that matches neither.

**Share of voice.** The prototype's tooltip says "answers mentioning your brand divided
by answers mentioning your brand OR competitors" — but that ratio has the brand's own
mentions in the numerator and a superset in the denominator, so it can never fall to a
third of a 58% mention rate the way its own stated 21% does. The volume-share reading —
brand mentions over brand-plus-competitor *mention instances*, the standard industry
definition — lands at 23.1% on the first build against the stated 21%, so that is what
`metrics.py` implements.

**Visibility.** Described as "weighted by mention rate, position, and share of voice"
with no arithmetic. Implemented as `sqrt(MRR × share_of_voice)`, where MRR is mean
reciprocal rank over all answers (standard IR metric — it folds mention rate and position
into one number). A geometric mean means a brand can't post a strong visibility score by
dominating one axis while failing the other. The prototype's 34% is a string with no
derivation to match.

### Page-level reconciliation

Page citation counts and their period-over-period change are computed by counting which
answers cited which URL, not asserted. Citations are attributed by exact per-page quota;
prior-period targets come from backing the stated `change_vs_previous_pct` out of the
current count.

Total citation volume per period is pinned upstream by the prompt-level citation-rate
quotas, so page shares are rescaled to that total. Rescaling applies one uniform factor,
which preserves the direction and ordering of the stated changes but shifts their
magnitude — `/features/atlas` computes at −19.5% against a stated −16%,
`/blog-post/athena-vs-semrush` at +13.1% against +18%. Page ranking matches the
prototype's ordering on 9 of 10 pages. Pages under 20 citations are excluded from trend
rules entirely, because at that volume a swing is attribution noise rather than signal.

## Charts and colour

The report's chart palette is **not** the prototype's. Validated with the `dataviz`
skill's checker, the prototype's five engine colours fail as a categorical palette: two
near-identical golds (`#C9A961`, `#A8893F`) plus a salmon give a worst adjacent-pair
separation of ΔE 4.4 under deuteranopia against a required 8, and 11.3 for normal vision
against a required 15 — the pair is hard to tell apart even with full colour vision.
`#1A0F2E` also reads as near-black and `#C9A961` fails contrast against the surface.

The replacement keeps the brand's amber/violet/teal character and passes all six checks
in both light and dark mode (worst adjacent ΔE 10.2 deutan, 30.2 normal vision):

```
#B45309  #7C3AED  #0D9488  #E11D48  #2563EB
```

Series colour is assigned by engine identity and never cycled, so re-sorting never
repaints a series. Every bar carries a direct value label and a table view follows the
chart, so nothing depends on reading colour alone. Severity uses a reserved status
palette, always paired with its text label.

## Swapping in live data

`Dataset` (in `dataset.py`) is the only thing that touches the JSON. `metrics.py` and
`insights.py` see nothing but its accessors — `answers()`, `pages`, `prompts`,
`search_console`, `backlinks`. Pointing this at a real AEO API means reimplementing that
one class; everything downstream is unchanged.

## Mapping back to the prototype

| Prototype construct | Line | Replaced by |
|---|---|---|
| `kpiDefs` — 6 KPIs as literals | ~4802 | `metrics.py` — computed from `answers[]` |
| `engineData` | ~4818 | `metrics.compute()` engine rows |
| `brandMetricsData`, `makeLeaderboard` | ~4828 | `metrics._leaderboards()` |
| `citationsData` — page counts as literals | ~4392 | `metrics.page_citation_stats()` |
| `insightsRaw` — 12 insights as literals | ~4548 | `insights.py` — 12 detection rules |
| `severity: 'High'` string literals | ~4550 | `insights.severity_from_score()` |
| hand-written `contributors[]` | ~4557 | `insights._contributors()` — computed |
| `articleBodies`, `changes[]` | ~5137 | `agent.py` draft pass / `fallback.py` |
| `insightDraftPanel` | ~5135 | `narrative.Draft`, `render_draft_markdown()` |

Not carried over: the dashboard UI itself, live engine querying, and CMS publishing. The
prototype's `pepperRequested`, `copilot*`, and wizard state model UI affordances with no
output; the Copilot's recommendation behaviour is covered by the `topic_citation_gap` and
`competitor_prompt_gap` rules instead of a separate mode.
