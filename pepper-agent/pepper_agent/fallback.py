"""Deterministic narrative, for when no model is reachable.

`python -m pepper_agent run` has to produce a real report whether or not the Claude
Agent SDK can start — auth is environment-dependent, and a report that fails to render
because a subprocess could not launch is not a working agent. So the LLM upgrades the
prose; it does not gate it.

Everything here is built from the evidence each rule already attached to its insight,
which is why the templates can be specific rather than generic. `--offline` selects
this path explicitly; `run` falls back to it with a warning.
"""

from __future__ import annotations

from .dataset import Dataset
from .insights import Insight
from .metrics import Metrics
from .narrative import Draft, DraftChange, DraftSection, InsightNote, Narrative

# Per-rule impact framing: why this class of finding matters commercially. The
# evidence supplies the numbers; this supplies the argument.
IMPACT_TEMPLATES = {
    "citation_decline": (
        "Citation share on an established page compounds in both directions. Every "
        "period this page keeps sliding, the harder it is to reclaim from whoever "
        "took the slot, because engines reinforce sources they have already chosen. "
        "Acting here protects traffic the brand already earned rather than chasing new."
    ),
    "topic_citation_gap": (
        "A topic cited well below portfolio rate is demand the brand is present for "
        "but not credited on. Engines are answering these questions today and sourcing "
        "someone else, so the gap widens on its own as those sources accumulate "
        "authority."
    ),
    "rising_page": (
        "This page is compounding without help, which makes under-investment the main "
        "risk rather than decline. Extending something already working is the cheapest "
        "available gain in both citation rate and organic traffic."
    ),
    "high_impressions_low_ctr": (
        "Search demand is already landing here and bouncing before the click. Because "
        "the page is credible enough for engines to cite, a title and description fix "
        "converts existing impressions with no AI-visibility risk — the shortest path "
        "from work to traffic in this report."
    ),
    "seo_strong_low_citations": (
        "Organic equity that has not converted into AI citations caps this page's value "
        "as discovery shifts toward answer engines. Structured data and direct-answer "
        "formatting turn ranking the brand already holds into citations it does not."
    ),
    "competitor_prompt_gap": (
        "Competitors are establishing the answer on a high-volume question while the "
        "brand is absent. Share of voice lost on a prompt cluster is slow to win back, "
        "because engines keep returning to sources they have cited before."
    ),
    "sentiment_divergence": (
        "Rising mentions on softening sentiment means more people are seeing a weaker "
        "version of the story. Visibility gains that carry negative framing can erode "
        "brand perception faster than silence would."
    ),
    "engine_concentration": (
        "Concentration turns one provider's ranking change into a portfolio-wide event. "
        "Diversifying citation sources is what makes the visibility number durable "
        "rather than contingent on a single algorithm holding still."
    ),
    "underindexed_engine": (
        "An engine the brand barely appears on is demand it cannot capture at all. "
        "Expanding there both adds volume and reduces dependence on the engines "
        "currently carrying the portfolio."
    ),
    "stale_high_value": (
        "A proven page slipping slowly is not urgent this week and expensive to ignore "
        "for a quarter. Refreshing content engines already trust protects citation rate "
        "at a fraction of the cost of earning a new page's authority."
    ),
    "unlinked_mentions": (
        "Unlinked mentions on high-authority domains are citations already earned but "
        "not credited. Converting them takes outreach rather than content investment, "
        "which makes this the highest-return-per-hour item available."
    ),
    "community_gap": (
        "Engines cite community threads directly, so an active discussion the brand is "
        "absent from is a source shaping answers without the brand's input. "
        "Participating is cheap; the discussion continues either way."
    ),
}

