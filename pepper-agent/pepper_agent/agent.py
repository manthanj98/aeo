"""The agent loop.

Detection has already established what is true. The agent's job is the part that needs
judgment: explaining why each finding matters commercially, and writing the content
that responds to it. It reaches the data only through the tools in `tools.py`, and the
system prompt forbids asserting a number it did not retrieve — which is checkable
afterward by diffing the report against `insights.json`.

Two passes:

1. **Report pass** — one session, reading KPIs, engine and competitor breakdowns, and
   the ranked findings, producing an executive summary plus an impact and
   recommendation for each selected finding.
2. **Draft pass** — one query per finding, producing either an article draft or a
   page-update brief depending on the finding's `action`.

If the SDK cannot start — no CLI, no credentials, a transport failure — this raises
`AgentUnavailable` and the CLI falls back to `fallback.py`. A report always gets
written.
"""

from __future__ import annotations

import json
import re

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ClaudeSDKError,
    PermissionResultAllow,
    PermissionResultDeny,
    TextBlock,
)

from .dataset import Dataset
from .insights import Insight
from .metrics import Metrics
from .narrative import Draft, DraftChange, DraftSection, InsightNote, Narrative
from .tools import ALLOWED_TOOL_NAMES, SERVER_NAME, build_server

DEFAULT_MODEL = "claude-opus-5"

SYSTEM_PROMPT = """\
You are an AEO (Answer Engine Optimization) analyst. You write the analysis layer of an
AI-visibility report for a brand tracked across ChatGPT, Perplexity, Google AI
Overviews, Microsoft Co-Pilot, and Claude.

The findings have already been detected by deterministic rules and their severity
already scored. You are not deciding what is true — you are explaining what it means
commercially and writing the content that responds to it.

Hard rules:

1. Every number you state must come from a tool call in this session. Do not estimate,
   round differently, extrapolate, or infer a figure you did not retrieve. If you want
   a number you do not have, call a tool for it.
2. Follow the brand writing guidelines returned by get_brand_context exactly.
3. Reply with a single JSON object and nothing else — no prose before or after, no
   markdown fence. The caller parses your reply directly.
4. Write for a marketing lead who has to choose what to work on this week. Be concrete
   about the mechanism and the trade-off. No filler, no restating the headline, no
   "in today's fast-moving landscape".
5. Impact means the commercial consequence of acting or not acting, and which tracked
   metric moves. Recommendation means the specific next action, not a category of work.
"""

REPORT_TASK = """\
Write the analysis layer for this period's report.

Steps:
1. Call get_brand_context, get_kpis, get_engine_breakdown, get_competitor_leaderboard,
   and get_topic_breakdown.
2. Call list_insights to see the ranked findings.
3. Call get_insight for each of these findings, which are the ones being reported on:
   {insight_ids}
   Use get_cited_pages, get_prompts, or get_answer_examples where a finding needs more
   grounding.

Then reply with exactly this JSON shape:

{{
  "executive_summary": "3-5 sentences. Lead with where visibility stands and the "
                       "direction of travel, name the single most consequential "
                       "finding and why, and close with what the queue looks like. "
                       "Cite specific figures you retrieved.",
  "notes": [
    {{
      "insight_id": "ins_01",
      "impact": "2-3 sentences on the commercial consequence and which tracked metric "
                "is at stake.",
      "recommendation": "1-2 sentences naming the specific next action."
    }}
  ]
}}

Include one note object for every finding id listed above, in the same order.
"""

DRAFT_ARTICLE_TASK = """\
Finding {insight_id} calls for new content. Call get_insight for it, plus whatever else
you need to ground the piece, then draft it.

Reply with exactly this JSON shape:

{{
  "title": "The working title of the piece",
  "rationale": "1-2 sentences on why this piece, tied to the finding's evidence.",
  "sections": [
    {{"heading": "Section heading", "body": "2-4 sentences of actual draft copy — "
                                            "write the content, not a description of "
                                            "what the content would say."}}
  ],
  "success_metric": "The specific number that would show this worked."
}}

Three to five sections. The first must answer the target question directly enough that
an AI engine could quote it verbatim.
"""

DRAFT_UPDATE_TASK = """\
Finding {insight_id} points at an existing page: {target_url}

Call get_insight for it, plus whatever else you need, then write a change brief for
that page — not a new article.

Reply with exactly this JSON shape:

{{
  "title": "Update brief: <the page path>",
  "rationale": "1-2 sentences on why this page needs work, from the evidence.",
  "changes": [
    {{"label": "Updated section", "detail": "What to change and how, specifically."}},
    {{"label": "Added", "detail": "What to add and where."}},
    {{"label": "Why", "detail": "The mechanism — why this change addresses the finding."}}
  ],
  "success_metric": "The specific number that would show this worked."
}}

Three to five changes. Each `detail` must be actionable by someone who has the page
open — name the section, the element, or the copy.
"""


class AgentUnavailable(RuntimeError):
    """The agent could not run; the caller should fall back to templates."""


def _extract_text(message) -> str:
    if not isinstance(message, AssistantMessage):
        return ""
    return "".join(
        block.text for block in message.content if isinstance(block, TextBlock)
    )


