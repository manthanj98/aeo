#!/usr/bin/env python3
"""The pre-registered analysis for the stepped-wedge rollout of Pepper Atlas.

Specification, fixed before the data is looked at:

  log(minutes_ict) = tau*treated_it + alpha_i + gamma_t + delta*cycle_seq + e

  i  CSM (cluster / randomisation unit)   alpha_i  CSM fixed effect
  t  stepped-wedge period                 gamma_t  calendar-period fixed effect
  c  report cycle

Four choices, each of which changes the answer:

1. LOG SCALE. The claim is multiplicative ("saves 4 of the 4+ hours"), the
   minutes distribution is right-skewed, and 1-exp(tau) reads directly as a
   percentage reduction. A level-scale model would be dominated by a handful of
   enterprise monsters.

2. PERIOD FIXED EFFECTS. In a stepped wedge, treatment and calendar time are
   confounded by construction: later periods have more treated CSMs. gamma_t is
   not a nicety, it is what makes the design identify anything at all. Every
   secondary cut below goes through the same two-way fixed-effect estimator for
   exactly this reason -- a naive pre/post mean on this design is biased, and
   in the bundled simulation it understates a known 35% effect as 14%.

3. RANDOMISATION INFERENCE AS THE HEADLINE TEST. With ~15 clusters, cluster-
   robust standard errors are anticonservative and will hand you significance
   you have not earned. Re-dealing the observed crossover schedule across CSMs
   reproduces the actual randomisation and is exact under the sharp null. The
   CR1 Wald test is reported alongside as a cross-check, and because power.py
   needs a cheap decision rule.

4. THE ONBOARDING CYCLE IS EXCLUDED AND REPORTED. The first report a CSM builds
   on a new tool is slower. Folding it into the headline either flatters or
   sinks the number depending on when you stop measuring, so it comes out of
   the primary estimate and gets its own line.

    python3 evals/analysis.py
    python3 evals/analysis.py --panel evals/data/null.csv --perms 2000
"""

import argparse
import math
import os
import random

from _linalg import SingularMatrixError, inverse, mean, quantile, solve
from _stats import t_two_sided_p
from panel import read_panel

# ---------------------------------------------------------------------------
# Pre-registered decision thresholds. See docs/eval-design.md section 6.
#
# 50% is not a round number picked for looks: it is what turns "4+ hours a
# week" into "under 2", which is the bar the rollout has to clear to be worth
# doing. The weekly bar is deliberately looser than the per-cycle bar, because
# a CSM whose freed time is refilled with more accounts is a real and expected
# outcome that should read as ITERATE, not SHIP.
# ---------------------------------------------------------------------------
SHIP_MIN_REDUCTION = 0.50          # minutes per report cycle
SHIP_CI_LOWER_BOUND = 0.35         # 90% CI lower bound on the same
SHIP_MIN_WEEKLY_REDUCTION = 0.40   # reporting hours per CSM-week
ITERATE_MIN_REDUCTION = 0.20
CSAT_NON_INFERIORITY = -0.20       # points on a 5-point scale
TARGET_WEEKLY_HOURS = 2.0          # the "4 hours" claim, restated as a level


# --------------------------------------------------------------------- design