# Per-rule next action, phrased as the thing to actually do.
RECOMMENDATION_TEMPLATES = {
    "citation_decline": (
        "Refresh {target} with current examples and a quotable summary paragraph, then "
        "re-check citation volume on {engines} next period."
    ),
    "topic_citation_gap": (
        "Publish a dedicated piece for the \"{topic}\" cluster built around direct "
        "answers to its highest-volume prompts, then track citation rate on that topic."
    ),
    "rising_page": (
        "Extend {target} with a new section on what is driving the gain, and add "
        "internal links from related pages to compound it."
    ),
    "high_impressions_low_ctr": (
        "Rewrite the title and meta description for {target} to lead with the specific "
        "number searchers want, and add a summary table near the top of the page."
    ),
    "seo_strong_low_citations": (
        "Add FAQ-style structured data and a direct-answer opening paragraph to "
        "{target}, formatted the way engines extract when choosing a source."
    ),
    "competitor_prompt_gap": (
        "Write a piece that answers \"{prompt}\" directly and comparatively, naming the "
        "trade-offs rather than only the brand's strengths."
    ),
    "sentiment_divergence": (
        "Refresh the messaging on \"{topic}\" content to address the caveats engines "
        "are surfacing, rather than adding more volume to the same framing."
    ),
    "engine_concentration": (
        "Publish for the sourcing patterns of the under-represented engines, and treat "
        "citation share by engine as a tracked metric rather than a by-product."
    ),
    "underindexed_engine": (
        "Produce one piece formatted for {engine}'s sourcing preferences — explicit "
        "reasoning, labelled data, direct comparisons — and measure its citation share "
        "next period."
    ),
    "stale_high_value": (
        "Refresh {target} with current figures and re-examine whether its claims still "
        "match what competitors now publish on the same question."
    ),
    "unlinked_mentions": (
        "Send a short outreach note to each domain asking for a link or source "
        "attribution on the existing mention, offering supporting data."
    ),
    "community_gap": (
        "Post once, substantively and without pitching, in the active threads — then "
        "stay in the conversation rather than treating it as a campaign."
    ),
}


def _target_label(insight: Insight) -> str:
    if insight.target_url:
        url = insight.target_url
        slash = url.find("/", url.find(".") if "." in url else 0)
        return url[slash:] if slash != -1 else url
    return "this page"


def _format(template: str, dataset: Dataset, insight: Insight) -> str:
    evidence = insight.evidence
    engines = evidence.get("engines") or []
    return template.format(
        target=_target_label(insight),
        topic=evidence.get("topic", "this topic"),
        prompt=evidence.get("prompt", "this prompt"),
        engine=evidence.get("engine", "that engine"),
        engines=", ".join(engines) if engines else "the engines involved",
        brand=dataset.brand_name,
    )


def build_notes(dataset: Dataset, insights: list[Insight]) -> dict[str, InsightNote]:
    notes = {}
    for insight in insights:
        impact = IMPACT_TEMPLATES.get(
            insight.rule,
            "This finding affects how often and how prominently the brand appears in "
            "AI answers.",
        )
        at_risk = ", ".join(insight.metrics_at_risk) or "Visibility"
        recommendation = _format(
            RECOMMENDATION_TEMPLATES.get(
                insight.rule, "Review the evidence and decide on a content response."),
            dataset, insight,
        )
        notes[insight.id] = InsightNote(
            insight_id=insight.id,
            impact=f"{impact} Metrics at risk: {at_risk}.",
            recommendation=recommendation,
        )
    return notes


