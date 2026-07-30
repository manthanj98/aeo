# Does Pepper Atlas actually save the four hours?

**Eval and experiment design for the CS reporting workflow.**

Every CS manager spends 4+ hours a week building client reports: pulling from Google Search
Console, Google Analytics, citation/AEO crawls, backlinks and rank tracking; stitching it in
spreadsheets; building decks; emailing on a cadence. Pepper Atlas replaces that loop with
auto-ingested data, auto-surfaced Insights, a brand-governed narrative layer and a configurable
refresh cadence.

This document is not about whether that is a good idea. It is about how we would know.

Everything below is pre-registered — written before the data is seen — and everything numeric in
it is reproducible from `evals/` in this repository, which has no third-party dependencies.

---

## 1. First, decompose the four hours

"Building reports" is seven different tasks, and Atlas hits them very unevenly. Measuring the
aggregate without the split is how a project ends up celebrating a 30% saving on the two tasks
that were already cheap.

| # | Task | What Atlas does to it |
|---|------|----------------------|
| 1 | Pull and export across five sources | **Eliminated** |
| 2 | Stitch and normalise (date-align, dedupe, fold engine-name variants) | **Eliminated** |
| 3 | Build charts and deck, apply brand formatting | **Eliminated** |
| 4 | Write the narrative: what changed and why | **Partial** — Insights plus a brand-governed draft |
| 5 | Internal QA and review | **Unchanged, plausibly heavier** — now reviewing AI output |
| 6 | Send, schedule, follow up | **Reduced** — cadence plus client self-serve |
| 7 | Ad-hoc re-cuts and "what does this mean?" | **May increase** — a live dashboard invites questions |

Rows 5 and 7 are the honest part. A tool that generates a narrative creates a new verification
job, and a client with a live dashboard asks more questions, not fewer. Both are pre-registered as
things that may move the wrong way, and the headline number is net of them. If we only measured
rows 1–3 we would "prove" a saving that the team never feels.

---

## 2. Measurement: three instruments, and self-report is never the primary

| | Instrument | Role |
|---|---|---|
| **S1** | Atlas telemetry — event stream, sessions stitched with a 120s idle gap, each segment attributed to a `report_cycle_id` | Ground truth for in-product time, post-period |
| **S2** | Off-Atlas work-surface metadata — Drive revision timestamps on the client's sheet and deck, email send times, resolved to edit-session minutes per cycle | **Primary baseline instrument** |
| **S3** | Diary and random-moment sampling — 30-second end-of-cycle form, two random pings a day | Calibration only |

S2 carries the design. It exists **retrospectively**, so the baseline can be reconstructed from
the last two quarters without running a study first, and it exists in **both** periods, so the
before/after comparison is not confounded by a change of instrument. That second property is worth
more than its precision: an instrument that only exists after launch cannot measure a saving.

S3 exists because some of the work leaves no digital trace — thinking, calls, the ten minutes
spent deciding what the number means. The calibration factor from S2 to true minutes is fitted on
the shadowing set (D1) and carries its own confidence interval into the headline.

**Self-reported hours are secondary and never primary.** People over-report recurring work and
their estimates barely move when the work does. Self-report answers "does this feel better", which
is worth knowing and is not the same question.

### Units

- **Primary causal unit: the report cycle** (client × cadence). That is what the product acts on.
- **Business claim unit: the CSM-week.** That is what "4+ hours a week" means.

Both are reported. They can disagree, and the disagreement is the finding: a CSM whose per-cycle
time halves while their book of business grows has created capacity for the company without
getting an hour of their own week back. Only the weekly number answers the question as asked.

---

## 3. Datasets

