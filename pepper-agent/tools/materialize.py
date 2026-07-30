#!/usr/bin/env python3
"""Expand the prototype's aggregate tables into an answer-level fact table.

The prototype (`prototype/pepperproject.standalone.html`) states every metric as a
literal: per-prompt mention/citation rates, per-engine rates, per-page citation counts.
Nothing is computed from anything. The agent needs the opposite arrangement — the
answer-level facts those aggregates would have been rolled up from — so that
`metrics.py` genuinely computes KPIs and `insights.py` genuinely detects patterns.

This script does that expansion once, deterministically (seeded PRNG), and the result
is committed as `data/visibility.json`. Run it again only if `data/source_tables.json`
changes:

    python tools/materialize.py

Marginal fitting, and one inconsistency in the source
-----------------------------------------------------
Each (prompt, engine) cell needs a mention probability that reproduces two marginals
at once: the prompt's stated rate when summed over engines, and the engine's stated
rate when summed over prompts. This uses the standard rank-one approximation

    p(mention | prompt, engine) = prompt_rate * engine_rate / mean_engine_rate

clamped to [0, 1], which preserves the prompt marginal exactly in expectation.

The two marginals cannot both be satisfied, because the prototype's own tables
disagree about the overall level: `trackedPrompts` averages 44.4% mention rate while
`engineData` averages 53.8%. No joint distribution has both as marginals. The finer-
grained prompt table is treated as authoritative for the level, and the engine table
for relative ordering between engines — so recovered engine rates come out uniformly
scaled by 44.4/53.8 ≈ 0.82 while preserving the stated ranking. `--report` prints the
residuals against both the raw and the level-adjusted engine targets.

Within a cell, mentions are allocated by quota (exactly round(runs x p) of the runs,
randomly chosen) rather than by independent coin flips. Bernoulli sampling at 10 runs
per cell adds about 7 points of binomial noise per prompt, which would swamp the
signal the detection rules read; quota allocation drops the residual to rounding.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "source_tables.json"
TARGET = ROOT / "data" / "visibility.json"

# Answer-level sentiment buckets. The prototype only gives a per-prompt
# `positive_rate`; the remainder is split between neutral and negative, weighted
# toward neutral because AI answers rarely disparage a brand outright.
NEUTRAL_SHARE_OF_REMAINDER = 0.72

# Answers are dated across the period so trend windows and "last 7 days" style
# filters have something real to slice on.
PERIOD_DAYS = {"current": ("2026-06", 1, 30), "prior": ("2026-05", 1, 31)}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def engine_run_counts(engines: list[dict], total_runs: int) -> dict[str, int]:
    """Split a prompt's runs across engines so the stated citation shares come out.

    Engines are not sampled equally, and it matters. The prototype's `engineData` gives
    both a citation *rate* (52% for ChatGPT down to 36% for Claude — a narrow spread)
    and a citation *share* (34% down to 8% — a wide one). Those only reconcile if
    engines differ in how many answers they contribute, not just in how often they
    cite: share = runs x rate, so runs is proportional to share / rate.

    Sampling engines equally would flatten citation share to roughly 20% each and hide
    the single-engine concentration the data actually carries.
    """
    weights = {e["name"]: e["citation_share"] / e["citation_rate"] for e in engines}
    total = sum(weights.values())
    counts = {name: int(round(total_runs * w / total)) for name, w in weights.items()}
    # Push any rounding slack onto the largest engine so the per-prompt total is exact.
    drift = total_runs - sum(counts.values())
    if drift:
        counts[max(counts, key=lambda n: counts[n])] += drift
    return counts


def weighted_choice(rng: random.Random, items: list, weights: list[float]):
    total = sum(weights)
    if total <= 0:
        return rng.choice(items)
    threshold = rng.random() * total
    running = 0.0
    for item, weight in zip(items, weights):
        running += weight
        if running >= threshold:
            return item
    return items[-1]


def quota_flags(rng: random.Random, n: int, probability: float) -> list[bool]:
    """Return n booleans of which exactly round(n * probability) are True.

    Independent Bernoulli draws at n=10 carry roughly 15 points of standard error per
    cell, which accumulates into several points per prompt and muddies the very
    deviations the detection rules look for. Fixing the count per cell and shuffling
    which runs carry it keeps the fact table realistic while holding the marginals to
    rounding error.
    """
    hits = int(round(n * probability))
    flags = [True] * hits + [False] * (n - hits)
    rng.shuffle(flags)
    return flags


def sample_position(rng: random.Random, engine_avg: float) -> int:
    """Draw a mention position centred on the engine's average position.

    Positions are 1-indexed ordinals, so the distribution is discrete and skewed
    right: an engine averaging 2.1 puts most mentions at 1-3 with a thin tail.
    """
    drawn = rng.gauss(engine_avg, 0.9)
    return max(1, min(8, int(round(drawn))))


def assign_cited_urls(rng: random.Random, answers: list[dict], pages: list[dict],
                      period: str) -> None:
    """Attribute each brand citation in `period` to a page, by exact quota.

    Independent weighted draws leave page totals with enough sampling noise that a
    page's period-over-period change is mostly noise — at 20-ish citations a page can
    swing 30% either way for no reason. Allocating exact per-page quotas removes that,
    so a page's computed change reflects the target share rather than the draw.

    Targets come from the page table's stated citation counts; for the prior period,
    from the count implied by backing the stated `change_vs_previous_pct` out. Total
    citation volume per period is pinned by the prompt-level citation-rate quotas
    upstream, so the shares are rescaled to that total. Rescaling applies one uniform
    factor across all pages, which preserves direction and ordering of the stated
    changes but shifts their magnitude — see README.md "Page-level reconciliation".
    """
    cited = [a for a in answers if a["period"] == period and a["brand_cited"]]
    if not cited:
        return

    if period == "current":
        weights = {p["url"]: float(p["citations_count"]) for p in pages}
    else:
        weights = {
            p["url"]: p["citations_count"] / (1.0 + p["change_vs_previous_pct"] / 100.0)
            for p in pages
        }
    total_weight = sum(weights.values())
    quota = {
        url: int(round(len(cited) * weight / total_weight))
        for url, weight in weights.items()
    }

    eligible: dict[str, list[str]] = {}
    for page in pages:
        for engine in page["engines"]:
            eligible.setdefault(engine, []).append(page["url"])

    # Shuffle so the leftover assignments aren't biased toward early answers, then
    # give each citation to the eligible page furthest from filling its quota.
    order = list(cited)
    rng.shuffle(order)
    remaining = dict(quota)
    for answer in order:
        candidates = eligible.get(answer["engine"]) or [p["url"] for p in pages]
        best = max(candidates, key=lambda url: remaining.get(url, 0))
        if remaining.get(best, 0) <= 0:
            # Every eligible page is at quota (rounding slack); fall back to the
            # largest page for this engine so no citation is dropped.
            best = max(candidates, key=lambda url: weights[url])
        remaining[best] = remaining.get(best, 0) - 1
        answer["cited_url"] = best


def build(source: dict, report: bool = False) -> dict:
    params = source["materialization"]
    rng = random.Random(params["seed"])
    total_runs = params["runs_per_prompt"]
    has_cites_p = params["has_citations_probability"]
    competitor_pool = params["competitor_brand_pool"]

    prompts = source["prompts"]
    engines = source["engines"]
    regions = source["regions"]
    pages = source["pages"]

    runs_per_engine = engine_run_counts(engines, total_runs)

    mean_mention = sum(p["mention_rate"] for p in prompts) / len(prompts) / 100.0
    mean_citation = sum(p["citation_rate"] for p in prompts) / len(prompts) / 100.0
    # Engine multipliers are normalized on the run-weighted mean, not the plain mean, so
    # that unequal sampling doesn't shift the overall level away from the prompt table.
    mean_engine_mention = sum(
        e["mention_rate"] * runs_per_engine[e["name"]] for e in engines
    ) / total_runs / 100.0
    mean_engine_citation = sum(
        e["citation_rate"] * runs_per_engine[e["name"]] for e in engines
    ) / total_runs / 100.0

    region_codes = [r["code"] for r in regions]
    region_weights = [r["weight"] for r in regions]

    # Brand citations are attributed to a real page so page-level citation counts
    # and their period-over-period change come out of the fact table rather than
    # being asserted. Candidate pages are restricted to those the prototype says
    # the engine actually cites.
    # Page attribution happens after the fact table is built — see assign_cited_urls.

    answers: list[dict] = []
    answer_seq = 0

    for period in ("current", "prior"):
        month, day_lo, day_hi = PERIOD_DAYS[period]
        for prompt in prompts:
            # The prior period is reconstructed by backing the stated trend out of
            # the current rate, which is what makes the computed trends real.
            if period == "current":
                p_mention = prompt["mention_rate"] / 100.0
                p_citation = prompt["citation_rate"] / 100.0
            else:
                p_mention = clamp((prompt["mention_rate"] - prompt["mention_trend"]) / 100.0)
                p_citation = clamp((prompt["citation_rate"] - prompt["citation_trend"]) / 100.0)

            positive_rate = prompt["positive_rate"] / 100.0
            neutral_rate = (1.0 - positive_rate) * NEUTRAL_SHARE_OF_REMAINDER

            for engine in engines:
                runs = runs_per_engine[engine["name"]]
                e_mention = engine["mention_rate"] / 100.0
                e_citation = engine["citation_rate"] / 100.0
                cell_mention = clamp(p_mention * e_mention / mean_engine_mention)
                cell_citation = clamp(p_citation * e_citation / mean_engine_citation)

                mention_flags = quota_flags(rng, runs, cell_mention)
                cites_flags = quota_flags(rng, runs, has_cites_p)
                # A brand citation requires the answer to cite anything at all, so the
                # citation quota is drawn over the runs that have citations, not over
                # all runs — otherwise the recovered citation rate is biased low.
                cite_indices = [i for i, f in enumerate(cites_flags) if f]
                brand_quota = int(round(len(cite_indices) * cell_citation))
                brand_indices = set(rng.sample(cite_indices, min(brand_quota, len(cite_indices))))

                for run_index in range(runs):
                    answer_seq += 1
                    mentioned = mention_flags[run_index]
                    has_citations = cites_flags[run_index]

                    if mentioned:
                        roll = rng.random()
                        sentiment = (
                            "Positive" if roll < positive_rate
                            else "Neutral" if roll < positive_rate + neutral_rate
                            else "Negative"
                        )
                        position = sample_position(rng, engine["avg_position"])
                    else:
                        sentiment = None
                        position = None

                    brand_cited = run_index in brand_indices
                    cited_url = None
                    # cited_url is filled in by assign_cited_urls() once all answers
                    # exist, so page totals can be allocated by exact quota instead of
                    # independent draws.
                    cited_url = None

                    # Competitors appear more often when the brand does not — that
                    # asymmetry is what the share-of-voice and content-gap rules read.
                    # Some answers name nobody tracked at all, which is what keeps
                    # "contested" a meaningful subset rather than every single answer.
                    n_competitors = (
                        rng.choice([0, 0, 1, 1, 2]) if mentioned
                        else rng.choice([0, 1, 1, 2, 2, 3])
                    )
                    competitors = rng.sample(competitor_pool, n_competitors) if n_competitors else []

                    answers.append({
                        "answer_id": f"ans_{answer_seq}",
                        "prompt_id": prompt["prompt_id"],
                        "engine": engine["name"],
                        "period": period,
                        "date": f"{month}-{rng.randint(day_lo, day_hi):02d}",
                        "region": weighted_choice(rng, region_codes, region_weights),
                        "mentioned": mentioned,
                        "position": position,
                        "sentiment": sentiment,
                        "has_citations": has_citations,
                        "brand_cited": brand_cited,
                        "cited_url": cited_url,
                        "competitor_brands": competitors,
                    })

    for period in ("current", "prior"):
        assign_cited_urls(rng, answers, pages, period)

    dataset = {
        "meta": {
            "generated_by": "tools/materialize.py",
            "source": "data/source_tables.json",
            "seed": params["seed"],
            "answer_count": len(answers),
            "periods": ["prior", "current"],
            "note": (
                "answers[] is the authoritative fact table: metrics.py computes all six "
                "KPIs from it. Aggregate tables carried over from the prototype are kept "
                "alongside as `reference` for reconciliation, not used as metric inputs."
            ),
        },
        "brand": source["brand"],
        "topics": source["topics"],
        "engines": engines,
        "regions": regions,
        "prompts": prompts,
        "pricing_prompt_ids": source["pricing_prompt_ids"],
        "answers": answers,
        "pages": pages,
        "search_console": source["search_console"],
        "backlinks": source["backlinks"],
        "brand_guidelines": source["brand_guidelines"],
        "reference": {
            "_note": "Prototype literals, retained for reconciliation only.",
            "brand_metrics": source["brand_metrics"],
            "sample_answers": source["sample_answers"],
        },
    }

    if report:
        _print_residuals(dataset, mean_mention, mean_citation)

    return dataset


def _print_residuals(dataset: dict, mean_mention: float, mean_citation: float) -> None:
    """Print how far the recovered marginals land from the stated ones."""
    current = [a for a in dataset["answers"] if a["period"] == "current"]
    engines = dataset["engines"]
    mean_engine = sum(e["mention_rate"] for e in engines) / len(engines)
    # The prompt table sets the level; engine targets are the stated rates scaled to it.
    level_factor = (mean_mention * 100.0) / mean_engine

    print(f"\nOverall level: prompt table says {mean_mention * 100:.1f}%, engine table "
          f"says {mean_engine:.1f}% — inconsistent by construction.")
    print(f"Prompt table treated as authoritative; engine targets scaled by "
          f"{level_factor:.3f}.")

    print("\nPer-engine mention rate (stated / level-adjusted -> recovered):")
    for engine in engines:
        rows = [a for a in current if a["engine"] == engine["name"]]
        got = 100.0 * sum(1 for a in rows if a["mentioned"]) / len(rows)
        target = engine["mention_rate"] * level_factor
        print(f"  {engine['name']:22} {engine['mention_rate']:5.1f} / {target:5.1f}"
              f" -> {got:5.1f}  ({got - target:+.1f} vs adjusted)")

    for label, stated_key, predicate in (
        ("mention rate", "mention_rate", lambda a: a["mentioned"]),
        ("citation rate", "citation_rate", lambda a: a["brand_cited"]),
    ):
        residuals = []
        for prompt in dataset["prompts"]:
            rows = [a for a in current if a["prompt_id"] == prompt["prompt_id"]]
            if label == "citation rate":
                rows = [a for a in rows if a["has_citations"]]
            if not rows:
                continue
            got = 100.0 * sum(1 for a in rows if predicate(a)) / len(rows)
            residuals.append((abs(got - prompt[stated_key]), prompt["prompt_id"],
                              prompt[stated_key], got))
        residuals.sort(reverse=True)
        print(f"\nPer-prompt {label}, 3 worst (stated -> recovered):")
        for _, pid, stated, got in residuals[:3]:
            print(f"  {pid:6} {stated:5.1f} -> {got:5.1f}  ({got - stated:+.1f})")
        mean_abs = sum(r[0] for r in residuals) / len(residuals)
        print(f"  mean absolute residual across 20 prompts: {mean_abs:.2f} pts")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true",
                       help="print marginal-fit residuals after building")
    parser.add_argument("--out", type=Path, default=TARGET)
    args = parser.parse_args()

    source = json.loads(SOURCE.read_text())
    dataset = build(source, report=args.report)
    args.out.write_text(json.dumps(dataset, indent=1) + "\n")
    size_kb = args.out.stat().st_size / 1024
    print(f"\nwrote {args.out.relative_to(ROOT)} "
          f"({dataset['meta']['answer_count']} answers, {size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