def _update_brief(dataset: Dataset, insight: Insight) -> Draft:
    """A change list against an existing URL, mirroring the prototype's `changes[]`."""
    evidence = insight.evidence
    target = _target_label(insight)

    changes = [DraftChange("Why", insight.root_cause)]
    if insight.rule == "citation_decline":
        changes = [
            DraftChange("Updated section", (
                f"Refresh the body of {target} with current examples and rewrite the "
                f"opening into a single quotable paragraph that answers "
                f"\"{evidence.get('top_prompt', 'the target prompt')}\" outright.")),
            DraftChange("Added", (
                "A comparison callout distinguishing this page from the competitor "
                "coverage that displaced it, so engines have a reason to prefer it "
                "again.")),
            DraftChange("Why", insight.root_cause),
        ]
    elif insight.rule == "high_impressions_low_ctr":
        estimated = evidence.get("estimated_clicks_at_median")
        changes = [
            DraftChange("Updated section", (
                "Rewrite the title tag and meta description to lead with the specific "
                "benchmark figure the query is asking for, rather than the topic name.")),
            DraftChange("Added", (
                "A summary table directly below the introduction so both readers and "
                "engines can extract the headline number without scrolling.")),
            DraftChange("Expected effect", (
                f"Reaching the {evidence.get('ctr_median_pct'):.1f}% page-median CTR on "
                f"{evidence.get('impressions'):,} impressions would be roughly "
                f"{estimated:,} clicks against {evidence.get('clicks'):,} today."
                if estimated else "Closing the CTR gap to the page median.")),
            DraftChange("Why", insight.root_cause),
        ]
    elif insight.rule == "seo_strong_low_citations":
        changes = [
            DraftChange("Added", (
                "FAQ-style schema.org markup around the comparison content already on "
                "the page, so engines can parse question-answer pairs directly.")),
            DraftChange("Updated section", (
                "A direct-answer summary paragraph at the top, written to be quoted "
                "verbatim rather than paraphrased.")),
            DraftChange("Why", insight.root_cause),
        ]
    elif insight.rule == "rising_page":
        changes = [
            DraftChange("Updated section", (
                "Extend the analysis with the current period's figures so the page "
                "stays the most current answer as citations climb.")),
            DraftChange("Added", (
                "A section naming what is driving the gain, plus internal links from "
                "related pages to compound it.")),
            DraftChange("Why", insight.root_cause),
        ]
    elif insight.rule == "stale_high_value":
        changes = [
            DraftChange("Updated section", (
                f"Replace the figures throughout {target} — the content is "
                f"{evidence.get('months_since_update')} months old and its claims "
                f"predate the current competitive set.")),
            DraftChange("Added", (
                "An explicit last-reviewed date and a short changelog, both signals "
                "engines weigh when choosing between comparable sources.")),
            DraftChange("Why", insight.root_cause),
        ]

    return Draft(
        insight_id=insight.id, kind="update_brief",
        title=f"Update brief: {target}",
        rationale=insight.root_cause,
        target_url=insight.target_url,
        changes=changes,
        success_metric=(
            f"Citation volume on {target} recovering above "
            f"{evidence.get('citations_prior', evidence.get('citations', 0))} next period"
            if insight.rule == "citation_decline" else
            f"{', '.join(insight.metrics_at_risk)} improving next period"
        ),
    )