| ID | Dataset | Size | Purpose |
|----|---------|------|---------|
| **D0** | Baseline cycle panel, reconstructed from S2 metadata over two quarters | all cycles × all CSMs | Baseline distribution, ICC, power inputs |
| **D1** | Time-and-motion shadowing, stratified by tier / cadence / tenure, two observers | 20–30 cycles | Fit the S2 → true-minutes calibration; validate the task taxonomy; report inter-rater reliability |
| **D2** | **Golden report corpus**: delivered reports **plus a frozen snapshot of the source data as of report time** | 60–100 | Offline insight and narrative eval |
| **D3** | Stress set: GSC lag, engine outage, near-zero citation volume, brand-new client, sign flips, new competitor entering | ~40 | Regression gate on every model or prompt change |
| **D4** | Client-side panel: dashboard engagement and per-cycle CSAT | experiment accounts | Detects work shifted onto the client |

**D2 is the one that has to start now.** The frozen input snapshot is the hard part: scoring
whether an insight was derivable requires the data *as it was*, and that cannot be reconstructed
after the fact. Every week we wait is a week of corpus we cannot build later.

Labelling: two CS managers independently mark every claim in a historical report as material or
filler and derivable or not; a third adjudicates; agreement is reported as Cohen's κ (Krippendorff's
α if we go past two labellers). The corpus lives in a restricted store and client identifiers are
scrubbed before anything reaches a judge model.

---

## 4. Offline gates — passed before anyone's time is measured

| Gate | Metric | Bar |
|------|--------|-----|
| **G1** Insight quality | Recall of findings both labellers called material, @ panel size | ≥ 0.70 |
| | False / trivial insight rate | ≤ 0.15 |
| | nDCG against materiality-weighted labels | reported, not gated in v1 |
| **G2** Narrative grounding | Numeric claims entailed by the snapshot (**deterministic checker**) | ≥ 0.98 |
| | Causal claims entailed (judged) | ≥ 0.90 |
| | Hallucinated entity — brand or URL absent from the client's data | **0** |
| **G3** Brand compliance | Deterministic lints from the Brand Guidelines surface | 100% |
| | Voice rubric (judged) | ≥ 0.90 |
| **Judge** | Cohen's κ vs human labels on a held-out slice | ≥ 0.60 |

Three commitments behind that table:

**Precision is the time metric; recall is the quality metric.** A missed insight is a worse report.
A wrong or trivial insight is a *slower* one — the CSM has to go and check it, and a CSM who
re-verifies every line has saved nothing. They are gated separately because they fail for
different reasons and get fixed by different people.

