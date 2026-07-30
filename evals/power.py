#!/usr/bin/env python3
"""Power and minimum detectable effect, by simulation.

There is no clean closed form for a stepped wedge with unbalanced cluster
sizes, a right-skewed outcome, a pre-registered exclusion rule and cycles
nested in accounts nested in CSMs. So the power calculation is the data
generating process itself: simulate the study many times at a known effect and
count how often the pre-registered test rejects.

Two things this is here to settle before anybody runs the study:

  * Is a CS team of this size big enough to see the effect we care about? A
    design that cannot detect a 40% saving is not worth three months of
    everyone's time, and it is much cheaper to learn that now.

  * Is more measurement precision cheaper than more people? The noise sweep
    answers this directly. Halving the measurement error of the primary
    outcome usually buys more power than hiring, and calibrating the S2
    instrument is a week of work rather than a hiring round.

Power is evaluated with the CR1 cluster-robust Wald test rather than
randomisation inference, purely for cost -- RI inside a power loop is a
thousand-fold more expensive. Because CR1 is known to over-reject at this
cluster count, --size-check measures both tests' false-positive rates at a
true effect of zero, so the gap is a reported number rather than an assumption.

    python3 evals/power.py
    python3 evals/power.py --sims 500 --size-check
"""

import argparse
import json
import math
import os

from _linalg import SingularMatrixError
from _stats import t_two_sided_p
from analysis import (
    SHIP_MIN_REDUCTION,
    apply_assignment,
    cycle_records,
    fit,
    infer_design,
    randomization_inference,
)
from simulate import simulate

DEFAULT_CSM_GRID = [10, 15, 20, 25]
DEFAULT_EFFECT_GRID = [0.10, 0.15, 0.20, 0.30, 0.40, 0.50]
DEFAULT_NOISE_GRID = [0.35, 0.50, 0.65]
TARGET_POWER = 0.80


def one_trial(seed, effect, n_csm, alpha=0.05, **sim_kwargs):
    """Simulate one study and return True if the pre-registered test rejects."""
    rows, _ = simulate(seed=seed, effect=effect, n_csm=n_csm, **sim_kwargs)
    design_info = infer_design(rows)
    status = apply_assignment(rows, design_info["assignment"], design_info["step_weeks"])
    try:
        records, labels, covariates = cycle_records(rows, status)
        result = fit(records, labels, covariates)
    except SingularMatrixError:
        return False
    tau = result["coef"]["treated"]
    se = result["se"]["treated"]
    if se != se or se <= 0:
        return False
    p = t_two_sided_p(tau / se, result["g"] - 1)
    return p < alpha


def power_at(effect, n_csm, sims, alpha=0.05, seed0=1000, **sim_kwargs):
    hits = sum(
        1 for s in range(sims) if one_trial(seed0 + s, effect, n_csm, alpha, **sim_kwargs)
    )
    return hits / sims


def mde(effects, powers, target=TARGET_POWER):
    """Smallest effect reaching `target` power, linearly interpolated."""
    for i in range(1, len(effects)):
        if powers[i] >= target:
            if powers[i - 1] >= target:
                continue
            span = powers[i] - powers[i - 1]
            if span <= 0:
                return effects[i]
            frac = (target - powers[i - 1]) / span
            return effects[i - 1] + frac * (effects[i] - effects[i - 1])
    return None


def size_check(n_csm, sims, perms, alpha=0.05, seed0=5000):
    """False-positive rate of both tests when the true effect is exactly zero.

    A correctly calibrated test rejects 5% of the time at alpha = 0.05. CR1 on
    15 clusters typically rejects more often than that; randomisation inference
    should sit on the nominal rate by construction. This is the evidence for
    making RI the headline test rather than a footnote.
    """
    cr1_hits = 0
    ri_hits = 0
    usable = 0
    for s in range(sims):
        rows, _ = simulate(seed=seed0 + s, effect=0.0, n_csm=n_csm)
        design_info = infer_design(rows)
        status = apply_assignment(rows, design_info["assignment"], design_info["step_weeks"])
        try:
            records, labels, covariates = cycle_records(rows, status)
            result = fit(records, labels, covariates)
        except SingularMatrixError:
            continue
        tau = result["coef"]["treated"]
        se = result["se"]["treated"]
        if se != se or se <= 0:
            continue
        usable += 1
        if t_two_sided_p(tau / se, result["g"] - 1) < alpha:
            cr1_hits += 1
        p_ri, _ = randomization_inference(
            rows, design_info,
            lambda r, st: cycle_records(r, st),
            "treated", tau, perms=perms, seed=seed0 + s,
        )
        if p_ri == p_ri and p_ri < alpha:
            ri_hits += 1
    if not usable:
        return {"n": 0, "cr1": float("nan"), "ri": float("nan")}
    return {"n": usable, "cr1": cr1_hits / usable, "ri": ri_hits / usable, "alpha": alpha}