def _article(dataset: Dataset, insight: Insight) -> Draft:
    """A new-content draft for an insight with no specific existing URL to fix."""
    evidence = insight.evidence
    brand = dataset.brand_name

    if insight.rule == "competitor_prompt_gap":
        prompt = evidence.get("prompt", "the target question")
        rivals = ", ".join(c["brand"] for c in evidence.get("top_competitors", [])) or "competitors"
        title = prompt.rstrip("?.").strip()
        sections = [
            DraftSection("Answer the question in the first paragraph", (
                f"Open by answering \"{prompt}\" directly and completely, in two or "
                f"three sentences an engine can quote without editing. This prompt "
                f"draws {evidence.get('volume', 0):,} searches a month and engines "
                f"currently name {rivals} instead of {brand}.")),
            DraftSection("Show the comparison honestly", (
                f"Compare the realistic options side by side, including where {rivals} "
                f"are the better fit. Engines cite sources that read as assessments "
                f"rather than pitches, and a comparison that never concedes anything "
                f"reads as the latter.")),
            DraftSection("Give the decision criteria", (
                "Set out the two or three factors that actually decide the choice, so "
                "a reader arriving from an AI answer can place themselves. This is the "
                "section that earns the citation on follow-up prompts.")),
            DraftSection("Close with the specific case for the brand", (
                f"State plainly which situations {brand} is the right answer for, "
                f"grounded in the criteria just given rather than asserted.")),
        ]
    elif insight.rule == "topic_citation_gap":
        topic = evidence.get("topic", "this topic")
        title = f"{topic}: what the answer engines are getting wrong"
        examples = evidence.get("example_prompts", [])
        sections = [
            DraftSection("Lead with the direct answer", (
                f"The brand is cited {evidence.get('citation_rate')}% of the time in "
                f"this topic against {evidence.get('portfolio_citation_rate')}% "
                f"portfolio-wide. Open with a quotable summary that answers the "
                f"cluster's central question outright.")),
            DraftSection("Cover the cluster's actual prompts", (
                "Structure the body around the questions engines are already fielding: "
                + "; ".join(f"\"{p}\"" for p in examples[:3]) +
                ". One clearly-headed section each, each independently quotable.")),
            DraftSection("Add the structure engines extract", (
                "A labelled comparison table and FAQ markup, so the piece can be parsed "
                "into an answer rather than summarized loosely.")),
        ]
    elif insight.rule == "underindexed_engine":
        engine = evidence.get("engine", "the under-indexed engine")
        title = f"How {engine} chooses what to cite, and what that changes"
        sections = [
            DraftSection("The observation", (
                f"{engine} carries {evidence.get('citation_share_pct')}% of the brand's "
                f"citations at a {evidence.get('citation_rate')}% citation rate, against "
                f"{evidence.get('strongest_citation_rate')}% on "
                f"{evidence.get('strongest_engine')}. The same content is not landing "
                f"the same way.")),
            DraftSection("What this engine appears to weigh", (
                "Explicit reasoning, labelled data, and direct comparisons over "
                "promotional phrasing. Work through what that means concretely for a "
                "page's structure rather than stating it as a principle.")),
            DraftSection("The changes worth making", (
                "Name the specific formatting and sourcing changes to test, and the "
                "citation-share number that would show they worked.")),
        ]
    elif insight.rule == "engine_concentration":
        top = evidence.get("top_engine", "one engine")
        title = "What each AI engine actually cites, and why concentration is a risk"
        shares = evidence.get("engine_shares", [])
        sections = [
            DraftSection("The concentration", (
                f"{evidence.get('top_engine_share_pct')}% of the brand's citations come "
                f"from {top}, against {evidence.get('even_share_pct')}% for an even "
                f"spread. Current distribution: " +
                "; ".join(f"{s['engine']} {s['share_pct']}%" for s in shares) + ".")),
            DraftSection("Why engines differ in what they cite", (
                "Work through what each major engine tends to prioritize when selecting "
                "sources — recency, structure, explicit comparison, community "
                "corroboration — with examples.")),
            DraftSection("What a balanced content strategy looks like", (
                "Set out how to publish for several engines' preferences at once "
                "without producing five versions of the same page.")),
        ]
    elif insight.rule == "unlinked_mentions":
        domains = evidence.get("domains", [])
        title = "Outreach: source attribution on existing mentions"
        listed = ", ".join(d["domain"] for d in domains)
        sections = [
            DraftSection("Subject line", "Quick source note on your recent piece"),
            DraftSection("Body", (
                f"Hi — we noticed your piece mentions {brand} by name, and we "
                f"appreciate it. Would you be open to linking the mention, or "
                f"attributing the specific figure referenced? Happy to send the "
                f"underlying data, a quote, or any additional context that would be "
                f"useful. Whatever is easiest on your end.")),
            DraftSection("Send to", (
                f"{listed} — {evidence.get('unlinked_mentions')} unlinked mentions at "
                f"average domain authority {evidence.get('avg_authority')}.")),
        ]
    elif insight.rule == "community_gap":
        title = "Community post: how AI visibility tracking actually differs from rank tracking"
        sections = [
            DraftSection("Framing", (
                "A substantive contribution, not a pitch. The threads are already "
                "discussing the category; the goal is to be useful in them.")),
            DraftSection("Body", (
                f"There have been a few threads here on tracking brand visibility in AI "
                f"answers, so here is what we have learned doing it — including what "
                f"does not work. Answer engines select sources on different signals "
                f"than ranking algorithms, which is why traditional rank tracking "
                f"misses most of it.")),
            DraftSection("Follow-through", (
                "Answer questions in-thread rather than posting once and leaving. "
                "Engines cite threads that show sustained discussion.")),
        ]
    elif insight.rule == "sentiment_divergence":
        topic = evidence.get("topic", "this topic")
        title = f"Messaging refresh: {topic}"
        sections = [
            DraftSection("What changed", (
                f"Mentions in this topic rose {evidence.get('mention_delta_pts')} points "
                f"while sentiment fell {abs(evidence.get('sentiment_delta', 0))}. More "
                f"visibility, worse framing.")),
            DraftSection("Address the caveats directly", (
                "Engines are surfacing qualifications rather than criticism. Name them "
                "and answer them in the content instead of publishing around them.")),
            DraftSection("What to measure", (
                "Sentiment on this topic recovering while mention rate holds.")),
        ]
    else:
        title = insight.title
        sections = [DraftSection("Draft", insight.root_cause)]

    return Draft(
        insight_id=insight.id, kind="article",
        title=title, rationale=insight.root_cause,
        sections=sections,
        success_metric=f"{', '.join(insight.metrics_at_risk)} improving next period",
    )


