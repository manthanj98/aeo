"""The deterministic layer, exposed to the agent as tools.

The agent gets no direct access to the dataset — only these functions. That is
deliberate: it cannot compute its own version of a KPI, so any number it writes either
came from a tool call or it made it up, and the latter is checkable by diffing the
report against `insights.json`.

Tools are read-only. Nothing here writes to disk; the CLI owns output.
"""

from __future__ import annotations

import json
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from .dataset import Dataset
from .insights import Insight
from .metrics import Metrics, page_citation_stats

# Set by build_server() before the agent runs. Module-level because the @tool decorator
# registers plain functions, which have no place to carry per-run state.
_STATE: dict[str, Any] = {}


def _ok(payload: Any) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=1)}]}


def _err(message: str) -> dict:
    return {"content": [{"type": "text", "text": f"error: {message}"}], "is_error": True}


def _dataset() -> Dataset:
    return _STATE["dataset"]


def _metrics() -> Metrics:
    return _STATE["metrics"]


def _insights() -> list[Insight]:
    return _STATE["insights"]


@tool("get_brand_context", "Brand, domain, period, tracked topics, and the writing "
                           "guidelines every draft must follow.", {})
async def get_brand_context(args: dict) -> dict:
    dataset = _dataset()
    return _ok({
        "brand": dataset.brand_name,
        "domain": dataset.brand_domain,
        "period": dataset.period_label,
        "prior_period": dataset.prior_period_label,
        "topics": [t["name"] for t in dataset.topics],
        "tracked_competitors": dataset.competitor_names,
        "engines": dataset.engine_names,
        "writing_guidelines": dataset.brand_guidelines,
        "answers_analysed": _metrics().answer_counts,
    })


@tool("get_kpis", "The six headline KPIs with values, period-over-period trends, and "
                  "the definition of each.", {})
async def get_kpis(args: dict) -> dict:
    return _ok([k.to_dict() for k in _metrics().kpis])


@tool("get_engine_breakdown", "Per-engine metrics: answers sampled, citation share, "
                              "citation count, mention rate, citation rate, average "
                              "position, sentiment.", {})
async def get_engine_breakdown(args: dict) -> dict:
    return _ok(_metrics().engine_rows)


@tool("get_competitor_leaderboard", "The brand ranked against tracked competitors on "
                                    "each metric. The brand's own figures are computed; "
                                    "competitor figures are carried over from source "
                                    "tables.", {})
async def get_competitor_leaderboard(args: dict) -> dict:
    return _ok(_metrics().leaderboards)


@tool("get_topic_breakdown", "Per-topic rollup: prompt count, monthly search volume, "
                             "mention rate, citation rate and its trend, share of "
                             "voice, sentiment.", {})
async def get_topic_breakdown(args: dict) -> dict:
    return _ok(_metrics().topic_rows)


@tool("list_insights", "All detected findings, ranked most severe first. Returns "
                       "identifiers, titles, severity, score, rule, and action — call "
                       "get_insight for the full evidence behind one.",
      {"severity": str, "action": str, "limit": int})
async def list_insights(args: dict) -> dict:
    rows = _insights()
    severity = (args.get("severity") or "").strip().title()
    if severity in {"High", "Medium", "Low"}:
        rows = [i for i in rows if i.severity == severity]
    action = (args.get("action") or "").strip().lower()
    if action in {"update", "draft"}:
        rows = [i for i in rows if i.action == action]
    limit = args.get("limit") or 0
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]
    return _ok([
        {"id": i.id, "title": i.title, "severity": i.severity, "score": i.score,
         "rule": i.rule, "action": i.action, "target_url": i.target_url,
         "stat_value": i.stat_value, "stat_delta": i.stat_delta,
         "metrics_at_risk": i.metrics_at_risk}
        for i in rows
    ])


@tool("get_insight", "Everything behind one finding: the evidence rows that triggered "
                     "it, its computed contributors, its severity arithmetic, and the "
                     "detected root cause.",
      {"insight_id": str})
