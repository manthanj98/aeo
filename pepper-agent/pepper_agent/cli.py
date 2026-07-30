"""Command-line entrypoint.

    python -m pepper_agent report                  metrics + findings, no drafts
    python -m pepper_agent draft --insight ins_04  one draft for one finding
    python -m pepper_agent run --top 3             the full loop
    python -m pepper_agent run --top 3 --offline   the full loop, no model call
    python -m pepper_agent inspect                 what the dataset holds

The agent is an upgrade to the prose, not a prerequisite for it: if the SDK cannot
start, every command still writes a complete report and says so in the output.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from . import fallback, render
from .dataset import Dataset, DatasetError
from .insights import Insight, detect, summarize
from .metrics import Metrics, compute
from .narrative import Narrative

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "out"


def _load(args) -> tuple[Dataset, Metrics, list[Insight]]:
    dataset = Dataset.load(args.data)
    metrics = compute(dataset)
    insights = detect(dataset, metrics)
    return dataset, metrics, insights


def _select(insights: list[Insight], top: int,
            insight_ids: list[str] | None) -> list[Insight]:
    """Pick which findings get drafts — by id if given, else the top N by severity."""
    if insight_ids:
        by_id = {i.id: i for i in insights}
        unknown = [i for i in insight_ids if i not in by_id]
        if unknown:
            raise SystemExit(
                f"unknown insight id(s): {', '.join(unknown)}\n"
                f"available: {', '.join(i.id for i in insights)}"
            )
        return [by_id[i] for i in insight_ids]
    return insights[:top] if top > 0 else []


def _merge_notes(agent_narrative: Narrative, template_narrative: Narrative) -> Narrative:
    """Fill any note the agent skipped with the template version.

    The agent is asked for notes on the findings being drafted; the report renders every
    finding. Rather than leaving the rest bare, the deterministic notes back-fill them,
    and the report says which findings the agent wrote about.
    """
    merged = dict(template_narrative.notes)
    merged.update(agent_narrative.notes)
    agent_narrative.notes = merged
    return agent_narrative


def _build_narrative(dataset: Dataset, metrics: Metrics, insights: list[Insight],
                     draft_for: list[Insight], args) -> Narrative:
    template = fallback.build(dataset, metrics, insights, draft_for)

    if args.offline:
        return template

    try:
        from . import agent as agent_module
    except ImportError as error:
        template.warnings.append(
            f"claude-agent-sdk is not installed ({error}); wrote the report from "
            f"deterministic templates. Install it with `pip install -r requirements.txt` "
            f"for agent-written analysis."
        )
        return template

    try:
        produced = asyncio.run(agent_module.run(
            dataset, metrics, insights, draft_for,
            model=args.model, verbose=not args.quiet,
        ))
    except agent_module.AgentUnavailable as error:
        template.warnings.append(
            f"The agent could not run ({error}); wrote the report from deterministic "
            f"templates instead. Every figure is still computed from the dataset — only "
            f"the prose is templated."
        )
        return template
    except KeyboardInterrupt:
        raise
    except Exception as error:  # noqa: BLE001 - a broken model path must not lose the report
        template.warnings.append(
            f"The agent failed unexpectedly ({type(error).__name__}: {error}); wrote the "
            f"report from deterministic templates instead."
        )
        return template

    return _merge_notes(produced, template)


def _emit(dataset: Dataset, metrics: Metrics, insights: list[Insight],
          narrative: Narrative, out_dir: Path, quiet: bool) -> None:
    written = render.write_all(out_dir, dataset, metrics, insights, narrative)
    if quiet:
        return
    print()
    print(render.render_terminal(dataset, metrics, insights, narrative))
    print()
    print("Wrote:")
    for path in written:
        try:
            shown = path.relative_to(Path.cwd())
        except ValueError:
            shown = path
        print(f"  {shown}")


# -- commands ------------------------------------------------------------------------

def cmd_report(args) -> int:
    dataset, metrics, insights = _load(args)
    narrative = _build_narrative(dataset, metrics, insights, [], args)
    _emit(dataset, metrics, insights, narrative, args.out, args.quiet)
    return 0


def cmd_run(args) -> int:
    dataset, metrics, insights = _load(args)
    draft_for = _select(insights, args.top, args.insight)
    if not draft_for and not args.quiet:
        print("No findings selected for drafting; writing the report only.")
    narrative = _build_narrative(dataset, metrics, insights, draft_for, args)
    _emit(dataset, metrics, insights, narrative, args.out, args.quiet)
    return 0


def cmd_draft(args) -> int:
    dataset, metrics, insights = _load(args)
    if not args.insight:
        raise SystemExit("draft requires --insight <id>; run `report` to list findings")
    draft_for = _select(insights, 0, args.insight)
    narrative = _build_narrative(dataset, metrics, insights, draft_for, args)
    _emit(dataset, metrics, insights, narrative, args.out, args.quiet)
    return 0


def cmd_inspect(args) -> int:
    dataset, metrics, insights = _load(args)
    described = dataset.describe()
    print("Dataset")
    for key, value in described.items():
        print(f"  {key:18} {value}")
    print()
    print("Computed KPIs")
    for kpi in metrics.kpis:
        print(f"  {kpi.label:18} {kpi.display:>8}  {kpi.trend_display:>10}  "
              f"{kpi.direction}")
    print()
    counts = summarize(insights)
    print(f"Detection: {counts['total']} findings from "
          f"{len(counts['rules_fired'])}/{len(counts['rules_available'])} rules")
    for severity in ("High", "Medium", "Low"):
        print(f"  {severity:8} {counts['by_severity'][severity]}")
    silent = sorted(set(counts["rules_available"]) - set(counts["rules_fired"]))
    if silent:
        print(f"  rules that found nothing: {', '.join(silent)}")
    print()
    for insight in insights:
        print(f"  {insight.id}  {insight.severity:<6} {insight.score:.3f}  "
              f"[{insight.action:<6}] {insight.rule:<26} {insight.title[:60]}")
    return 0


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data", type=Path, default=None,
                        help="path to visibility.json (default: data/visibility.json)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="output directory (default: out/)")
    parser.add_argument("--model", default="claude-opus-5",
                        help="model for the agent passes (default: claude-opus-5)")
    parser.add_argument("--offline", action="store_true",
                        help="skip the model entirely and use deterministic templates")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the terminal summary")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pepper_agent",
        description="AI-visibility (AEO) agent: computes KPIs, detects insights, and "
                    "drafts the content that responds to them.",
    )
    # Common flags are attached to the top level and to every subcommand, so that both
    # `run --offline` and `--offline run` work. Typing the flag after the subcommand is
    # the more natural order and argparse does not allow it otherwise.
    _add_common(parser)

    common = argparse.ArgumentParser(add_help=False)
    _add_common(common)

    subparsers = parser.add_subparsers(dest="command")

    report = subparsers.add_parser("report", parents=[common],
                                   help="metrics and findings, no drafts")
    report.set_defaults(func=cmd_report, top=0, insight=None)

    run = subparsers.add_parser("run", parents=[common],
                                help="report plus drafts for the top findings")
    run.add_argument("--top", type=int, default=3,
                     help="how many findings to draft for (default: 3)")
    run.add_argument("--insight", action="append",
                     help="draft for a specific finding id; repeatable, overrides --top")
    run.set_defaults(func=cmd_run)

    draft = subparsers.add_parser("draft", parents=[common],
                                  help="draft for one specific finding")
    draft.add_argument("--insight", action="append", required=True,
                       help="finding id, e.g. ins_04; repeatable")
    draft.set_defaults(func=cmd_draft, top=0)

    inspect = subparsers.add_parser(
        "inspect", parents=[common],
        help="print what the dataset holds and what detection found")
    inspect.set_defaults(func=cmd_inspect, top=0, insight=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except DatasetError as error:
        print(f"dataset error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
