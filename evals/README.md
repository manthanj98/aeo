# `evals/` — the runnable half of the design

Everything in [`docs/eval-design.md`](../docs/eval-design.md) that involves a number is computed
here. **No third-party dependencies**: standard library only, Python 3.9+. Nothing to install.

That constraint is not only about portability. With ~15 clusters the right inference is
randomisation-based rather than asymptotic, and randomisation tests and cluster bootstraps are a
few hundred lines of plain Python. Reaching for `statsmodels` here would have bought a worse
estimator.

```bash
python3 evals/test_evals.py -v        # 51 tests, ~15s
python3 evals/simulate.py --effect 0.35
python3 evals/analysis.py
python3 evals/power.py --size-check   # ~6 min with the size check, ~2 min without
python3 evals/offline_eval.py --set golden
python3 evals/offline_eval.py --set stress
```

Scripts run from anywhere: `python3 evals/analysis.py` from the repo root works the same as
`python3 analysis.py` from inside `evals/`.

---

## Files

| File | What it is |
|------|-----------|
| `simulate.py` | Data-generating process. A synthetic stepped-wedge panel with a **known** effect planted in it |
| `analysis.py` | The pre-registered analysis: two-way FE, randomisation inference, cluster bootstrap, decision gate |
| `power.py` | Monte Carlo power and MDE, plus the size check that justifies the choice of test |
| `offline_eval.py` | The G1/G2/G3 quality gates that must pass before the rollout starts |
| `panel.py` | The report-cycle schema, with every column documented |
| `_linalg.py`, `_stats.py` | Dense solve/inverse; incomplete beta, Student-t, Cohen's κ |
| `test_evals.py` | 51 tests |
| `fixtures/` | Sample golden (D2) and stress (D3) corpora, plus a judge-validation slice |
| `data/` | Generated panels and `power.json`. Regenerable; safe to delete |

---

## Reading the analysis output

```
PRIMARY   minutes per report cycle          (two-way FE, log scale)
  reduction             32.9%
  90% CI                [26.1%, 39.4%]   cluster bootstrap, 500 reps
  randomisation p       0.0020   500 permutations   <- headline
  CR1 Wald p            0.0000   t = -6.52, df = 14   cross-check only
```

**Take the randomisation p-value.** The CR1 Wald test is printed beside it because it is the
conventional thing to report, and because `power.py --size-check` shows exactly how much it
over-states: across 300 studies with a true effect of zero, CR1 rejects 7.7% of the time at a
nominal 5%, while randomisation inference rejects 5.3%.

```
CLAIM     reporting hours per CSM-week      (the original 4+ hours)
  baseline              5.21 h/week   (untreated CSM-weeks)
  adjusted post         3.26 h/week   (target < 2.0)
```

The per-cycle effect and the weekly claim are separate lines because they can disagree, and the
disagreement is the point: per-cycle time can fall while the week stays full because the book of
business grew. Only the weekly line answers the question that was asked.

Note that `adjusted post` is the baseline projected forward by the **model** estimate, not the raw
post-period mean. The raw mean is confounded with calendar time and with who crossed over first —
on a panel with a true effect of exactly zero it reads as 32% *worse*.

```
DURABILITY  reduction by weeks since crossover
  weeks 1-3               31.0%   n = 104
  weeks 4-6               34.5%   n = 98
  weeks 7+                29.5%   n = 108
  first cycle             28.1%   vs steady state 32.5%  ->  onboarding drag 1.07x
```

Three coefficients against a shared control, not three raw bucket means — the buckets are
confounded with both who crossed over early and what month it is. Flat means durable; a downward
slope means novelty. `onboarding drag` is what a CSM's first report on the new tool costs relative
to their steady state, and it is excluded from the headline rather than hidden in it.

---

## Reading the offline gate output

The golden set **clears**; the stress set **blocks** and names every defect. Exit code is 1 on any
failure, so this drops into CI as-is.

```
G1  insight quality
  recall of material findings   0.944    <- protects the report
  false / trivial insight rate  0.125    <- protects the four hours
```

Those two labels are the whole argument for gating both. A missed insight makes the report worse.
A wrong insight makes the report *slower*, because the CSM has to go and check it — and a CSM who
checks every line has saved nothing.

The stress fixtures each carry one planted defect, and `test_evals.py` asserts that the harness
finds exactly those and no others:

| Fixture | Defect | Gate that catches it |
|---|---|---|
| `stress_001_gsc_lag` | Narrative quotes 14.2% when the snapshot says 9.8% | numeric grounding |
| `stress_002_hallucinated_entities` | A competitor the client does not track, and an invented URL | entity hallucination |
| `stress_003_brand_rules` | `16%`, bare `2.0 pts`, `N/A`, unexpanded `AEO` | brand lints |
| `stress_004_sparse_new_client` | Panel filled with unsupported insights on an 11-day-old account | insight false rate, causal grounding |

---

## The fixtures are a sample, not the corpus

`fixtures/golden/` holds 6 report cycles standing in for the 60–100 of D2, and packs them into one
file for readability; the real corpus is one file per cycle. `matched_finding` and the two
`labeler_*` votes are **annotation outputs**, not model outputs — two CS managers labelled every
claim in the historical report and a third adjudicated the matches. The fixtures encode the corpus
*after* labelling, which is what a scoring harness consumes.

Likewise `judged` blocks hold the recorded verdicts of a validated judge. The harness scores them;
it does not call a model. Judge validation itself lives in `fixtures/judge_validation.json` and is
gated at Cohen's κ ≥ 0.60.

---

## Verifying the estimator rather than trusting it

The tests worth reading are in `TestEstimator`:

- `test_recovers_injected_effect` — plant 35%, get 35% ± 3pp back, across three seeds.
- `test_null_effect_is_not_manufactured` / `test_null_is_rarely_rejected` — plant nothing, find
  nothing, and reject the true null no more than occasionally.
- `test_fe_beats_naive_difference` — at the realistic team size of 15, the naive pre/post contrast
  has a mean absolute error of 0.055 against the fixed-effect estimator's 0.029. The design
  argument, asserted rather than argued.
- `test_onboarding_cost_is_recovered_and_excluded` — the planted 1.25× first-cycle penalty comes
  back out, and all 120 onboarding cycles are excluded from the headline.
- `test_novelty_decay_is_visible_when_present` — a planted 5%/week erosion shows up in the
  durability buckets, and a flat effect stays flat.
- `test_scope_creep_shows_up_...` — with report scope quietly growing under treatment, the
  unadjusted estimate overstates what the tool did, and `--adjust-scope` recovers the gap.

---

## Useful flags

```bash
# Sensitivity: what the headline looks like if the onboarding cycle is kept in
python3 evals/analysis.py --include-onboarding

# Parkinson check: hold report scope constant
python3 evals/analysis.py --adjust-scope

# A study that should read KILL
python3 evals/simulate.py --effect 0.0 --out evals/data/null.csv
python3 evals/analysis.py --panel evals/data/null.csv

# A study that should read SHIP
python3 evals/simulate.py --effect 0.58 --out evals/data/ship.csv
python3 evals/analysis.py --panel evals/data/ship.csv

# Exercise the CSAT stop rule
python3 evals/simulate.py --effect 0.60 --csat-effect -0.4 --out evals/data/breach.csv
python3 evals/analysis.py --panel evals/data/breach.csv

# Novelty that fades, and reports that quietly get bigger
python3 evals/simulate.py --novelty-decay 0.05
python3 evals/simulate.py --scope-creep 3
```
