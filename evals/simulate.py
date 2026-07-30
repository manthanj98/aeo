#!/usr/bin/env python3
"""Generate a synthetic report-cycle panel with a known, injected effect.

Why a simulator at all: the analysis in analysis.py is only trustworthy if it
recovers an effect we planted, and refuses to find one we didn't. This module
is the ground truth for both of those checks (see test_evals.py) and the data
generating process behind the power curves in power.py.

The defaults are anchored to the problem as stated: a CSM carrying ~6 accounts
on mixed cadence closes roughly 2.4 report cycles a week, and 4+ hours a week
across those cycles works out to ~100 minutes of active build time per cycle.
That is the baseline the simulator reproduces.

    python3 evals/simulate.py --seed 7 --effect 0.35
    python3 evals/simulate.py --seed 7 --effect 0.0 --out evals/data/null.csv
"""

import argparse
import math
import os
import random

from panel import csm_week_hours, write_panel

# Cadence -> weeks between report cycles, with the mix we assume across a book
# of business. Biweekly dominates; weekly is the enterprise minority.
CADENCES = [("weekly", 1, 0.25), ("biweekly", 2, 0.45), ("monthly", 4, 0.30)]

# Tier -> (probability, multiplier on build time). Enterprise reports are
# bigger and slower; starter reports are near-templated.
TIERS = [("enterprise", 0.20, 1.35), ("growth", 0.50, 1.00), ("starter", 0.30, 0.75)]


def _weighted_choice(rng, options):
    """Pick from [(value, weight, ...), ...] using the second element as weight."""
    total = sum(opt[1] for opt in options)
    draw = rng.random() * total
    upto = 0.0
    for opt in options:
        upto += opt[1]
        if draw <= upto:
            return opt
    return options[-1]


def assign_start_steps(rng, csm_ids, steps):
    """Assign each CSM a stepped-wedge crossover step, balanced across sequences.

    Period 0 is all-control by construction (that baseline period is what lets
    the design separate the treatment effect from the calendar-time effect), so
    crossover steps run 1..steps-1. CSMs are shuffled then dealt round-robin so
    the sequences stay as close to equal size as the team allows.
    """
    if steps < 2:
        raise ValueError("a stepped wedge needs at least 2 periods")
    shuffled = list(csm_ids)
    rng.shuffle(shuffled)
    sequences = list(range(1, steps))
    return {csm: sequences[i % len(sequences)] for i, csm in enumerate(shuffled)}