**Deterministic checks before judges.** Numbers in a report are extractable and comparable against
the snapshot the report was generated from; sending arithmetic to a language model to be graded is
slower, costlier and less reliable than comparing two floats. Only the irreducibly fuzzy parts —
is this causal claim supported, is this on-voice — go to a judge. The same applies to brand rules:
the product already stores them as data on its Brand Guidelines page ("round percentages to one
decimal place", "spell out AEO/GEO on first use"), and rules stored as data are rules a linter can
enforce at 100%, with nothing left to judge.

**Any judge that replaces a human is itself validated.** Ship at κ ≥ 0.60 against adjudicated human
labels, recalibrate on every model or prompt change, and keep auditing a human-only sample each
cycle to catch drift. A judge nobody has validated is an opinion with a number attached.

> **Product recommendation that falls out of building this.** The numeric checker in
> `evals/offline_eval.py` has to infer which metric each figure refers to, because the golden
> corpus is human-written and carries no provenance. For narrative *Atlas generates*, the
> generator should emit each numeric claim tagged with the metric it came from. That turns the
> highest-volume gate from a good heuristic into an exact check, and it costs one field.

---

## 5. The online experiment

**Design: stepped-wedge cluster randomised.** CSMs are randomised to a crossover step; roughly five
periods of three weeks. Everyone starts on the current workflow and everyone finishes on Atlas.

Why not a parallel A/B:

1. A CS team is 10–25 people. At that size a between-person comparison is badly underpowered;
   within-person contrasts recover most of the power (see §6).
2. Everyone gets the tool eventually, which avoids running a months-long control group whose
   members can see their colleagues' new toy.
3. A staged rollout is what would happen anyway, so the design costs nothing operationally.

The cost is that treatment is confounded with calendar time by construction — later periods have
more treated CSMs. Period fixed effects handle it; that *is* the stepped-wedge estimator. A
quarter-boundary indicator absorbs QBR spikes.

**Randomise CSMs, not accounts.** A CSM cannot be half-treated, and the outcome is CSM time.

**Contamination.** Control is enforced by feature flag, and control-arm Atlas logins are verified to
be zero rather than assumed. A survey item catches template sharing. ITT is primary; per-protocol
is secondary.

**The onboarding cycle is excluded, and reported.** Each CSM's first post-crossover cycle is
pre-registered as excluded from the primary estimate. The first report built on a new tool is
slower, and folding it in either flatters or sinks the number depending on when you stop measuring.
It gets its own line in the output.

**Primary outcome.** Calibrated active minutes per delivered cycle, on the log scale — the claim is
multiplicative, the distribution is right-skewed, and `1 − exp(τ)` reads directly as a percentage.

**Secondary.** Reporting hours per CSM-week; cycles delivered per CSM-week (freed capacity);
on-time rate; ad-hoc question volume; time-to-first-draft.

**Guardrails, with stop rules.** Per-cycle client CSAT; client-reported factual errors (each one a
counted P1); QA rejection rate; CSM confidence; renewal signal; escalation-to-creator rate — the
prototype's own "Talk to our team" action.

### Analysis

```
log(minutes_ict) = τ·treated_it + α_i + γ_t + δ·cycle_seq + ε
```

CSM fixed effects `α_i`, period fixed effects `γ_t`, cluster-robust (CR1) standard errors by CSM,
90% CI by cluster bootstrap with resampled clusters relabelled.

**The headline p-value is randomisation inference**, not the Wald test. With ~15 clusters,
cluster-robust standard errors over-reject; permuting the observed crossover schedule across CSMs
reproduces the actual randomisation and is exact under the sharp null. This is measured rather than
asserted — `evals/power.py --size-check` runs 300 null studies and finds:

| Test | Rejection rate at a true effect of zero (nominal α = 0.05) |
|------|---|
| CR1 cluster-robust Wald | **7.7%** |
| Randomisation inference | **5.3%** |

CR1 finds half again as many effects as it should when there is nothing there. It is still
reported, as a cross-check.

### Why the obvious analysis is not good enough

On simulated data with a **known 35% effect** planted, at the realistic team size of 15 CSMs, the
naive pre/post comparison of means recovers 32.5% on average with a mean absolute error of 0.055.
The fixed-effect estimator recovers 34.3% with an MAE of 0.029 — half the error. On a panel with a
**true effect of exactly zero**, the naive weekly comparison reads as *32% worse*, purely because
late-crossover CSMs and later calendar periods are not the same thing. Both results are asserted in
`evals/test_evals.py`, not just claimed here.

---

## 6. Power — simulated, not assumed

There is no clean closed form for a stepped wedge with unbalanced cluster sizes, a skewed outcome
and a pre-registered exclusion rule, so the power calculation is the data-generating process
itself. From `evals/power.py`, 250 simulated studies per cell, α = 0.05:

| CSMs | 10% | 15% | 20% | 30% | 40% | 50% | **MDE @ 80%** |
|------|-----|-----|-----|-----|-----|-----|-----|
| 10 | 0.27 | 0.51 | 0.80 | 1.00 | 1.00 | 1.00 | **20%** |
| 15 | 0.40 | 0.72 | 0.94 | 1.00 | 1.00 | 1.00 | **17%** |
| 20 | 0.46 | 0.86 | 0.98 | 1.00 | 1.00 | 1.00 | **14%** |
| 25 | 0.58 | 0.91 | 1.00 | 1.00 | 1.00 | 1.00 | **13%** |

A team of 15 detects a 17% saving. The ship bar is 50%, so the study is comfortably powered for the
effect that matters — the risk here is not missing a real win, it is measurement noise
manufacturing a fake one, which is what §5's size check is about.

**Better measurement is cheaper than more people.** Holding the team at 15 CSMs and varying only
the noise in the primary outcome:

| sd(log minutes) | MDE @ 80% |
|---|---|
| 0.65 (loose instrument) | 21% |
| 0.50 (baseline assumption) | 17% |
| 0.35 (tight, well-calibrated) | **13%** |

Tightening the instrument from 0.65 to 0.35 buys more than growing the team from 15 to 25. That is
a week of work on the S2 calibration versus a hiring round, and it is the single highest-leverage
thing to do before the study starts.

---

## 7. Decision criteria, pre-registered

50% is not a round number chosen for looks: it is what turns "4+ hours a week" into "under 2".

| Verdict | Condition |
|---|---|
| **SHIP** | ≥ 50% reduction in minutes/cycle, **and** 90% CI lower bound ≥ 35%, **and** ≥ 40% reduction in hours/CSM-week, **and** no guardrail breach |
| **ITERATE** | 20–50% reduction, or the reduction lands but the CI is wide or the weekly saving is absorbed |
| **KILL / RETHINK** | < 20% reduction, or a guardrail breach |

Guardrail breach: CSAT non-inferiority violated beyond −0.2 on the 5-point scale, any P1 factual
incident attributable to the auto-narrative, or QA rejection rate worse by more than 5pp. A CSAT
breach overrides any size of time saving — a faster report nobody trusts is not a saving.

The weekly bar is deliberately looser than the per-cycle bar, because freed time being refilled
with more accounts is a real and expected outcome. It should read as ITERATE, not SHIP, and not be
quietly reported as success.

**Where did the time go.** Pre-registered alongside the primary: freed hours are attributed to more
accounts, to strategic work, or to nothing, via the diary instrument and accounts-per-CSM. Without
this, "saved 4 hours" is unfalsifiable as a business claim — there is no observation that could
contradict it.

---

## 8. Threats to validity

| Threat | Mitigation |
|---|---|
| **Work shifted onto the client** | D4 — client-side engagement and CSAT. The single most likely way this claim is false |
| **Work shifted to analysts or design** | Measure their hours too, same instruments |
| Novelty effect | Report weeks 1–3 / 4–6 / 7+ as separate coefficients against a shared control. A durable saving is flat; the analysis prints this every run |
| Hawthorne | Stepped wedge means everyone is observed throughout, treated and not |
| Self-selection | Randomise. No volunteers, no early-access list |
| Instrument change pre/post | S2 spans both periods — the reason it is the baseline instrument |
| Parkinson / scope creep | Covariate-adjust on report scope (charts, pages, custom cuts). `analysis.py --adjust-scope` |
| Learning curve | First post-crossover cycle excluded and reported separately |
| Seasonality, QBR spikes | Period fixed effects plus a quarter-boundary indicator |

---

## 9. Sequence

1. **Now** — start the D2 golden corpus with frozen input snapshots. It cannot be built retroactively.
2. **Weeks 1–2** — reconstruct D0 from S2 metadata; run D1 shadowing; fit the calibration; re-run
   `power.py` on real variance and confirm the design is powered.
3. **Weeks 2–4** — label D2, build D3, run the offline gates. **If G1–G3 do not pass, the rollout
   does not start.** No amount of time saved survives a report the client stops trusting.
4. **Weeks 5–19** — the stepped wedge, five steps of three weeks.
5. **Week 20** — analysis exactly as specified above, verdict from the table in §7.

---

## 10. Reproducing everything here

No installs, no dependencies, Python 3.9+:

```bash
python3 evals/test_evals.py            # 51 tests: estimator recovers planted effects, gates fire
python3 evals/simulate.py --effect 0.35
python3 evals/analysis.py              # the pre-registered analysis, end to end
python3 evals/power.py --size-check    # the tables in §6 and the size check in §5
python3 evals/offline_eval.py --set golden   # clears
python3 evals/offline_eval.py --set stress   # blocks, and says why
```

See `evals/README.md` for what each number means.