def _bar(value, width=24):
    filled = int(round(value * width))
    return "#" * filled + "." * (width - filled)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sims", type=int, default=250, help="simulated studies per grid cell")
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--csms", type=int, nargs="+", default=DEFAULT_CSM_GRID)
    parser.add_argument("--effects", type=float, nargs="+", default=DEFAULT_EFFECT_GRID)
    parser.add_argument("--noise", type=float, nargs="+", default=DEFAULT_NOISE_GRID,
                        help="sd of log-minutes for the measurement-precision sweep")
    parser.add_argument("--noise-csms", type=int, default=15,
                        help="team size held fixed during the noise sweep")
    parser.add_argument("--size-check", action="store_true",
                        help="also measure the false-positive rate of CR1 vs randomisation inference")
    parser.add_argument("--size-sims", type=int, default=60)
    parser.add_argument("--size-perms", type=int, default=200)
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "data", "power.json"))
    args = parser.parse_args()

    out = {"sims": args.sims, "alpha": args.alpha, "target_power": TARGET_POWER}

    print("=" * 74)
    print(f"POWER   probability the pre-registered test detects a real saving")
    print(f"        {args.sims} simulated studies per cell, alpha = {args.alpha}")
    print("=" * 74)
    header = "  CSMs  " + "".join(f"{e:>8.0%}" for e in args.effects) + "     MDE @ 80%"
    print(header)

    grid = {}
    for n_csm in args.csms:
        powers = [power_at(e, n_csm, args.sims, args.alpha) for e in args.effects]
        grid[n_csm] = powers
        detect = mde(args.effects, powers)
        label = f"{detect:.0%}" if detect is not None else f">{max(args.effects):.0%}"
        print(f"  {n_csm:>4}  " + "".join(f"{p:>8.2f}" for p in powers) + f"     {label:>8}")
    out["grid"] = {str(k): v for k, v in grid.items()}
    out["effects"] = args.effects
    out["mde"] = {
        str(k): mde(args.effects, v) for k, v in grid.items()
    }

    # Power at the pre-registered ship bar, or the closest effect on the grid.
    bar_effect = min(args.effects, key=lambda e: abs(e - SHIP_MIN_REDUCTION))
    print()
    print(f"        power at the {bar_effect:.0%} ship bar")
    for n_csm in args.csms:
        p = grid[n_csm][args.effects.index(bar_effect)]
        print(f"  {n_csm:>4}  {_bar(p)}  {p:.2f}")
    out["ship_bar_effect"] = bar_effect

    print()
    print("=" * 74)
    print(f"MEASUREMENT PRECISION   is a tighter instrument cheaper than more people?")
    print(f"                        team size fixed at {args.noise_csms} CSMs")
    print("=" * 74)
    noise_effects = [e for e in args.effects if e <= 0.30]
    print("  sd(log)  " + "".join(f"{e:>8.0%}" for e in noise_effects) + "     MDE @ 80%")
    noise_grid = {}
    for sd in args.noise:
        powers = [
            power_at(e, args.noise_csms, args.sims, args.alpha, sd_log=sd)
            for e in noise_effects
        ]
        noise_grid[sd] = powers
        detect = mde(noise_effects, powers)
        label = f"{detect:.0%}" if detect is not None else f">{max(noise_effects):.0%}"
        print(f"  {sd:>7.2f}  " + "".join(f"{p:>8.2f}" for p in powers) + f"     {label:>8}")
    out["noise_effects"] = noise_effects
    out["noise_grid"] = {str(k): v for k, v in noise_grid.items()}
    out["noise_mde"] = {str(k): mde(noise_effects, v) for k, v in noise_grid.items()}
    out["noise_csms"] = args.noise_csms

    if args.size_check:
        print()
        print("=" * 74)
        print("SIZE CHECK   false-positive rate when the true effect is zero")
        print(f"             {args.size_sims} null studies, {args.size_perms} permutations each")
        print("=" * 74)
        for n_csm in (args.noise_csms,):
            res = size_check(n_csm, args.size_sims, args.size_perms, args.alpha)
            print(f"  {n_csm} CSMs, n = {res['n']} usable studies, nominal alpha = {args.alpha}")
            print(f"    CR1 cluster-robust Wald   rejects {res['cr1']:.1%}")
            print(f"    randomisation inference   rejects {res['ri']:.1%}")
            out["size_check"] = {"n_csm": n_csm, **res}

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print()
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
