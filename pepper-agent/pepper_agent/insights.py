"""Insight detection.

The prototype hardcodes twelve insights as literals — severity, headline stat, root
cause, impact, and contributors all typed out by hand (`insightsRaw`, ~line 4548). This
module derives the same *kinds* of finding from the data, which means a given insight
appears only when the numbers support it, and its severity follows from how bad it
actually is.

Twelve rules, each `(Dataset, Metrics) -> list[Insight]`. No LLM: detection is
reproducible and auditable, and the agent's job downstream is to explain and act on
what these rules find, not to decide what is true.

Severity
--------
`score = sqrt(magnitude x reach)`, both normalized to 0-1:

- **magnitude** — how far the metric deviates, scaled against a per-rule reference
  deviation at which the finding is considered fully severe.
- **reach** — the share of the portfolio affected. Every rule expresses this as a true
  fraction of a portfolio total, never an arbitrary divisor, so that severities are
  comparable between rules:

  | Rule family                                  | reach = affected / total   |
  |----------------------------------------------|----------------------------|
  | page citation rules, engine rules            | citations / all citations  |
  | CTR and organic rules                        | impressions / all impressions |
  | prompt and topic rules                       | search volume / all volume |
  | outreach and community rules                 | gainable citations / all citations |

  The units still differ between families — a citation is not an impression — so
  cross-family comparison is approximate. Within a family it is exact.

A geometric mean means neither axis alone carries a finding. A catastrophic drop on a
page nobody reads stays Low; a mild dip across half the portfolio does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from statistics import median
from typing import Callable

from .dataset import Dataset
from .metrics import Metrics, page_citation_stats, pct, signed

SEVERITY_HIGH = 0.45
SEVERITY_MEDIUM = 0.22
SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}

# A page needs this many citations in the current period before a change in its
# citation count is treated as signal. Below it, period-over-period swings are
# dominated by attribution noise and the rule would manufacture findings.
MIN_CITATIONS_FOR_TREND = 20

# A prompt needs this much monthly search volume before a coverage gap is worth
# writing content for.
MIN_VOLUME_FOR_GAP = 1500


def severity_from_score(score: float) -> str:
    if score >= SEVERITY_HIGH:
        return "High"
    if score >= SEVERITY_MEDIUM:
        return "Medium"
    return "Low"


@dataclass
class Insight:
    """One detected finding, with the evidence that produced it."""

    id: str
    rule: str
    title: str
    severity: str
    score: float
    magnitude: float
    reach: float
    stat_value: str
    stat_delta: str
    stat_direction: str
    root_cause: str
    action: str                      # 'update' (existing URL) or 'draft' (new content)
    target_url: str | None = None
    evidence: dict = field(default_factory=dict)
    contributors: list[dict] = field(default_factory=list)
    metrics_at_risk: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _contributors(dataset: Dataset, answers: list[dict], *,
                  extra: list[dict] | None = None) -> list[dict]:
    """Break an affected answer set down by engine, region, and prompt type.

    The prototype's `contributors` are hand-written strings. These are computed: each
    dimension's largest bucket, with its share and absolute count, so a reader can see
    where a finding concentrates.
    """
    if not answers:
        return list(extra or [])

    rows = []
    dimensions: list[tuple[str, Callable[[dict], str]]] = [
        ("Engine", lambda a: a["engine"]),
        ("Region", lambda a: dataset.region_name(a["region"])),
        ("Prompt type", lambda a: (dataset.prompt(a["prompt_id"]) or {}).get(
            "prompt_type", "Unknown")),
    ]
    for label, key in dimensions:
        counts: dict[str, int] = {}
        for answer in answers:
            bucket = key(answer)
            counts[bucket] = counts.get(bucket, 0) + 1
        top, count = max(counts.items(), key=lambda kv: kv[1])
        rows.append({
            "label": label,
            "value": top,
            "share_pct": pct(count, len(answers)),
            "detail": f"{count} of {len(answers)} answers",
        })
    rows.extend(extra or [])
    return rows


# -- rules --------------------------------------------------------------------------

def rule_citation_decline(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """Pages losing citation share faster than the portfolio as a whole.

    Compared against the portfolio's own change rather than against zero: a page down
    5% while the portfolio is up 12% is losing ground, and a page down 5% in a
    portfolio down 8% is not the problem.
    """
    pages = page_citation_stats(dataset)
    total_now = sum(p["citations"] for p in pages)
    total_before = sum(p["citations_prior"] for p in pages)
    portfolio_change = pct(total_now - total_before, total_before) if total_before else 0.0

    out = []
    for page in pages:
        if page["citations"] < MIN_CITATIONS_FOR_TREND:
            continue
        relative = round(page["change_pct"] - portfolio_change, 1)
        if relative > -10.0:
            continue

        cited = [a for a in dataset.answers("current") if a["cited_url"] == page["url"]]
        magnitude = min(1.0, abs(relative) / 40.0)
        reach = page["citations"] / max(total_now, 1)
        score = (magnitude * reach) ** 0.5

        out.append(Insight(
            id="", rule="citation_decline",
            title=f"Citation volume declined for {_path(page['url'])} "
                  f"against a portfolio {'up' if portfolio_change >= 0 else 'down'} "
                  f"{abs(portfolio_change):.1f}%",
            severity=severity_from_score(score), score=round(score, 4),
            magnitude=round(magnitude, 4), reach=round(reach, 4),
            stat_value=f"{page['citations']}",
            stat_delta=f"{signed(page['change_pct'], '%')} vs prior period "
                       f"({signed(relative)} vs portfolio)",
            stat_direction="negative",
            root_cause=(
                f"This page drew {page['citations']} citations this period against "
                f"{page['citations_prior']} last period, a {page['change_pct']:.1f}% move "
                f"while the portfolio as a whole moved {portfolio_change:+.1f}%. Its "
                f"citations concentrate in "
                f"{', '.join(page['engines']) or 'no engine'}, so an engine-side ranking "
                f"shift there shows up here first."
            ),
            action="update", target_url=page["url"],
            evidence={
                "url": page["url"], "citations": page["citations"],
                "citations_prior": page["citations_prior"],
                "change_pct": page["change_pct"],
                "portfolio_change_pct": portfolio_change,
                "relative_change_pts": relative,
                "engines": page["engines"], "top_prompt": page["top_prompt"],
                "avg_citation_position": page["avg_citation_position"],
                "impressions": page["impressions"], "ctr_pct": page["ctr_pct"],
            },
            contributors=_contributors(dataset, cited),
            metrics_at_risk=["Citation rate", "Visibility"],
        ))
    return out


def rule_topic_citation_gap(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """Topics where the brand is cited well below portfolio rate while rivals appear.

    The prototype's equivalent is pinned to pricing prompts. This finds whichever topic
    is actually weak, which on the seed data is not pricing — pricing is the brand's
    strongest topic. That difference is the point: the rule reads the data.
    """
    portfolio_rate = metrics.kpi("citation_rate").value
    total_volume = sum(t["volume"] for t in metrics.topic_rows) or 1

    out = []
    for topic in metrics.topic_rows:
        if topic["citation_rate"] >= portfolio_rate * 0.75:
            continue
        contested_share = pct(topic["competitor_answers"], topic["answers"])
        if contested_share < 40.0:
            continue

        shortfall = portfolio_rate - topic["citation_rate"]
        magnitude = min(1.0, shortfall / portfolio_rate) if portfolio_rate else 0.0
        reach = topic["volume"] / total_volume
        score = (magnitude * reach) ** 0.5
        answers = dataset.answers_for_topic(topic["topic_id"], "current")

        out.append(Insight(
            id="", rule="topic_citation_gap",
            title=f"\"{topic['topic']}\" is cited at {topic['citation_rate']:.1f}% "
                  f"against a {portfolio_rate:.1f}% portfolio rate",
            severity=severity_from_score(score), score=round(score, 4),
            magnitude=round(magnitude, 4), reach=round(reach, 4),
            stat_value=f"{topic['citation_rate']:.1f}%",
            stat_delta=f"{signed(-shortfall)} vs portfolio, across "
                       f"{topic['prompts']} prompts and {topic['volume']:,} monthly searches",
            stat_direction="negative",
            root_cause=(
                f"Across {topic['answers']} answers in this topic the brand earns a "
                f"citation {topic['citation_rate']:.1f}% of the time versus "
                f"{portfolio_rate:.1f}% portfolio-wide, while a tracked competitor is "
                f"named in {contested_share:.1f}% of those answers. Engines are answering "
                f"these questions and sourcing someone else."
            ),
            action="draft",
            evidence={
                "topic": topic["topic"], "topic_id": topic["topic_id"],
                "citation_rate": topic["citation_rate"],
                "portfolio_citation_rate": portfolio_rate,
                "mention_rate": topic["mention_rate"],
                "prompts": topic["prompts"], "volume": topic["volume"],
                "competitor_answer_share_pct": contested_share,
                "example_prompts": [
                    p["text"] for p in dataset.prompts
                    if p["topic_id"] == topic["topic_id"]
                ][:4],
            },
            contributors=_contributors(dataset, answers),
            metrics_at_risk=["Citation rate", "Share of voice"],
        ))
    return out


def rule_rising_page(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """Pages gaining citations and impressions together — worth doubling down on."""
    pages = page_citation_stats(dataset)
    total_now = sum(p["citations"] for p in pages)

    out = []
    for page in pages:
        impressions_change = page.get("impressions_change_pct")
        if page["citations"] < MIN_CITATIONS_FOR_TREND or impressions_change is None:
            continue
        if page["change_pct"] <= 5.0 or impressions_change <= 0:
            continue

        magnitude = min(1.0, (page["change_pct"] + impressions_change) / 60.0)
        reach = page["citations"] / max(total_now, 1)
        score = (magnitude * reach) ** 0.5
        cited = [a for a in dataset.answers("current") if a["cited_url"] == page["url"]]

        out.append(Insight(
            id="", rule="rising_page",
            title=f"{_path(page['url'])} is gaining citations and impressions together",
            severity=severity_from_score(score), score=round(score, 4),
            magnitude=round(magnitude, 4), reach=round(reach, 4),
            stat_value=f"{page['citations']}",
            stat_delta=f"{signed(page['change_pct'], '%')} citations, "
                       f"{signed(impressions_change, '%')} impressions",
            stat_direction="positive",
            root_cause=(
                f"Citations rose {page['change_pct']:.1f}% to {page['citations']} while "
                f"Search Console impressions rose {impressions_change:.1f}% to "
                f"{page['impressions']:,}. AI citation volume and organic demand are "
                f"climbing together, which is the cheapest kind of growth to extend."
            ),
            action="update", target_url=page["url"],
            evidence={
                "url": page["url"], "citations": page["citations"],
                "citations_prior": page["citations_prior"],
                "change_pct": page["change_pct"],
                "impressions": page["impressions"],
                "impressions_change_pct": impressions_change,
                "ctr_pct": page["ctr_pct"], "engines": page["engines"],
                "top_prompt": page["top_prompt"],
            },
            contributors=_contributors(dataset, cited),
            metrics_at_risk=["Citation rate", "Visibility"],
        ))
    return out


def rule_high_impressions_low_ctr(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """Pages with real search demand, weak click-through, and solid AI citations.

    A CTR problem on a page AI engines already trust: the title and description are
    the cheap fix, and there is no AI-visibility risk in touching them.
    """
    pages = [p for p in page_citation_stats(dataset) if p["impressions"] and p["ctr_pct"]]
    if len(pages) < 3:
        return []
    impressions_median = median(p["impressions"] for p in pages)
    # Rounded once here so every consumer — headline, delta, evidence, and the draft
    # templates that read the evidence — prints the same figure. Formatting it
    # separately at each use produced "7.8%" in one sentence and "7.85%" in the next.
    ctr_median = round(median(p["ctr_pct"] for p in pages), 1)
    citations_median = median(p["citations"] for p in pages)
    total_impressions = sum(p["impressions"] for p in pages) or 1

    out = []
    for page in pages:
        if page["impressions"] <= impressions_median or page["ctr_pct"] >= ctr_median:
            continue
        if page["citations"] < citations_median * 0.5:
            continue

        ctr_gap = ctr_median - page["ctr_pct"]
        magnitude = min(1.0, ctr_gap / ctr_median)
        reach = page["impressions"] / total_impressions
        score = (magnitude * reach) ** 0.5

        out.append(Insight(
            id="", rule="high_impressions_low_ctr",
            title=f"Quick win: {_path(page['url'])} draws "
                  f"{page['impressions']:,} impressions at only {page['ctr_pct']:.1f}% CTR",
            severity=severity_from_score(score), score=round(score, 4),
            magnitude=round(magnitude, 4), reach=round(reach, 4),
            stat_value=f"{page['ctr_pct']:.1f}%",
            stat_delta=f"{signed(-ctr_gap)} vs the {ctr_median:.1f}% page median, "
                       f"on {page['impressions']:,} impressions",
            stat_direction="negative",
            root_cause=(
                f"Search demand is landing on this page — {page['impressions']:,} "
                f"impressions at average position {page['search_position']} — but only "
                f"{page['ctr_pct']:.1f}% of it clicks through, against a "
                f"{ctr_median:.1f}% median across tracked pages. It holds "
                f"{page['citations']} AI citations, so the content is credible enough to "
                f"be sourced; the title and meta description are what is not earning the "
                f"click."
            ),
            action="update", target_url=page["url"],
            evidence={
                "url": page["url"], "impressions": page["impressions"],
                "clicks": page["clicks"], "ctr_pct": page["ctr_pct"],
                "ctr_median_pct": ctr_median,
                "search_position": page["search_position"],
                "citations": page["citations"],
                "estimated_clicks_at_median": int(
                    page["impressions"] * ctr_median / 100.0),
            },
            contributors=[
                {"label": "Impressions", "value": f"{page['impressions']:,}",
                 "share_pct": pct(page["impressions"], total_impressions),
                 "detail": "share of tracked-page impressions"},
                {"label": "Clicks forgone", "value": str(int(
                    page["impressions"] * ctr_gap / 100.0)),
                 "share_pct": round(ctr_gap, 1),
                 "detail": "pts of CTR below page median"},
            ],
            metrics_at_risk=["Organic clicks"],
        ))
    return out


def rule_seo_strong_low_citations(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """Pages ranking well organically but rarely cited by AI engines.

    SEO equity that has not converted into AI citations — usually a formatting and
    structured-data problem rather than a content problem.
    """
    pages = [p for p in page_citation_stats(dataset) if p["impressions"] and p["search_position"]]
    if len(pages) < 3:
        return []
    impressions_median = median(p["impressions"] for p in pages)
    citations_median = median(p["citations"] for p in pages)
    total_impressions = sum(p["impressions"] for p in pages) or 1

    out = []
    for page in pages:
        if page["impressions"] <= impressions_median:
            continue
        if page["citations"] >= citations_median:
            continue

        shortfall = citations_median - page["citations"]
        magnitude = min(1.0, shortfall / max(citations_median, 1))
        reach = page["impressions"] / total_impressions
        score = (magnitude * reach) ** 0.5

        out.append(Insight(
            id="", rule="seo_strong_low_citations",
            title=f"AI opportunity: {_path(page['url'])} ranks well organically but "
                  f"holds only {page['citations']} citations",
            severity=severity_from_score(score), score=round(score, 4),
            magnitude=round(magnitude, 4), reach=round(reach, 4),
            stat_value=f"{page['citations']}",
            stat_delta=f"citations vs a {citations_median:.0f} page median, on "
                       f"{page['impressions']:,} impressions at position "
                       f"{page['search_position']}",
            stat_direction="negative",
            root_cause=(
                f"This page earns {page['impressions']:,} impressions at average "
                f"position {page['search_position']}, above the tracked-page median, yet "
                f"AI engines cite it only {page['citations']} times against a median of "
                f"{citations_median:.0f}. Ranking well and being quotable are different "
                f"bars: engines favour direct-answer phrasing and structured data when "
                f"choosing what to source."
            ),
            action="update", target_url=page["url"],
            evidence={
                "url": page["url"], "impressions": page["impressions"],
                "search_position": page["search_position"],
                "ctr_pct": page["ctr_pct"], "citations": page["citations"],
                "citations_median": citations_median,
                "engines": page["engines"], "top_prompt": page["top_prompt"],
            },
            contributors=[
                {"label": "Impressions", "value": f"{page['impressions']:,}",
                 "share_pct": pct(page["impressions"], total_impressions),
                 "detail": "share of tracked-page impressions"},
                {"label": "Citations", "value": str(page["citations"]),
                 "share_pct": pct(page["citations"], citations_median * 2 or 1),
                 "detail": f"vs {citations_median:.0f} median"},
            ],
            metrics_at_risk=["Citation rate", "Visibility"],
        ))
    return out


def rule_competitor_prompt_gap(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """High-volume prompts where competitors are named and the brand is not."""
    total_volume = sum(p["volume"] for p in dataset.prompts) or 1
    portfolio_mention = metrics.kpi("mention_rate").value

    out = []
    for prompt in dataset.prompts:
        if prompt["volume"] < MIN_VOLUME_FOR_GAP:
            continue
        answers = dataset.answers("current", prompt_id=prompt["prompt_id"])
        if not answers:
            continue
        mention = pct(sum(1 for a in answers if a["mentioned"]), len(answers))
        if mention >= portfolio_mention * 0.7:
            continue

        missed = [a for a in answers if not a["mentioned"] and a["competitor_brands"]]
        competitor_share = pct(len(missed), len(answers))
        if competitor_share < 35.0:
            continue

        rival_counts: dict[str, int] = {}
        for answer in missed:
            for brand in answer["competitor_brands"]:
                rival_counts[brand] = rival_counts.get(brand, 0) + 1
        top_rivals = sorted(rival_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]

        magnitude = min(1.0, (portfolio_mention - mention) / portfolio_mention)
        reach = prompt["volume"] / total_volume
        score = (magnitude * reach) ** 0.5

        out.append(Insight(
            id="", rule="competitor_prompt_gap",
            title=f"Content gap: competitors own \"{prompt['text']}\"",
            severity=severity_from_score(score), score=round(score, 4),
            magnitude=round(magnitude, 4), reach=round(reach, 4),
            stat_value=f"{mention:.1f}%",
            stat_delta=f"mention rate vs {portfolio_mention:.1f}% portfolio, on "
                       f"{prompt['volume']:,} monthly searches",
            stat_direction="negative",
            root_cause=(
                f"Across {len(answers)} answers to this prompt the brand is named "
                f"{mention:.1f}% of the time against {portfolio_mention:.1f}% "
                f"portfolio-wide, and in {competitor_share:.1f}% of them a competitor is "
                f"named while the brand is not — most often "
                f"{', '.join(name for name, _ in top_rivals) or 'no single rival'}. "
                f"Engines have an answer for this question and it is not the brand."
            ),
            action="draft",
            evidence={
                "prompt_id": prompt["prompt_id"], "prompt": prompt["text"],
                "topic": dataset.topic_name(prompt["topic_id"]),
                "volume": prompt["volume"], "mention_rate": mention,
                "portfolio_mention_rate": portfolio_mention,
                "answers": len(answers),
                "competitor_only_answers": len(missed),
                "competitor_only_share_pct": competitor_share,
                "top_competitors": [
                    {"brand": name, "answers": count} for name, count in top_rivals
                ],
            },
            contributors=_contributors(dataset, missed),
            metrics_at_risk=["Mention rate", "Share of voice"],
        ))
    return out


def rule_sentiment_divergence(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """Topics where the brand is mentioned more often but portrayed less favourably."""
    out = []
    for topic in metrics.topic_rows:
        now = dataset.answers_for_topic(topic["topic_id"], "current")
        before = dataset.answers_for_topic(topic["topic_id"], "prior")
        if not now or not before:
            continue

        from .metrics import mention_rate as _mr, sentiment_score as _ss
        mention_delta = round(_mr(now) - _mr(before), 1)
        sentiment_delta = round(_ss(now) - _ss(before), 1)
        if mention_delta <= 1.0 or sentiment_delta >= -1.0:
            continue

        total_volume = sum(t["volume"] for t in metrics.topic_rows) or 1
        magnitude = min(1.0, abs(sentiment_delta) / 10.0)
        reach = topic["volume"] / total_volume
        score = (magnitude * reach) ** 0.5

        out.append(Insight(
            id="", rule="sentiment_divergence",
            title=f"Sentiment risk: \"{topic['topic']}\" mentions are up "
                  f"{mention_delta:.1f} pts while sentiment is down "
                  f"{abs(sentiment_delta):.1f}",
            severity=severity_from_score(score), score=round(score, 4),
            magnitude=round(magnitude, 4), reach=round(reach, 4),
            stat_value=f"{topic['sentiment']:.1f}",
            stat_delta=f"sentiment {signed(sentiment_delta, '')} while mentions "
                       f"{signed(mention_delta)}",
            stat_direction="negative",
            root_cause=(
                f"Engines mention the brand more often in this topic than last period "
                f"({signed(mention_delta)} to {topic['mention_rate']:.1f}%) but frame it "
                f"less favourably ({signed(sentiment_delta, '')} to "
                f"{topic['sentiment']:.1f}). Rising visibility on softening sentiment "
                f"means more people are seeing a weaker version of the story."
            ),
            action="draft",
            evidence={
                "topic": topic["topic"], "topic_id": topic["topic_id"],
                "mention_rate": topic["mention_rate"],
                "mention_delta_pts": mention_delta,
                "sentiment": topic["sentiment"],
                "sentiment_delta": sentiment_delta,
                "answers": topic["answers"], "volume": topic["volume"],
            },
            contributors=_contributors(
                dataset, [a for a in now if a["mentioned"] and a["sentiment"] != "Positive"]),
            metrics_at_risk=["Sentiment"],
        ))
    return out


def rule_engine_concentration(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """Citation volume concentrated in one engine — a single-point-of-failure risk."""
    rows = sorted(metrics.engine_rows, key=lambda r: r["citation_share"], reverse=True)
    if len(rows) < 2:
        return []
    top = rows[0]
    even_share = 100.0 / len(rows)
    if top["citation_share"] < even_share * 1.5:
        return []

    excess = top["citation_share"] - even_share
    magnitude = min(1.0, excess / even_share)
    reach = top["citation_share"] / 100.0
    score = (magnitude * reach) ** 0.5
    cited = [a for a in dataset.answers("current", engine=top["engine"]) if a["brand_cited"]]

    return [Insight(
        id="", rule="engine_concentration",
        title=f"Engine concentration: {top['citation_share']:.1f}% of citations come "
              f"from {top['engine']} alone",
        severity=severity_from_score(score), score=round(score, 4),
        magnitude=round(magnitude, 4), reach=round(reach, 4),
        stat_value=f"{top['citation_share']:.1f}%",
        stat_delta=f"vs {even_share:.1f}% if citations were spread evenly across "
                   f"{len(rows)} engines",
        stat_direction="negative",
        root_cause=(
            f"{top['brand_citations']} of "
            f"{sum(r['brand_citations'] for r in rows)} brand citations come from "
            f"{top['engine']}. An even spread would be {even_share:.1f}% per engine; this "
            f"is {top['citation_share']:.1f}%. A ranking change at one provider would "
            f"take a disproportionate share of total visibility with it."
        ),
        action="draft",
        evidence={
            "top_engine": top["engine"],
            "top_engine_share_pct": top["citation_share"],
            "even_share_pct": round(even_share, 1),
            "engine_shares": [
                {"engine": r["engine"], "share_pct": r["citation_share"],
                 "citations": r["brand_citations"]} for r in rows
            ],
        },
        contributors=_contributors(dataset, cited),
        metrics_at_risk=["Citation rate", "Visibility"],
    )]


def rule_underindexed_engine(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """An engine where the brand is far below its share of the tracked set."""
    rows = sorted(metrics.engine_rows, key=lambda r: r["citation_share"])
    if len(rows) < 2:
        return []
    weakest = rows[0]
    strongest = rows[-1]
    even_share = 100.0 / len(rows)
    if weakest["citation_share"] > even_share * 0.55:
        return []

    magnitude = min(1.0, (even_share - weakest["citation_share"]) / even_share)
    # Reach is what could be gained by reaching even share, not what is held today.
    reach = (even_share - weakest["citation_share"]) / 100.0
    score = (magnitude * reach) ** 0.5

    return [Insight(
        id="", rule="underindexed_engine",
        title=f"Untapped engine: {weakest['engine']} carries only "
              f"{weakest['citation_share']:.1f}% of citations",
        severity=severity_from_score(score), score=round(score, 4),
        magnitude=round(magnitude, 4), reach=round(reach, 4),
        stat_value=f"{weakest['citation_share']:.1f}%",
        stat_delta=f"vs {strongest['citation_share']:.1f}% on "
                   f"{strongest['engine']} and {even_share:.1f}% even share",
        stat_direction="negative",
        root_cause=(
            f"{weakest['engine']} cites the brand {weakest['brand_citations']} times "
            f"({weakest['citation_share']:.1f}% of all citations) at a citation rate of "
            f"{weakest['citation_rate']:.1f}%, against {strongest['citation_rate']:.1f}% "
            f"on {strongest['engine']}. Content that satisfies one engine's sourcing "
            f"preferences is not satisfying this one's."
        ),
        action="draft",
        evidence={
            "engine": weakest["engine"],
            "citation_share_pct": weakest["citation_share"],
            "citation_rate": weakest["citation_rate"],
            "mention_rate": weakest["mention_rate"],
            "avg_position": weakest["avg_position"],
            "answers": weakest["answers"],
            "strongest_engine": strongest["engine"],
            "strongest_citation_rate": strongest["citation_rate"],
            "even_share_pct": round(even_share, 1),
        },
        contributors=_contributors(
            dataset, dataset.answers("current", engine=weakest["engine"])),
        metrics_at_risk=["Citation rate", "Share of voice"],
    )]


def rule_stale_high_value(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """Well-cited pages that have not been refreshed and are slipping in position."""
    pages = page_citation_stats(dataset)
    if not pages:
        return []
    citations_median = median(p["citations"] for p in pages)
    total_now = sum(p["citations"] for p in pages) or 1

    out = []
    for page in pages:
        months = page.get("months_since_update")
        if months is None or months < 6 or page["citations"] < citations_median:
            continue

        was = page.get("avg_citation_position_6mo_ago")
        now_pos = page["avg_citation_position"]
        slipped = (was is not None and now_pos is not None and now_pos > was)

        magnitude = min(1.0, months / 12.0)
        if slipped:
            magnitude = min(1.0, magnitude + (now_pos - was) / 4.0)
        reach = page["citations"] / total_now
        score = (magnitude * reach) ** 0.5

        position_note = (
            f"Average citation position has slipped from {was} to {now_pos}."
            if slipped else
            f"Average citation position is holding at {now_pos}."
        )

        out.append(Insight(
            id="", rule="stale_high_value",
            title=f"Refresh candidate: {_path(page['url'])} holds "
                  f"{page['citations']} citations on content {months} months old",
            severity=severity_from_score(score), score=round(score, 4),
            magnitude=round(magnitude, 4), reach=round(reach, 4),
            stat_value=f"{page['citations']}",
            stat_delta=f"citations, last updated {months} months ago",
            stat_direction="neutral",
            root_cause=(
                f"Engines still cite this page {page['citations']} times, above the "
                f"{citations_median:.0f} median, but the content has not been touched in "
                f"{months} months. {position_note} Competitors publishing more current "
                f"material on the same question is the usual reason a proven page starts "
                f"drifting down."
            ),
            action="update", target_url=page["url"],
            evidence={
                "url": page["url"], "citations": page["citations"],
                "citations_median": citations_median,
                "months_since_update": months,
                "avg_citation_position": now_pos,
                "avg_citation_position_6mo_ago": was,
                "position_slipped": slipped,
                "engines": page["engines"], "top_prompt": page["top_prompt"],
            },
            contributors=_contributors(
                dataset,
                [a for a in dataset.answers("current") if a["cited_url"] == page["url"]]),
            metrics_at_risk=["Citation rate", "Avg. position"],
        ))
    return out


def rule_unlinked_mentions(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """High-authority domains naming the brand without a followed link or citation."""
    candidates = [
        b for b in dataset.backlinks
        if b.get("unlinked_mentions", 0) > 0 and b["authority_score"] >= 60
    ]
    if not candidates:
        return []

    mentions = sum(b["unlinked_mentions"] for b in candidates)
    avg_authority = sum(b["authority_score"] for b in candidates) / len(candidates)
    total_citations = sum(r["brand_citations"] for r in metrics.engine_rows) or 1

    magnitude = min(1.0, avg_authority / 100.0)
    # Each unlinked mention is one citation that could be converted, so reach is that
    # gain measured against the citations already earned.
    reach = min(1.0, mentions / total_citations)
    score = (magnitude * reach) ** 0.5

    return [Insight(
        id="", rule="unlinked_mentions",
        title=f"Outreach opportunity: {mentions} unlinked brand mentions on "
              f"authority-{int(avg_authority)}+ domains",
        severity=severity_from_score(score), score=round(score, 4),
        magnitude=round(magnitude, 4), reach=round(reach, 4),
        stat_value=str(mentions),
        stat_delta=f"across {len(candidates)} domains averaging authority "
                   f"{avg_authority:.0f}",
        stat_direction="neutral",
        root_cause=(
            f"{', '.join(b['domain'] for b in candidates)} already name the brand "
            f"without linking or attributing a source. These are citations sitting one "
            f"email away, against a current base of {total_citations} earned citations."
        ),
        action="draft",
        evidence={
            "unlinked_mentions": mentions,
            "avg_authority": round(avg_authority, 1),
            "domains": [
                {"domain": b["domain"], "authority_score": b["authority_score"],
                 "unlinked_mentions": b["unlinked_mentions"],
                 "link_type": b["link_type"], "existing_links": b["count"]}
                for b in candidates
            ],
            "current_total_citations": total_citations,
        },
        contributors=[
            {"label": "Domains", "value": str(len(candidates)),
             "share_pct": 100.0, "detail": "with unlinked mentions"},
            {"label": "Avg authority", "value": f"{avg_authority:.0f}",
             "share_pct": round(avg_authority, 1), "detail": "across those domains"},
        ],
        metrics_at_risk=["Citation rate"],
    )]


def rule_community_gap(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """Active community threads discussing the brand with no official presence.

    Engines cite forum threads directly, so a discussion the brand is absent from is a
    source the brand does not shape.
    """
    threads = [b for b in dataset.backlinks if b.get("community_threads", 0) > 0]
    if not threads:
        return []

    total_threads = sum(b["community_threads"] for b in threads)
    top = max(threads, key=lambda b: b["community_threads"])
    total_citations = sum(r["brand_citations"] for r in metrics.engine_rows) or 1

    magnitude = min(1.0, top["authority_score"] / 100.0)
    # Each thread is a source an engine could cite, so reach is that potential measured
    # against citations already earned — the same basis the outreach rule uses.
    reach = min(1.0, total_threads / total_citations)
    score = (magnitude * reach) ** 0.5

    return [Insight(
        id="", rule="community_gap",
        title=f"Community gap: {total_threads} threads discuss the brand on "
              f"{top['domain']} with no official presence",
        severity=severity_from_score(score), score=round(score, 4),
        magnitude=round(magnitude, 4), reach=round(reach, 4),
        stat_value=str(total_threads),
        stat_delta=f"active threads on authority-{top['authority_score']} domains",
        stat_direction="neutral",
        root_cause=(
            f"{top['domain']} carries {top['community_threads']} threads mentioning the "
            f"brand at domain authority {top['authority_score']}, and engines cite "
            f"community threads directly when answering. The conversation is happening "
            f"in a source engines trust, without the brand in it."
        ),
        action="draft",
        evidence={
            "total_threads": total_threads,
            "domains": [
                {"domain": b["domain"], "threads": b["community_threads"],
                 "authority_score": b["authority_score"]} for b in threads
            ],
        },
        contributors=[
            {"label": "Threads", "value": str(total_threads),
             "share_pct": 100.0, "detail": f"on {len(threads)} community domains"},
            {"label": "Top domain", "value": top["domain"],
             "share_pct": pct(top["community_threads"], total_threads),
             "detail": f"authority {top['authority_score']}"},
        ],
        metrics_at_risk=["Mention rate", "Citation rate"],
    )]


RULES: tuple[Callable[[Dataset, Metrics], list[Insight]], ...] = (
    rule_citation_decline,
    rule_topic_citation_gap,
    rule_rising_page,
    rule_high_impressions_low_ctr,
    rule_seo_strong_low_citations,
    rule_competitor_prompt_gap,
    rule_sentiment_divergence,
    rule_engine_concentration,
    rule_underindexed_engine,
    rule_stale_high_value,
    rule_unlinked_mentions,
    rule_community_gap,
)


def _path(url: str) -> str:
    """Trim a tracked URL down to its path for use in a headline."""
    for prefix in ("www.", "https://", "http://"):
        url = url.removeprefix(prefix)
    slash = url.find("/")
    return url[slash:] if slash != -1 else url


def detect(dataset: Dataset, metrics: Metrics) -> list[Insight]:
    """Run every rule and return findings ranked most severe first.

    Ties inside a severity band break on score, so the ordering is total and stable —
    the same dataset always yields the same ranked list, which is what lets the agent's
    "top N" selection be reproducible.
    """
    found: list[Insight] = []
    for rule in RULES:
        found.extend(rule(dataset, metrics))

    found.sort(key=lambda i: (SEVERITY_ORDER[i.severity], -i.score))
    for index, insight in enumerate(found, start=1):
        insight.id = f"ins_{index:02d}"
    return found


def summarize(insights: list[Insight]) -> dict:
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for insight in insights:
        counts[insight.severity] += 1
    return {
        "total": len(insights),
        "by_severity": counts,
        "by_action": {
            "update": sum(1 for i in insights if i.action == "update"),
            "draft": sum(1 for i in insights if i.action == "draft"),
        },
        "rules_fired": sorted({i.rule for i in insights}),
        "rules_available": [r.__name__.removeprefix("rule_") for r in RULES],
    }