def _parse_json_reply(text: str, context: str) -> dict:
    """Pull the JSON object out of a reply.

    The system prompt asks for bare JSON, but models sometimes fence it or add a
    sentence. Try the whole string, then a fenced block, then the outermost braces,
    before giving up.
    """
    candidates = [text.strip()]

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1).strip())

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed

    raise AgentUnavailable(
        f"could not parse the agent's {context} reply as JSON "
        f"(first 200 chars: {text.strip()[:200]!r})"
    )


async def _permit_aeo_tools_only(tool_name: str, tool_input: dict, context):
    """Allow the read-only AEO tools; refuse anything else.

    There is no interactive approver in this process, so an unlisted tool would
    otherwise stall the session. Denying explicitly lets the model recover by calling
    something it is allowed to use.
    """
    if tool_name in ALLOWED_TOOL_NAMES:
        return PermissionResultAllow()
    return PermissionResultDeny(
        message=f"{tool_name} is not available to this agent; use the AEO tools "
                f"({', '.join(n.split('__')[-1] for n in ALLOWED_TOOL_NAMES)})."
    )


async def _ask(client: ClaudeSDKClient, prompt: str, context: str) -> dict:
    await client.query(prompt)
    chunks: list[str] = []
    async for message in client.receive_response():
        chunks.append(_extract_text(message))
    return _parse_json_reply("".join(chunks), context)


async def run(dataset: Dataset, metrics: Metrics, insights: list[Insight],
              draft_for: list[Insight], *, model: str = DEFAULT_MODEL,
              max_turns: int = 40, verbose: bool = False) -> Narrative:
    """Produce a `Narrative` via the Claude Agent SDK.

    Raises `AgentUnavailable` if the session cannot run or a reply cannot be parsed.
    """
    server = build_server(dataset, metrics, insights)
    options = ClaudeAgentOptions(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={SERVER_NAME: server},
        # The AEO tools are read-only and in-process, so listing them in allowed_tools
        # is enough — no permission bypass is needed. That matters: bypassPermissions
        # maps to --dangerously-skip-permissions, which the CLI refuses to run as root,
        # and containers commonly run as root.
        allowed_tools=list(ALLOWED_TOOL_NAMES),
        disallowed_tools=["Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch"],
        can_use_tool=_permit_aeo_tools_only,
        max_turns=max_turns,
    )

    reported = draft_for or insights
    warnings: list[str] = []

    try:
        async with ClaudeSDKClient(options=options) as client:
            if verbose:
                print(f"  agent: report pass over {len(reported)} findings…")
            report = await _ask(
                client,
                REPORT_TASK.format(
                    insight_ids=", ".join(i.id for i in reported)),
                "report",
            )

            notes: dict[str, InsightNote] = {}
            for entry in report.get("notes", []):
                insight_id = entry.get("insight_id")
                if not insight_id:
                    continue
                notes[insight_id] = InsightNote(
                    insight_id=insight_id,
                    impact=str(entry.get("impact", "")).strip(),
                    recommendation=str(entry.get("recommendation", "")).strip(),
                )

            missing = [i.id for i in reported if i.id not in notes]
            if missing:
                warnings.append(
                    f"The agent returned no impact note for {', '.join(missing)}; "
                    f"template text was used for those."
                )

            drafts: list[Draft] = []
            for insight in draft_for:
                if verbose:
                    print(f"  agent: drafting for {insight.id} ({insight.action})…")
                is_update = insight.action == "update" and insight.target_url
                task = (
                    DRAFT_UPDATE_TASK.format(
                        insight_id=insight.id, target_url=insight.target_url)
                    if is_update else
                    DRAFT_ARTICLE_TASK.format(insight_id=insight.id)
                )
                payload = await _ask(client, task, f"draft for {insight.id}")
                drafts.append(Draft(
                    insight_id=insight.id,
                    kind="update_brief" if is_update else "article",
                    title=str(payload.get("title") or insight.title).strip(),
                    rationale=str(payload.get("rationale")
                                  or insight.root_cause).strip(),
                    target_url=insight.target_url if is_update else None,
                    sections=[
                        DraftSection(
                            heading=str(s.get("heading", "")).strip(),
                            body=str(s.get("body", "")).strip())
                        for s in payload.get("sections", [])
                        if isinstance(s, dict)
                    ],
                    changes=[
                        DraftChange(
                            label=str(c.get("label", "")).strip(),
                            detail=str(c.get("detail", "")).strip())
                        for c in payload.get("changes", [])
                        if isinstance(c, dict)
                    ],
                    success_metric=str(payload.get("success_metric", "")).strip(),
                ))

    except AgentUnavailable:
        raise
    except ClaudeSDKError as error:
        raise AgentUnavailable(f"{type(error).__name__}: {error}") from error
    except (OSError, RuntimeError) as error:
        raise AgentUnavailable(f"{type(error).__name__}: {error}") from error

    summary = str(report.get("executive_summary", "")).strip()
    if not summary:
        raise AgentUnavailable("the agent returned no executive summary")

    return Narrative(
        executive_summary=summary,
        notes=notes,
        drafts=drafts,
        source="agent",
        model=model,
        warnings=warnings,
    )