def simulate(
    seed=7,
    effect=0.35,
    n_csm=15,
    n_accounts=6,
    steps=5,
    step_weeks=3,
    baseline_minutes=100.0,
    sd_log=0.50,
    icc_csm=0.30,
    icc_account=0.15,
    time_drift=0.01,
    learning_penalty=0.22,
    novelty_decay=0.0,
    scope_creep=0.0,
    csat_effect=0.0,
):
    """Return (rows, truth) for one synthetic study.

    effect          Fractional reduction in minutes per cycle. 0.35 == 35% faster.
    novelty_decay   Per-week erosion of the effect after crossover. 0 keeps the
                    effect flat; 0.02 makes it fade, which is what a novelty
                    artefact looks like and what the decay analysis must catch.
    scope_creep     Extra charts per treated cycle. Models Parkinson's law: the
                    tool makes reports cheap, so reports quietly get bigger and
                    eat the saving.
    csat_effect     Shift in per-cycle CSAT under treatment. Negative values let
                    the guardrail be exercised in tests.
    """
    rng = random.Random(seed)

    # Split the total log-scale variance into CSM, account and residual parts.
    total_var = sd_log ** 2
    sd_csm = math.sqrt(total_var * icc_csm)
    sd_account = math.sqrt(total_var * icc_account)
    sd_resid = math.sqrt(max(total_var * (1.0 - icc_csm - icc_account), 1e-9))

    tau = math.log(1.0 - effect) if effect < 1.0 else float("-inf")

    csm_ids = [f"csm_{i:02d}" for i in range(n_csm)]
    start_steps = assign_start_steps(rng, csm_ids, steps)
    total_weeks = steps * step_weeks

    csm_effects = {csm: rng.gauss(0.0, sd_csm) for csm in csm_ids}

    rows = []
    for csm in csm_ids:
        start_step = start_steps[csm]
        crossover_week = start_step * step_weeks
        csm_rows = []

        for a in range(n_accounts):
            account_id = f"{csm}_acct_{a}"
            tier, _, tier_mult = _weighted_choice(rng, TIERS)
            cadence, interval, _ = _weighted_choice(rng, CADENCES)
            account_effect = rng.gauss(0.0, sd_account)
            offset = rng.randrange(interval)

            for week in range(offset, total_weeks, interval):
                period = week // step_weeks
                treated = 1 if period >= start_step else 0
                weeks_treated = (week - crossover_week + 1) if treated else 0

                # Effect size, optionally eroding week by week after crossover.
                if treated:
                    retained = max(0.0, 1.0 - novelty_decay * max(0, weeks_treated - 1))
                    treat_term = tau * retained
                else:
                    treat_term = 0.0

                scope = 8 + (2 if tier == "enterprise" else 0)
                scope += sum(1 for _ in range(4) if rng.random() < 0.5) - 2
                if treated and scope_creep:
                    scope += int(scope_creep) + (
                        1 if rng.random() < (scope_creep - int(scope_creep)) else 0
                    )
                scope = max(3, scope)

                log_minutes = (
                    math.log(baseline_minutes)
                    + math.log(tier_mult)
                    + csm_effects[csm]
                    + account_effect
                    + time_drift * period
                    + treat_term
                    + 0.02 * (scope - 9)
                    + rng.gauss(0.0, sd_resid)
                )

                csm_rows.append(
                    {
                        "csm_id": csm,
                        "account_id": account_id,
                        "tier": tier,
                        "cadence": cadence,
                        "period": period,
                        "week": week,
                        "start_step": start_step,
                        "treated": treated,
                        "weeks_treated": weeks_treated,
                        "minutes": math.exp(log_minutes),
                        "scope_charts": scope,
                        "_log_minutes": log_minutes,
                    }
                )

        # cycle_seq and is_first_post are properties of the CSM's own ordering,
        # so they can only be filled in once all of that CSM's cycles exist.
        csm_rows.sort(key=lambda r: (r["week"], r["account_id"]))
        seen_treated = False
        for seq, row in enumerate(csm_rows):
            row["cycle_seq"] = seq
            first_post = row["treated"] == 1 and not seen_treated
            row["is_first_post"] = 1 if first_post else 0
            if row["treated"]:
                seen_treated = True
            # The first cycle on a new tool is slower, not faster. Pre-register
            # it as excluded or it will either flatter or sink the estimate.
            if first_post and learning_penalty:
                row["_log_minutes"] += learning_penalty
                row["minutes"] = math.exp(row["_log_minutes"])

        rows.extend(csm_rows)

    rows.sort(key=lambda r: (r["week"], r["csm_id"], r["account_id"]))
    for i, row in enumerate(rows):
        row["cycle_id"] = f"cyc_{i:05d}"
        del row["_log_minutes"]

        # Guardrails. On-time slips when a cycle runs long; CSAT is flat under
        # treatment unless csat_effect is set to exercise the stop rule.
        row["on_time"] = 1 if (row["minutes"] < 200 or rng.random() < 0.75) else 0
        csat = rng.gauss(4.3 + (csat_effect if row["treated"] else 0.0), 0.5)
        row["csat"] = round(min(5.0, max(1.0, csat)), 2)

    truth = {
        "effect": effect,
        "tau": tau,
        "n_csm": n_csm,
        "n_cycles": len(rows),
        "start_steps": start_steps,
        "steps": steps,
        "step_weeks": step_weeks,
    }
    return rows, truth


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--effect", type=float, default=0.35, help="fractional reduction in minutes/cycle")
    parser.add_argument("--csms", type=int, default=15)
    parser.add_argument("--accounts", type=int, default=6, help="accounts per CSM")
    parser.add_argument("--steps", type=int, default=5, help="stepped-wedge periods")
    parser.add_argument("--step-weeks", type=int, default=3)
    parser.add_argument("--baseline-minutes", type=float, default=100.0)
    parser.add_argument("--sd-log", type=float, default=0.50)
    parser.add_argument("--icc-csm", type=float, default=0.30)
    parser.add_argument("--icc-account", type=float, default=0.15)
    parser.add_argument("--time-drift", type=float, default=0.01)
    parser.add_argument("--learning-penalty", type=float, default=0.22)
    parser.add_argument("--novelty-decay", type=float, default=0.0)
    parser.add_argument("--scope-creep", type=float, default=0.0)
    parser.add_argument("--csat-effect", type=float, default=0.0)
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "data", "panel.csv"))
    args = parser.parse_args()

    rows, truth = simulate(
        seed=args.seed,
        effect=args.effect,
        n_csm=args.csms,
        n_accounts=args.accounts,
        steps=args.steps,
        step_weeks=args.step_weeks,
        baseline_minutes=args.baseline_minutes,
        sd_log=args.sd_log,
        icc_csm=args.icc_csm,
        icc_account=args.icc_account,
        time_drift=args.time_drift,
        learning_penalty=args.learning_penalty,
        novelty_decay=args.novelty_decay,
        scope_creep=args.scope_creep,
        csat_effect=args.csat_effect,
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    write_panel(args.out, rows)

    weeks = csm_week_hours(rows)
    pre = [w["hours"] for w in weeks if not w["treated"]]
    post = [w["hours"] for w in weeks if w["treated"]]

    print(f"wrote {len(rows)} report cycles for {truth['n_csm']} CSMs -> {args.out}")
    print(f"  design         stepped wedge, {args.steps} periods x {args.step_weeks} weeks")
    print(f"  injected effect {args.effect:.0%} reduction in minutes/cycle (tau = {truth['tau']:.4f})")
    if pre:
        print(f"  pre-crossover  {sum(pre)/len(pre):.2f} reporting hours per CSM-week")
    if post:
        print(f"  post-crossover {sum(post)/len(post):.2f} reporting hours per CSM-week")


if __name__ == "__main__":
    main()
