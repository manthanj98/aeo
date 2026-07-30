"""Narrative containers — the prose layer that sits on top of the computed layer.

`metrics.py` and `insights.py` establish what is true. This module holds what gets
*said* about it: the executive summary, the per-insight impact and recommendation, and
the content drafts. Two producers fill these in — `agent.py` via the Claude Agent SDK,
and `fallback.py` from deterministic templates — and the renderers consume them without
caring which one ran.

Keeping the shapes here is what makes the LLM optional rather than load-bearing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class InsightNote:
    """What the narrative layer adds to a detected insight."""

    insight_id: str
    impact: str
    recommendation: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DraftChange:
    """One line of a page-update brief."""

    label: str          # 'Updated section' | 'Added' | 'Why'
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DraftSection:
    heading: str
    body: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Draft:
    """A content deliverable produced for one insight.

    `kind` mirrors the prototype's `articleAction`: an insight implicating a specific
    existing URL yields an `update_brief`, one implying missing content yields an
    `article`.
    """

    insight_id: str
    kind: str                        # 'article' | 'update_brief'
    title: str
    rationale: str
    target_url: str | None = None
    sections: list[DraftSection] = field(default_factory=list)
    changes: list[DraftChange] = field(default_factory=list)
    success_metric: str = ""

    @property
    def is_update(self) -> bool:
        return self.kind == "update_brief"

    @property
    def slug(self) -> str:
        cleaned = "".join(
            char.lower() if char.isalnum() else "-" for char in self.title
        )
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned.strip("-")[:60]

    def to_dict(self) -> dict:
        return {
            "insight_id": self.insight_id,
            "kind": self.kind,
            "title": self.title,
            "rationale": self.rationale,
            "target_url": self.target_url,
            "sections": [s.to_dict() for s in self.sections],
            "changes": [c.to_dict() for c in self.changes],
            "success_metric": self.success_metric,
        }


@dataclass
class Narrative:
    """Everything the prose layer contributes to one run."""

    executive_summary: str
    notes: dict[str, InsightNote] = field(default_factory=dict)
    drafts: list[Draft] = field(default_factory=list)
    source: str = "template"          # 'agent' | 'template'
    model: str | None = None
    warnings: list[str] = field(default_factory=list)

    def note_for(self, insight_id: str) -> InsightNote | None:
        return self.notes.get(insight_id)

    def draft_for(self, insight_id: str) -> Draft | None:
        for draft in self.drafts:
            if draft.insight_id == insight_id:
                return draft
        return None

    def to_dict(self) -> dict:
        return {
            "executive_summary": self.executive_summary,
            "notes": {k: v.to_dict() for k, v in self.notes.items()},
            "drafts": [d.to_dict() for d in self.drafts],
            "source": self.source,
            "model": self.model,
            "warnings": self.warnings,
        }
