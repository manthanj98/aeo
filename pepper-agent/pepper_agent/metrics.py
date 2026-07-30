"""KPI computation.

The six KPIs are the ones the prototype defines in `kpiDefs` (~line 4802) but never
computes. The definitions there are real and usable, so they are implemented verbatim
where the prototype states a formula; the one exception is Visibility, whose stated
definition ("weighted by mention rate, position, and share of voice") is prose rather
than arithmetic. See `visibility_score` for the formula chosen and why.

Everything here is computed from `answers[]`. No LLM is involved, so a given dataset
always produces the same numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import mean

from .dataset import Dataset

# Sentiment maps to a 0-100 score: positive counts full, neutral counts half, negative
# counts zero. Straight from the prototype's Sentiment definition.
SENTIMENT_WEIGHT = {"Positive": 1.0, "Neutral": 0.5, "Negative": 0.0}


def pct(numerator: float, denominator: float) -> float:
    """Percentage, rounded to one decimal, guarding a zero denominator.

    One decimal everywhere is a brand guideline ("Round percentages to one decimal
    place in customer-facing reports"), and it also keeps a column from mixing
    "+2 pts" with "+1.3 pts" the way the prototype's `signed1` helper guards against.
    """
    if not denominator:
        return 0.0
    return round(100.0 * numerator / denominator, 1)


def signed(value: float, unit: str = " pts") -> str:
    """Format a delta with an explicit sign and one decimal."""
    return f"{'+' if value >= 0 else ''}{value:.1f}{unit}"


@dataclass
class Kpi:
    key: str
    label: str
    value: float
    unit: str
    trend: float
    definition: str
    higher_is_better: bool = True

    @property
    def display(self) -> str:
        if self.unit == "%":
            return f"{self.value:.1f}%"
        return f"{self.value:.1f}"

    @property
    def trend_display(self) -> str:
        if abs(self.trend) < 0.05:
            return "steady"
        return signed(self.trend, " pts" if self.unit == "%" else "")

    @property
    def direction(self) -> str:
        """'up' / 'down' / 'flat' in the sense of *good for the brand*."""
        if abs(self.trend) < 0.05:
            return "flat"
        improving = (self.trend > 0) if self.higher_is_better else (self.trend < 0)
        return "up" if improving else "down"

    def to_dict(self) -> dict:
        return {**asdict(self), "display": self.display,
                "trend_display": self.trend_display, "direction": self.direction}


# -- individual KPIs, each over a list of answer rows --------------------------------

def mention_rate(answers: list[dict]) -> float:
    """Answers mentioning the brand, over total answers."""
    return pct(sum(1 for a in answers if a["mentioned"]), len(answers))


def share_of_voice(answers: list[dict]) -> float:
    """Brand mention volume as a share of all tracked-brand mention volume.

    Each competitor named in an answer counts as its own mention, so an answer listing
    three competitors alongside the brand contributes one brand mention against three
    competitor mentions.

    This departs from the prototype's tooltip, which says "answers mentioning your
    brand divided by answers mentioning your brand OR competitors". That reading is
    arithmetically incapable of producing the prototype's own stated 21% next to a 58%
    mention rate: a share-of-*answers* ratio has the brand's own mentions in the
    numerator and a superset in the denominator, so it can never fall to a third of the
    mention rate. The volume-share reading — the standard industry definition — lands
    at 23.1% on this dataset against the stated 21%, so that is what is implemented.
    See README.md "KPI reconciliation".
    """
    brand = sum(1 for a in answers if a["mentioned"])
    competitor = sum(len(a["competitor_brands"]) for a in answers)
    return pct(brand, brand + competitor)


def contested_answer_share(answers: list[dict]) -> float:
    """Share of answers that mention the brand or any tracked competitor.

    Not a headline KPI — it is the denominator context the content-gap rules need to
    tell "nobody is discussed here" apart from "competitors are, and we are not".
    """
    contested = sum(1 for a in answers if a["mentioned"] or a["competitor_brands"])
    return pct(contested, len(answers))


def citation_rate(answers: list[dict]) -> float:
    """Answers citing the brand domain, over answers with at least one citation.

    The prototype's definition notes that multiple URLs from the same domain count
    once; the fact table already records one `brand_cited` flag per answer, so
    per-domain deduplication is structural here rather than a step to perform.
    """
    with_citations = [a for a in answers if a["has_citations"]]
    return pct(sum(1 for a in with_citations if a["brand_cited"]), len(with_citations))


def sentiment_score(answers: list[dict]) -> float:
    """(positive + 0.5 x neutral) / total brand mentions, scaled 0-100."""
    mentions = [a for a in answers if a["mentioned"] and a["sentiment"]]
    if not mentions:
        return 0.0
    weighted = sum(SENTIMENT_WEIGHT.get(a["sentiment"], 0.0) for a in mentions)
    return round(100.0 * weighted / len(mentions), 1)


def avg_position(answers: list[dict]) -> float:
    """Mean ordinal position of the brand across answers that mention it."""
    positions = [a["position"] for a in answers if a["mentioned"] and a["position"]]
    return round(mean(positions), 1) if positions else 0.0


def mean_reciprocal_rank(answers: list[dict]) -> float:
    """Mean of 1/position over all answers, counting a non-mention as zero.

    Standard information-retrieval MRR. It folds mention rate and position into one
    number: being mentioned first in half the answers scores 0.5, being mentioned
    third in all of them scores 0.33.
    """
    if not answers:
        return 0.0
    total = sum(
        1.0 / a["position"] for a in answers
        if a["mentioned"] and a["position"]
    )
    return total / len(answers)


def visibility_score(answers: list[dict]) -> float:
    """Overall visibility, 0-100.

    The prototype describes this as "weighted by mention rate, position, and share of
    voice" but gives no arithmetic. Implemented as the geometric mean of mean
    reciprocal rank and share of voice:

        visibility = sqrt(MRR x share_of_voice)

    MRR carries mention rate and position together; share of voice carries the
    competitive dimension. A geometric mean means a brand cannot post a strong
    visibility score by dominating one axis while failing the other, which is the
    property that makes the number worth reporting as a headline.

    This does not reproduce the prototype's literal 34% — see README.md
    "KPI reconciliation". The prototype's figure is a hardcoded string with no
    derivation to match.
    """
    mrr = mean_reciprocal_rank(answers) * 100.0
    sov = share_of_voice(answers)
    return round((mrr * sov) ** 0.5, 1)


# -- KPI set ------------------------------------------------------------------------

KPI_SPECS = (
    ("visibility_score", "Visibility", "%", visibility_score, True,
     "Geometric mean of mean reciprocal rank and share of voice, 0-100. Combines how "
     "often and how prominently the brand appears with how it fares against competitors."),
    ("mention_rate", "Mention rate", "%", mention_rate, True,
     "Answers mentioning your brand divided by total answers. Higher means greater visibility."),
    ("share_of_voice", "Share of voice", "%", share_of_voice, True,
     "Brand mentions as a share of all tracked-brand mention volume — each competitor "
     "named in an answer counts as its own mention. Higher means you dominate the "
     "conversation relative to competitors."),
    ("citation_rate", "Citation rate", "%", citation_rate, True,
     "Answers citing your domain divided by answers with at least one citation. Multiple "
     "URLs from the same domain count once. Higher indicates greater authority."),
    ("sentiment", "Sentiment", "", sentiment_score, True,
     "Positive mentions plus half of neutral mentions, divided by total brand mentions "
     "(0-100). Higher indicates better portrayal by AI platforms."),
    ("avg_position", "Avg. position", "", avg_position, False,
     "Average position where your brand is mentioned in AI answers (1 = first). Lower "
     "means earlier, more prominent mentions."),
)


@dataclass
class Metrics:
    """Computed KPIs plus the engine and competitor breakdowns."""

    kpis: list[Kpi]
    engine_rows: list[dict]
    leaderboards: list[dict]
    topic_rows: list[dict]
    answer_counts: dict[str, int]

    def kpi(self, key: str) -> Kpi:
        for item in self.kpis:
            if item.key == key:
                return item
        raise KeyError(key)

    def to_dict(self) -> dict:
        return {
            "kpis": [k.to_dict() for k in self.kpis],
            "engines": self.engine_rows,
            "leaderboards": self.leaderboards,
            "topics": self.topic_rows,
            "answer_counts": self.answer_counts,
        }


def compute(dataset: Dataset) -> Metrics:
    current = dataset.answers("current")
    prior = dataset.answers("prior")

    kpis = []
    for key, label, unit, fn, higher_is_better, definition in KPI_SPECS:
        now = fn(current)
        before = fn(prior)
        kpis.append(Kpi(
            key=key, label=label, value=now, unit=unit,
            trend=round(now - before, 1), definition=definition,
            higher_is_better=higher_is_better,
        ))

    engine_rows = []
    for engine in dataset.engines:
        rows_now = dataset.answers("current", engine=engine["name"])
        rows_before = dataset.answers("prior", engine=engine["name"])
        cited_now = [a for a in rows_now if a["brand_cited"]]
        engine_rows.append({
            "engine": engine["name"],
            "color": engine.get("color", "#4A2C7A"),
            "answers": len(rows_now),
            "visibility_score": visibility_score(rows_now),
            "mention_rate": mention_rate(rows_now),
            "mention_trend": round(mention_rate(rows_now) - mention_rate(rows_before), 1),
            "share_of_voice": share_of_voice(rows_now),
            "citation_rate": citation_rate(rows_now),
            "citation_trend": round(citation_rate(rows_now) - citation_rate(rows_before), 1),
            "sentiment": sentiment_score(rows_now),
            "avg_position": avg_position(rows_now),
            "brand_citations": len(cited_now),
        })

    # Citation share is each engine's slice of total brand citations — the input to the
    # engine-concentration and under-indexed-engine rules.
    total_citations = sum(r["brand_citations"] for r in engine_rows) or 1
    for row in engine_rows:
        row["citation_share"] = pct(row["brand_citations"], total_citations)

    leaderboards = _leaderboards(dataset)
    topic_rows = _topic_rows(dataset)

    return Metrics(
        kpis=kpis,
        engine_rows=engine_rows,
        leaderboards=leaderboards,
        topic_rows=topic_rows,
        answer_counts={"current": len(current), "prior": len(prior)},
    )


def _leaderboards(dataset: Dataset) -> list[dict]:
    """Rank the brand against competitors on each metric.

    The brand's own row is recomputed from `answers[]`; competitor rows come from the
    prototype's static competitor table, because the dataset carries no answer-level
    data for competitors. Each leaderboard flags this so a reader knows which numbers
    are computed and which are carried over.
    """
    current = dataset.answers("current")
    computed = {
        "mention_rate": mention_rate(current),
        "citation_rate": citation_rate(current),
        "share_of_voice": share_of_voice(current),
        "sentiment": sentiment_score(current),
        "avg_position": avg_position(current),
    }

    specs = (
        ("mention_rate", "Mention Rate", "%", False),
        ("citation_rate", "Citation Rate", "%", False),
        ("share_of_voice", "Share of Voice", "%", False),
        ("sentiment", "Sentiment", "", False),
        ("avg_position", "Average Position", "", True),
    )

    boards = []
    for key, label, unit, lower_is_better in specs:
        rows = []
        for entry in dataset.reference_brand_metrics:
            is_you = entry["is_you"]
            rows.append({
                "name": entry["name"],
                "value": computed[key] if is_you else float(entry[key]),
                "is_you": is_you,
                "source": "computed" if is_you else "reference",
            })
        rows.sort(key=lambda r: r["value"], reverse=not lower_is_better)
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
            row["display"] = f"{row['value']:.1f}{unit}"
        boards.append({
            "key": key, "label": label, "rows": rows,
            "brand_rank": next(r["rank"] for r in rows if r["is_you"]),
            "field_size": len(rows),
        })
    return boards


def _topic_rows(dataset: Dataset) -> list[dict]:
    """Per-topic rollup — the unit the content-gap rules operate on."""
    rows = []
    for topic in dataset.topics:
        now = dataset.answers_for_topic(topic["id"], "current")
        before = dataset.answers_for_topic(topic["id"], "prior")
        if not now:
            continue
        prompt_ids = {a["prompt_id"] for a in now}
        volume = sum(
            p["volume"] for p in dataset.prompts if p["prompt_id"] in prompt_ids
        )
        rows.append({
            "topic_id": topic["id"],
            "topic": topic["name"],
            "prompts": len(prompt_ids),
            "volume": volume,
            "answers": len(now),
            "mention_rate": mention_rate(now),
            "citation_rate": citation_rate(now),
            "citation_trend": round(citation_rate(now) - citation_rate(before), 1),
            "share_of_voice": share_of_voice(now),
            "sentiment": sentiment_score(now),
            "brand_citations": sum(1 for a in now if a["brand_cited"]),
            "competitor_answers": sum(1 for a in now if a["competitor_brands"]),
        })
    rows.sort(key=lambda r: r["volume"], reverse=True)
    return rows


def page_citation_stats(dataset: Dataset) -> list[dict]:
    """Per-page citation counts and period-over-period change, computed from answers.

    The prototype states `citations_count` and `change_vs_previous` as literals. Here
    both come out of the fact table by counting which answers cited which URL, so a
    page's decline is an observation rather than an assertion. The page table's stated
    counts are carried alongside as `stated_citations` for comparison.
    """
    stats = []
    for page in dataset.pages:
        url = page["url"]
        now = [a for a in dataset.answers("current") if a["cited_url"] == url]
        before = [a for a in dataset.answers("prior") if a["cited_url"] == url]
        count_now, count_before = len(now), len(before)
        change = pct(count_now - count_before, count_before) if count_before else 0.0
        positions = [a["position"] for a in now if a["position"]]
        engines_now = sorted({a["engine"] for a in now})
        sc = dataset.sc_row(url) or {}
        stats.append({
            "url": url,
            "top_prompt": page["top_prompt"],
            "citations": count_now,
            "citations_prior": count_before,
            "change_pct": change,
            "stated_citations": page["citations_count"],
            "avg_citation_position": round(mean(positions), 1) if positions else None,
            "stated_avg_citation_position": page["avg_citation_position"],
            "engines": engines_now,
            "months_since_update": page.get("months_since_update"),
            "avg_citation_position_6mo_ago": page.get("avg_citation_position_6mo_ago"),
            "sentiment_delta_pct": page.get("sentiment_delta_pct"),
            "impressions": sc.get("impressions"),
            "clicks": sc.get("clicks"),
            "ctr_pct": sc.get("ctr_pct"),
            "search_position": sc.get("position"),
            "impressions_change_pct": sc.get("impressions_change_pct"),
        })
    stats.sort(key=lambda r: r["citations"], reverse=True)
    return stats