async def get_insight(args: dict) -> dict:
    insight_id = args.get("insight_id")
    for insight in _insights():
        if insight.id == insight_id:
            return _ok(insight.to_dict())
    return _err(f"no insight with id {insight_id!r}; "
                f"known ids: {[i.id for i in _insights()]}")


@tool("get_cited_pages", "Tracked pages with citation counts, period-over-period "
                         "change, average citation position, and their Search Console "
                         "impressions, clicks, CTR, and position.",
      {"limit": int})
async def get_cited_pages(args: dict) -> dict:
    rows = page_citation_stats(_dataset())
    limit = args.get("limit") or 0
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]
    return _ok(rows)


@tool("get_prompts", "Tracked prompts with search volume, topic, mention rate and "
                     "citation rate, plus the computed rates from the answer set.",
      {"topic": str, "limit": int})
async def get_prompts(args: dict) -> dict:
    from .metrics import citation_rate, mention_rate

    dataset = _dataset()
    topic_filter = (args.get("topic") or "").strip().lower()
    rows = []
    for prompt in dataset.prompts:
        topic_name = dataset.topic_name(prompt["topic_id"])
        if topic_filter and topic_filter not in topic_name.lower():
            continue
        answers = dataset.answers("current", prompt_id=prompt["prompt_id"])
        rows.append({
            "prompt_id": prompt["prompt_id"],
            "prompt": prompt["text"],
            "topic": topic_name,
            "prompt_type": prompt["prompt_type"],
            "volume": prompt["volume"],
            "answers": len(answers),
            "mention_rate": mention_rate(answers),
            "citation_rate": citation_rate(answers),
            "competitor_only_answers": sum(
                1 for a in answers if not a["mentioned"] and a["competitor_brands"]),
        })
    rows.sort(key=lambda r: r["volume"], reverse=True)
    limit = args.get("limit") or 0
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]
    return _ok(rows)


@tool("get_answer_examples", "Individual AI answers, for grounding a claim in what "
                             "engines actually returned. Filter by prompt, engine, or "
                             "whether the brand was mentioned or cited.",
      {"prompt_id": str, "engine": str, "mentioned": bool, "brand_cited": bool,
       "limit": int})
async def get_answer_examples(args: dict) -> dict:
    dataset = _dataset()
    rows = dataset.answers(
        "current",
        engine=(args.get("engine") or None),
        prompt_id=(args.get("prompt_id") or None),
    )
    if isinstance(args.get("mentioned"), bool):
        rows = [a for a in rows if a["mentioned"] is args["mentioned"]]
    if isinstance(args.get("brand_cited"), bool):
        rows = [a for a in rows if a["brand_cited"] is args["brand_cited"]]

    limit = args.get("limit") or 12
    rows = rows[: max(1, min(int(limit), 40))]
    return _ok([
        {"answer_id": a["answer_id"], "prompt": dataset.prompt_text(a["prompt_id"]),
         "engine": a["engine"], "region": dataset.region_name(a["region"]),
         "date": a["date"], "mentioned": a["mentioned"], "position": a["position"],
         "sentiment": a["sentiment"], "brand_cited": a["brand_cited"],
         "cited_url": a["cited_url"], "competitor_brands": a["competitor_brands"]}
        for a in rows
    ])


TOOLS = (
    get_brand_context,
    get_kpis,
    get_engine_breakdown,
    get_competitor_leaderboard,
    get_topic_breakdown,
    list_insights,
    get_insight,
    get_cited_pages,
    get_prompts,
    get_answer_examples,
)

SERVER_NAME = "aeo"

# Fully-qualified names for ClaudeAgentOptions.allowed_tools. The SDK namespaces
# in-process MCP tools as mcp__<server>__<tool>.
ALLOWED_TOOL_NAMES = tuple(
    f"mcp__{SERVER_NAME}__{t.name}" for t in TOOLS
)


def build_server(dataset: Dataset, metrics: Metrics, insights: list[Insight]):
    """Bind this run's computed data and return the in-process MCP server."""
    _STATE["dataset"] = dataset
    _STATE["metrics"] = metrics
    _STATE["insights"] = insights
    return create_sdk_mcp_server(name=SERVER_NAME, version="1.0.0", tools=list(TOOLS))