def infer_design(rows):
    """Recover the wedge geometry from the panel itself."""
    weeks = sorted({r["week"] for r in rows})
    n_periods = len({r["period"] for r in rows})
    step_weeks = max(1, (max(weeks) + 1) // n_periods) if n_periods else 1
    assignment = {row["csm_id"]: row["start_step"] for row in rows}
    return {
        "n_periods": n_periods,
        "step_weeks": step_weeks,
        "assignment": assignment,
        "csms": sorted(assignment),
    }


def apply_assignment(rows, assignment, step_weeks):
    """Recompute treatment status under a (possibly permuted) crossover schedule.

    Also recomputes is_first_post, because the exclusion rule is a function of
    the assignment. Under randomisation inference the test statistic must be
    recomputed exactly as it was for the observed assignment -- including which
    rows it drops -- or the reference distribution belongs to a different
    statistic than the one being tested.
    """
    by_csm = {}
    for idx, row in enumerate(rows):
        by_csm.setdefault(row["csm_id"], []).append(idx)

    status = [None] * len(rows)
    for csm, indices in by_csm.items():
        start_step = assignment[csm]
        crossover_week = start_step * step_weeks
        indices.sort(key=lambda i: (rows[i]["cycle_seq"], rows[i]["week"]))
        seen_treated = False
        for i in indices:
            treated = 1 if rows[i]["period"] >= start_step else 0
            first_post = treated == 1 and not seen_treated
            if treated:
                seen_treated = True
            status[i] = {
                "treated": treated,
                "is_first_post": 1 if first_post else 0,
                "weeks_treated": (rows[i]["week"] - crossover_week + 1) if treated else 0,
            }
    return status


def build_design(records, labels, covariates=()):
    """Sparse two-way fixed-effect design.

    records   dicts with keys: csm_id, period, value (already log-transformed),
              plus any names listed in `covariates`.
    labels    parallel list; None means control, any other value names a
              treatment dummy. Multiple distinct labels give multiple
              coefficients in one model, which is how the durability buckets
              and the onboarding cycle are estimated against a shared control.

    Rows are stored as (column_index, value) pairs. Each row touches only a
    handful of columns, which is what makes the thousands of refits needed for
    randomisation inference and bootstrapping affordable in pure Python.
    """
    if not records:
        raise SingularMatrixError("no records to fit")

    csms = sorted({r["csm_id"] for r in records})
    periods = sorted({r["period"] for r in records})
    treat_names = sorted({lab for lab in labels if lab is not None})
    if not treat_names:
        raise SingularMatrixError("no treated records")

    # Drop the first level of each factor as the reference category, otherwise
    # the dummies are collinear with the intercept.
    csm_col = {csm: 1 + n for n, csm in enumerate(csms[1:])}
    base = 1 + len(csms) - 1
    period_col = {p: base + n for n, p in enumerate(periods[1:])}
    base += len(periods) - 1

    cov_col = {}
    cov_mean = {}
    for name in covariates:
        cov_col[name] = base
        cov_mean[name] = mean([r[name] for r in records])
        base += 1

    treat_col = {name: base + n for n, name in enumerate(treat_names)}
    k = base + len(treat_names)

    design = []
    y = []
    clusters = []
    for rec, lab in zip(records, labels):
        nz = [(0, 1.0)]
        col = csm_col.get(rec["csm_id"])
        if col is not None:
            nz.append((col, 1.0))
        col = period_col.get(rec["period"])
        if col is not None:
            nz.append((col, 1.0))
        for name in covariates:
            nz.append((cov_col[name], rec[name] - cov_mean[name]))
        if lab is not None:
            nz.append((treat_col[lab], 1.0))
        design.append(nz)
        y.append(rec["value"])
        clusters.append(rec["csm_id"])

    return {
        "design": design,
        "y": y,
        "clusters": clusters,
        "k": k,
        "treat_col": treat_col,
        "n_clusters": len(csms),
    }


# ------------------------------------------------------------------ estimation


def ols_sparse(design, k, y):
    """Ordinary least squares on a sparse row representation."""
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for nz, yi in zip(design, y):
        for a, (ja, va) in enumerate(nz):
            xty[ja] += va * yi
            for jb, vb in nz[a:]:
                if ja <= jb:
                    xtx[ja][jb] += va * vb
                else:
                    xtx[jb][ja] += va * vb
    for a in range(k):
        for b in range(a + 1, k):
            xtx[b][a] = xtx[a][b]
    return solve(xtx, xty), xtx


def cluster_robust_se(design, k, y, beta, clusters, xtx, col):
    """CR1 cluster-robust standard error for one coefficient.

    V = (X'X)^-1 [ sum_g X_g' u_g u_g' X_g ] (X'X)^-1 with the usual finite
    -sample correction G/(G-1) * (N-1)/(N-K). Reported alongside, never instead
    of, the randomisation-inference p-value.
    """
    residuals = []
    for nz, yi in zip(design, y):
        fitted = sum(v * beta[j] for j, v in nz)
        residuals.append(yi - fitted)

    scores = {}
    for nz, u, g in zip(design, residuals, clusters):
        vec = scores.setdefault(g, [0.0] * k)
        for j, v in nz:
            vec[j] += v * u

    n = len(y)
    g = len(scores)
    if g <= 1 or n <= k:
        return float("nan")

    meat = [[0.0] * k for _ in range(k)]
    for vec in scores.values():
        for a in range(k):
            if vec[a] == 0.0:
                continue
            va = vec[a]
            row = meat[a]
            for b in range(k):
                row[b] += va * vec[b]

    bread = inverse(xtx)
    correction = (g / (g - 1.0)) * ((n - 1.0) / (n - k))
    tmp = [sum(bread[col][a] * meat[a][b] for a in range(k)) for b in range(k)]
    var = sum(tmp[b] * bread[b][col] for b in range(k)) * correction
    return math.sqrt(var) if var > 0 else float("nan")


def fit(records, labels, covariates=(), want_se=True):
    """Fit the two-way FE model and return coefficients (+ CR1 SEs) per label."""
    d = build_design(records, labels, covariates)
    beta, xtx = ols_sparse(d["design"], d["k"], d["y"])
    out = {"coef": {}, "se": {}, "n": len(d["y"]), "g": d["n_clusters"]}
    for name, col in d["treat_col"].items():
        out["coef"][name] = beta[col]
        out["se"][name] = (
            cluster_robust_se(d["design"], d["k"], d["y"], beta, d["clusters"], xtx, col)
            if want_se
            else float("nan")
        )
    return out


# -------------------------------------------------------------- record shapers


def cycle_records(rows, status, include_onboarding=False, adjust_scope=False):
    """Cycle-level records for the primary model."""
    records, labels = [], []
    for row, st in zip(rows, status):
        if st["is_first_post"] and not include_onboarding:
            continue
        rec = {
            "csm_id": row["csm_id"],
            "period": row["period"],
            "value": math.log(row["minutes"]),
            "cycle_seq": float(row["cycle_seq"]),
        }
        if adjust_scope:
            rec["scope_charts"] = float(row["scope_charts"])
        records.append(rec)
        labels.append("treated" if st["treated"] else None)
    covariates = ("cycle_seq", "scope_charts") if adjust_scope else ("cycle_seq",)
    return records, labels, covariates


def decay_records(rows, status):
    """Same model, but treatment split by weeks since crossover.

    Three dummies against a shared untreated control, all with CSM and period
    fixed effects. A durable saving is flat across the buckets; a novelty
    artefact fades. Estimated, not eyeballed, because the naive bucket means
    are confounded with both who crossed over early and what month it is.
    """
    records, labels = [], []
    for row, st in zip(rows, status):
        if st["is_first_post"]:
            continue
        records.append({
            "csm_id": row["csm_id"],
            "period": row["period"],
            "value": math.log(row["minutes"]),
            "cycle_seq": float(row["cycle_seq"]),
        })
        if not st["treated"]:
            labels.append(None)
        elif st["weeks_treated"] <= 3:
            labels.append("weeks 1-3")
        elif st["weeks_treated"] <= 6:
            labels.append("weeks 4-6")
        else:
            labels.append("weeks 7+")
    return records, labels, ("cycle_seq",)


def onboarding_records(rows, status):
    """One model with two dummies: the first post-crossover cycle, and steady
    state. The onboarding cost is the gap between them."""
    records, labels = [], []
    for row, st in zip(rows, status):
        records.append({
            "csm_id": row["csm_id"],
            "period": row["period"],
            "value": math.log(row["minutes"]),
            "cycle_seq": float(row["cycle_seq"]),
        })
        if not st["treated"]:
            labels.append(None)
        elif st["is_first_post"]:
            labels.append("first cycle")
        else:
            labels.append("steady state")
    return records, labels, ("cycle_seq",)


def weekly_records(rows, status):
    """Collapse to CSM-weeks: the level at which the "4 hours a week" claim lives.

    The week containing a CSM's onboarding cycle is dropped, mirroring the
    cycle-level exclusion. Weeks with no cycles are genuinely zero-reporting
    weeks and are excluded rather than logged as zero -- log(0) is undefined,
    and a week with no report due is not evidence about the cost of reports.
    """
    buckets = {}
    contaminated = set()
    for row, st in zip(rows, status):
        key = (row["csm_id"], row["week"])
        if st["is_first_post"]:
            contaminated.add(key)
        bucket = buckets.setdefault(key, {
            "csm_id": row["csm_id"],
            "week": row["week"],
            "period": row["period"],
            "minutes": 0.0,
            "cycles": 0,
            "treated": 0,
        })
        bucket["minutes"] += row["minutes"]
        bucket["cycles"] += 1
        bucket["treated"] = max(bucket["treated"], st["treated"])

    records, labels, raw = [], [], []
    for key, bucket in sorted(buckets.items()):
        if key in contaminated:
            continue
        bucket["hours"] = bucket["minutes"] / 60.0
        records.append({
            "csm_id": bucket["csm_id"],
            "period": bucket["period"],
            "value": math.log(bucket["hours"]),
        })
        labels.append("treated" if bucket["treated"] else None)
        raw.append(bucket)
    return records, labels, (), raw


# ---------------------------------------------------------------- inference


def randomization_inference(rows, design_info, make_records, label, observed,
                            perms=1000, seed=11):
    """Test by re-dealing the observed crossover schedule across CSMs.

    Under the sharp null of no effect for anyone, each CSM's outcomes are fixed
    and only the schedule is random. Permuting the observed multiset of
    crossover steps therefore generates the exact reference distribution of
    tau-hat, with no appeal to asymptotics in the number of clusters -- which
    matters a great deal when that number is 15.
    """
    rng = random.Random(seed)
    csms = design_info["csms"]
    observed_steps = [design_info["assignment"][c] for c in csms]
    step_weeks = design_info["step_weeks"]

    null_taus = []
    for _ in range(perms):
        shuffled = list(observed_steps)
        rng.shuffle(shuffled)
        status = apply_assignment(rows, dict(zip(csms, shuffled)), step_weeks)
        try:
            records, labels, covariates = make_records(rows, status)[:3]
            result = fit(records, labels, covariates, want_se=False)
            null_taus.append(result["coef"][label])
        except (SingularMatrixError, KeyError):
            # A permutation that leaves a period with no treated variation is a
            # legitimate draw that yields no statistic; dropping it is standard.
            continue

    if not null_taus:
        return float("nan"), []
    extreme = sum(1 for t in null_taus if abs(t) >= abs(observed) - 1e-12)
    # Add-one correction: the observed assignment is itself one of the draws,
    # so a p-value of exactly zero is not attainable.
    return (extreme + 1) / (len(null_taus) + 1), null_taus


def cluster_bootstrap_ci(rows, status, make_records, label, reps=1000, seed=13,
                         level=0.90):
    """Percentile CI from resampling whole CSMs with replacement.

    Resampled clusters are relabelled so a CSM drawn twice gets two distinct
    fixed effects; without that the duplicated dummy columns are collinear and
    every replicate fails.
    """
    rng = random.Random(seed)
    by_csm = {}
    for i, row in enumerate(rows):
        by_csm.setdefault(row["csm_id"], []).append(i)
    csms = sorted(by_csm)

    taus = []
    for _ in range(reps):
        draw_rows, draw_status = [], []
        for copy_idx, csm in enumerate(rng.choices(csms, k=len(csms))):
            for i in by_csm[csm]:
                clone = dict(rows[i])
                clone["csm_id"] = f"{csm}#{copy_idx}"
                draw_rows.append(clone)
                draw_status.append(status[i])
        try:
            records, labels, covariates = make_records(draw_rows, draw_status)[:3]
            taus.append(fit(records, labels, covariates, want_se=False)["coef"][label])
        except (SingularMatrixError, KeyError):
            continue

    if len(taus) < 20:
        return float("nan"), float("nan"), len(taus)
    alpha = (1.0 - level) / 2.0
    return quantile(taus, alpha), quantile(taus, 1.0 - alpha), len(taus)


# ---------------------------------------------------------------------- driver


def guardrails(rows, status):
    treated_csat = [r["csat"] for r, s in zip(rows, status) if s["treated"]]
    control_csat = [r["csat"] for r, s in zip(rows, status) if not s["treated"]]
    treated_ot = [r["on_time"] for r, s in zip(rows, status) if s["treated"]]
    control_ot = [r["on_time"] for r, s in zip(rows, status) if not s["treated"]]
    return {
        "csat_delta": (mean(treated_csat) - mean(control_csat)) if treated_csat and control_csat else float("nan"),
        "csat_treated": mean(treated_csat) if treated_csat else float("nan"),
        "csat_control": mean(control_csat) if control_csat else float("nan"),
        "on_time_delta": (mean(treated_ot) - mean(control_ot)) if treated_ot and control_ot else float("nan"),
    }


def run(rows, perms=1000, boots=1000, seed=11, include_onboarding=False,
        adjust_scope=False):
    design_info = infer_design(rows)
    status = apply_assignment(rows, design_info["assignment"], design_info["step_weeks"])

    def make_primary(r, s):
        return cycle_records(r, s, include_onboarding, adjust_scope)

    # --- primary: minutes per report cycle -------------------------------
    records, labels, covariates = make_primary(rows, status)
    primary = fit(records, labels, covariates)
    tau = primary["coef"]["treated"]
    se = primary["se"]["treated"]
    df = primary["g"] - 1
    t_stat = tau / se if se == se and se else float("nan")

    if perms > 0:
        p_ri, null_taus = randomization_inference(
            rows, design_info, make_primary, "treated", tau, perms=perms, seed=seed
        )
    else:
        p_ri, null_taus = float("nan"), []

    if boots > 0:
        lo, hi, n_boot = cluster_bootstrap_ci(
            rows, status, make_primary, "treated", reps=boots, seed=seed + 2
        )
    else:
        lo, hi, n_boot = float("nan"), float("nan"), 0

    # --- business claim: reporting hours per CSM-week --------------------
    w_records, w_labels, w_cov, w_raw = weekly_records(rows, status)
    weekly = fit(w_records, w_labels, w_cov)
    tau_week = weekly["coef"]["treated"]
    se_week = weekly["se"]["treated"]
    if perms > 0:
        p_ri_week, _ = randomization_inference(
            rows, design_info, weekly_records, "treated", tau_week,
            perms=max(200, perms // 2), seed=seed + 4,
        )
    else:
        p_ri_week = float("nan")
    # Baseline level from untreated CSM-weeks only, then projected forward by
    # the adjusted effect. The raw post-period mean is confounded with calendar
    # time and with who crossed over first, so it is not the number to quote.
    pre_hours = [b["hours"] for b in w_raw if not b["treated"]]
    baseline_hours = mean(pre_hours) if pre_hours else float("nan")

    # --- durability, onboarding, guardrails ------------------------------
    d_records, d_labels, d_cov = decay_records(rows, status)
    try:
        decay = fit(d_records, d_labels, d_cov)
    except SingularMatrixError:
        decay = {"coef": {}, "se": {}}
    decay_counts = {}
    for lab in d_labels:
        if lab:
            decay_counts[lab] = decay_counts.get(lab, 0) + 1

    o_records, o_labels, o_cov = onboarding_records(rows, status)
    try:
        onboarding = fit(o_records, o_labels, o_cov, want_se=False)
    except SingularMatrixError:
        onboarding = {"coef": {}}

    return {
        "tau": tau,
        "reduction": 1.0 - math.exp(tau),
        "se": se,
        "t": t_stat,
        "p_wald": t_two_sided_p(t_stat, df) if t_stat == t_stat else float("nan"),
        "p_ri": p_ri,
        "n_null_draws": len(null_taus),
        "ci_low_reduction": 1.0 - math.exp(hi) if hi == hi else float("nan"),
        "ci_high_reduction": 1.0 - math.exp(lo) if lo == lo else float("nan"),
        "n_boot": n_boot,
        "n_cycles": primary["n"],
        "n_excluded": len(rows) - primary["n"],
        "n_clusters": primary["g"],
        "weekly": {
            "tau": tau_week,
            "reduction": 1.0 - math.exp(tau_week),
            "se": se_week,
            "p_ri": p_ri_week,
            "baseline_hours": baseline_hours,
            "projected_hours": baseline_hours * math.exp(tau_week),
            "n_weeks": weekly["n"],
        },
        "decay": {
            name: {
                "reduction": 1.0 - math.exp(decay["coef"][name]),
                "n": decay_counts.get(name, 0),
            }
            for name in ("weeks 1-3", "weeks 4-6", "weeks 7+")
            if name in decay["coef"]
        },
        "onboarding": {
            "first": 1.0 - math.exp(onboarding["coef"]["first cycle"]) if "first cycle" in onboarding["coef"] else float("nan"),
            "steady": 1.0 - math.exp(onboarding["coef"]["steady state"]) if "steady state" in onboarding["coef"] else float("nan"),
            "drag": math.exp(onboarding["coef"]["first cycle"] - onboarding["coef"]["steady state"])
            if "first cycle" in onboarding["coef"] and "steady state" in onboarding["coef"]
            else float("nan"),
        },
        "guardrails": guardrails(rows, status),
    }


def decision(result):
    """Apply the pre-registered gate. No post-hoc rules, no rescued conclusions."""
    reduction = result["reduction"]
    ci_low = result["ci_low_reduction"]
    weekly_reduction = result["weekly"]["reduction"]
    csat_delta = result["guardrails"]["csat_delta"]
    reasons = []

    if csat_delta == csat_delta and csat_delta < CSAT_NON_INFERIORITY:
        reasons.append(
            f"CSAT guardrail breached ({csat_delta:+.2f} < {CSAT_NON_INFERIORITY:+.2f}) -- "
            "a faster report nobody trusts is not a saving"
        )
        return "KILL / RETHINK", reasons

    ship = (
        reduction >= SHIP_MIN_REDUCTION
        and ci_low == ci_low
        and ci_low >= SHIP_CI_LOWER_BOUND
        and weekly_reduction >= SHIP_MIN_WEEKLY_REDUCTION
    )
    if ship:
        reasons.append(f"minutes/cycle down {reduction:.1%} (bar {SHIP_MIN_REDUCTION:.0%})")
        reasons.append(f"90% CI lower bound {ci_low:.1%} (bar {SHIP_CI_LOWER_BOUND:.0%})")
        reasons.append(
            f"hours/CSM-week down {weekly_reduction:.1%} (bar {SHIP_MIN_WEEKLY_REDUCTION:.0%}): "
            f"{result['weekly']['baseline_hours']:.1f} h -> {result['weekly']['projected_hours']:.1f} h"
        )
        return "SHIP", reasons

    if reduction >= ITERATE_MIN_REDUCTION:
        reasons.append(f"minutes/cycle down {reduction:.1%}, inside the iterate band "
                       f"[{ITERATE_MIN_REDUCTION:.0%}, {SHIP_MIN_REDUCTION:.0%})")
        if ci_low == ci_low and ci_low < SHIP_CI_LOWER_BOUND:
            reasons.append(f"90% CI lower bound {ci_low:.1%} below the {SHIP_CI_LOWER_BOUND:.0%} bar")
        if weekly_reduction < SHIP_MIN_WEEKLY_REDUCTION:
            reasons.append(
                f"hours/CSM-week only down {weekly_reduction:.1%} "
                f"({result['weekly']['baseline_hours']:.1f} h -> {result['weekly']['projected_hours']:.1f} h) -- "
                "per-cycle savings partly absorbed by account load"
            )
        return "ITERATE", reasons

    reasons.append(f"minutes/cycle down {reduction:.1%}, below the {ITERATE_MIN_REDUCTION:.0%} floor")
    return "KILL / RETHINK", reasons


def _fmt(value, spec="{:.3f}"):
    return "n/a" if value != value else spec.format(value)


def report(result):
    lines = []
    add = lines.append
    add("=" * 74)
    add("PRIMARY   minutes per report cycle          (two-way FE, log scale)")
    add("=" * 74)
    add(f"  cycles analysed       {result['n_cycles']}   ({result['n_excluded']} onboarding cycles excluded)")
    add(f"  clusters (CSMs)       {result['n_clusters']}")
    add(f"  tau                   {_fmt(result['tau'], '{:+.4f}')} log-minutes")
    add(f"  reduction             {_fmt(result['reduction'], '{:.1%}')}")
    add(f"  90% CI                [{_fmt(result['ci_low_reduction'], '{:.1%}')}, "
        f"{_fmt(result['ci_high_reduction'], '{:.1%}')}]   cluster bootstrap, {result['n_boot']} reps")
    add(f"  randomisation p       {_fmt(result['p_ri'], '{:.4f}')}   {result['n_null_draws']} permutations   <- headline")
    add(f"  CR1 Wald p            {_fmt(result['p_wald'], '{:.4f}')}   t = {_fmt(result['t'], '{:+.2f}')}, "
        f"df = {result['n_clusters'] - 1}   cross-check only")
    add("")
    add("CLAIM     reporting hours per CSM-week      (the original 4+ hours)")
    w = result["weekly"]
    add(f"  CSM-weeks analysed    {w['n_weeks']}")
    add(f"  reduction             {_fmt(w['reduction'], '{:.1%}')}   randomisation p {_fmt(w['p_ri'], '{:.4f}')}")
    add(f"  baseline              {_fmt(w['baseline_hours'], '{:.2f}')} h/week   (untreated CSM-weeks)")
    add(f"  adjusted post         {_fmt(w['projected_hours'], '{:.2f}')} h/week   "
        f"(target < {TARGET_WEEKLY_HOURS:.1f})")
    add("")
    add("DURABILITY  reduction by weeks since crossover")
    if result["decay"]:
        for name in ("weeks 1-3", "weeks 4-6", "weeks 7+"):
            bucket = result["decay"].get(name)
            if bucket:
                add(f"  {name:<20}  {_fmt(bucket['reduction'], '{:>6.1%}')}   n = {bucket['n']}")
    else:
        add("  not estimable on this panel")
    o = result["onboarding"]
    add(f"  first cycle           {_fmt(o['first'], '{:>6.1%}')}   vs steady state "
        f"{_fmt(o['steady'], '{:.1%}')}  ->  onboarding drag {_fmt(o['drag'], '{:.2f}')}x")
    add("")
    add("GUARDRAILS")
    g = result["guardrails"]
    add(f"  CSAT delta            {_fmt(g['csat_delta'], '{:+.2f}')}   "
        f"treated {_fmt(g['csat_treated'], '{:.2f}')} vs control {_fmt(g['csat_control'], '{:.2f}')}, "
        f"margin {CSAT_NON_INFERIORITY:+.2f}")
    add(f"  on-time delta         {_fmt(g['on_time_delta'], '{:+.1%}')}")
    add("")
    verdict, reasons = decision(result)
    add(f"PRE-REGISTERED DECISION:   {verdict}")
    for reason in reasons:
        add(f"  - {reason}")
    add("=" * 74)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_panel = os.path.join(os.path.dirname(__file__), "data", "panel.csv")
    parser.add_argument("--panel", default=default_panel)
    parser.add_argument("--perms", type=int, default=1000, help="randomisation-inference permutations")
    parser.add_argument("--boots", type=int, default=1000, help="cluster bootstrap replicates")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--include-onboarding", action="store_true",
                        help="keep each CSM's first post-crossover cycle in the primary estimate")
    parser.add_argument("--adjust-scope", action="store_true",
                        help="add report scope as a covariate (Parkinson / scope-creep check)")
    args = parser.parse_args()

    rows = read_panel(args.panel)
    result = run(
        rows,
        perms=args.perms,
        boots=args.boots,
        seed=args.seed,
        include_onboarding=args.include_onboarding,
        adjust_scope=args.adjust_scope,
    )
    print(report(result))


if __name__ == "__main__":
    main()
