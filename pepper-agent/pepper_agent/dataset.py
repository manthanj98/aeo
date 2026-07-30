"""Loading and access for the AI-visibility dataset.

Everything downstream reads the data through `Dataset`, never by opening the JSON
directly. Swapping the seed file for a live AEO API means reimplementing this class
alone — `metrics.py` and `insights.py` only ever see the accessors below.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "visibility.json"

REQUIRED_SECTIONS = (
    "brand", "topics", "engines", "prompts", "answers", "pages",
    "search_console", "backlinks", "brand_guidelines",
)


class DatasetError(RuntimeError):
    """Raised when the dataset is missing sections or internally inconsistent."""


@dataclass
class Dataset:
    """An AI-visibility dataset for one brand over two comparable periods."""

    raw: dict[str, Any]
    path: Path | None = None
    _pages_by_url: dict[str, dict] = field(default_factory=dict, repr=False)
    _sc_by_url: dict[str, dict] = field(default_factory=dict, repr=False)
    _prompts_by_id: dict[str, dict] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        missing = [s for s in REQUIRED_SECTIONS if s not in self.raw]
        if missing:
            raise DatasetError(f"dataset missing required sections: {', '.join(missing)}")
        if not self.raw["answers"]:
            raise DatasetError("dataset has no answers; nothing can be computed")

        self._pages_by_url = {p["url"]: p for p in self.raw["pages"]}
        self._sc_by_url = {r["url"]: r for r in self.raw["search_console"]}
        self._prompts_by_id = {p["prompt_id"]: p for p in self.raw["prompts"]}

        periods = {a["period"] for a in self.raw["answers"]}
        for required in ("current", "prior"):
            if required not in periods:
                raise DatasetError(
                    f"answers[] has no '{required}' period; trend metrics need both"
                )
        orphans = {a["prompt_id"] for a in self.raw["answers"]} - set(self._prompts_by_id)
        if orphans:
            raise DatasetError(f"answers reference unknown prompt ids: {sorted(orphans)}")

    # -- construction ----------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Dataset":
        resolved = Path(path) if path else DEFAULT_DATA_PATH
        if not resolved.exists():
            raise DatasetError(
                f"{resolved} not found — run `python tools/materialize.py` to build it"
            )
        return cls(raw=json.loads(resolved.read_text()), path=resolved)

    # -- brand and taxonomy ----------------------------------------------------

    @property
    def brand_name(self) -> str:
        return self.raw["brand"]["name"]

    @property
    def brand_domain(self) -> str:
        return self.raw["brand"]["domain"]

    @property
    def period_label(self) -> str:
        return self.raw["brand"].get("period_label", "current period")

    @property
    def prior_period_label(self) -> str:
        return self.raw["brand"].get("prior_period_label", "prior period")

    @property
    def engines(self) -> list[dict]:
        return self.raw["engines"]

    @property
    def engine_names(self) -> list[str]:
        return [e["name"] for e in self.raw["engines"]]

    @property
    def topics(self) -> list[dict]:
        return self.raw["topics"]

    @property
    def brand_guidelines(self) -> list[str]:
        return self.raw["brand_guidelines"]

    @property
    def competitor_names(self) -> list[str]:
        return [b["name"] for b in self.raw["reference"]["brand_metrics"] if not b["is_you"]]

    def topic_name(self, topic_id: str) -> str:
        for topic in self.raw["topics"]:
            if topic["id"] == topic_id:
                return topic["name"]
        return "Uncategorized"

    def region_name(self, code: str) -> str:
        for region in self.raw.get("regions", []):
            if region["code"] == code:
                return region["name"]
        return code.upper()

    # -- answers ---------------------------------------------------------------

    def answers(self, period: str = "current", *, engine: str | None = None,
                prompt_id: str | None = None, region: str | None = None) -> list[dict]:
        rows = [a for a in self.raw["answers"] if a["period"] == period]
        if engine:
            rows = [a for a in rows if a["engine"] == engine]
        if prompt_id:
            rows = [a for a in rows if a["prompt_id"] == prompt_id]
        if region:
            rows = [a for a in rows if a["region"] == region]
        return rows

    def answers_for_topic(self, topic_id: str, period: str = "current") -> list[dict]:
        ids = {p["prompt_id"] for p in self.raw["prompts"] if p["topic_id"] == topic_id}
        return [a for a in self.answers(period) if a["prompt_id"] in ids]

    def answers_for_prompts(self, prompt_ids: Iterable[str],
                            period: str = "current") -> list[dict]:
        wanted = set(prompt_ids)
        return [a for a in self.answers(period) if a["prompt_id"] in wanted]

    # -- prompts, pages, search console, backlinks ------------------------------

    @property
    def prompts(self) -> list[dict]:
        return self.raw["prompts"]

    def prompt(self, prompt_id: str) -> dict | None:
        return self._prompts_by_id.get(prompt_id)

    def prompt_text(self, prompt_id: str) -> str:
        prompt = self._prompts_by_id.get(prompt_id)
        return prompt["text"] if prompt else prompt_id

    @property
    def pricing_prompt_ids(self) -> list[str]:
        return self.raw.get("pricing_prompt_ids", [])

    @property
    def pages(self) -> list[dict]:
        return self.raw["pages"]

    def page(self, url: str) -> dict | None:
        return self._pages_by_url.get(url)

    @property
    def search_console(self) -> list[dict]:
        return self.raw["search_console"]

    def sc_row(self, url: str) -> dict | None:
        return self._sc_by_url.get(url)

    @property
    def backlinks(self) -> list[dict]:
        return self.raw["backlinks"]

    # -- reconciliation reference ----------------------------------------------

    @property
    def reference_brand_metrics(self) -> list[dict]:
        """The prototype's hardcoded competitor table.

        Used for the competitor leaderboards and for reconciliation only — never as an
        input to a computed KPI. Competitor-side answer-level data would be needed to
        compute their metrics the same way, and the prototype has none.
        """
        return self.raw["reference"]["brand_metrics"]

    def describe(self) -> dict:
        return {
            "path": str(self.path) if self.path else "<in-memory>",
            "brand": self.brand_name,
            "domain": self.brand_domain,
            "period": self.period_label,
            "prior_period": self.prior_period_label,
            "answers_current": len(self.answers("current")),
            "answers_prior": len(self.answers("prior")),
            "prompts": len(self.prompts),
            "engines": len(self.engines),
            "pages": len(self.pages),
        }