def build_draft(dataset: Dataset, insight: Insight) -> Draft:
    if insight.action == "update" and insight.target_url:
        return _update_brief(dataset, insight)
    return _article(dataset, insight)


def build_executive_summary(dataset: Dataset, metrics: Metrics,
                            insights: list[Insight]) -> str:
    visibility = metrics.kpi("visibility_score")
    citation = metrics.kpi("citation_rate")
    mention = metrics.kpi("mention_rate")
    sov = metrics.kpi("share_of_voice")

    highs = [i for i in insights if i.severity == "High"]
    counts = {"High": 0, "Medium": 0, "Low": 0}
    for insight in insights:
        counts[insight.severity] += 1

    board = next((b for b in metrics.leaderboards if b["key"] == "citation_rate"), None)
    rank_note = ""
    if board:
        leader = next(r for r in board["rows"] if r["rank"] == 1)
        if not leader["is_you"]:
            rank_note = (
                f" On citation rate the brand ranks {board['brand_rank']} of "
                f"{board['field_size']} against tracked competitors, behind "
                f"{leader['name']} at {leader['display']}."
            )

    lead = (
        f"Across {metrics.answer_counts['current']:,} AI answers in "
        f"{dataset.period_label}, {dataset.brand_name} holds a visibility score of "
        f"{visibility.display} ({visibility.trend_display} versus "
        f"{dataset.prior_period_label}), appearing in {mention.display} of answers with "
        f"{sov.display} share of voice and a {citation.display} citation rate."
        f"{rank_note}"
    )

    if highs:
        headline = highs[0]
        plural = counts["High"] != 1
        body = (
            f" {counts['High']} finding{'s' if plural else ''} "
            f"rate{'' if plural else 's'} High severity, led by: {headline.title}. "
            f"{headline.root_cause}"
        )
    else:
        body = (
            f" No finding reaches High severity this period; the "
            f"{counts['Medium']} Medium-severity items are the substantive queue."
        )

    tail = (
        f" Detection surfaced {len(insights)} findings in total "
        f"({counts['High']} High, {counts['Medium']} Medium, {counts['Low']} Low), of "
        f"which {sum(1 for i in insights if i.action == 'update')} point at an existing "
        f"page and {sum(1 for i in insights if i.action == 'draft')} call for new content."
    )

    return lead + body + tail


def build(dataset: Dataset, metrics: Metrics, insights: list[Insight],
          draft_for: list[Insight], warnings: list[str] | None = None) -> Narrative:
    return Narrative(
        executive_summary=build_executive_summary(dataset, metrics, insights),
        notes=build_notes(dataset, insights),
        drafts=[build_draft(dataset, i) for i in draft_for],
        source="template",
        model=None,
        warnings=list(warnings or []),
    )
