# Pepper Atlas — does it actually save the four hours?

Every CS manager at Pepper spends 4+ hours a week building client reports. Pepper Atlas is the
proposed fix. This repository is the **eval and experiment design that would tell us whether it
works** — the measurement definition, the datasets, the experiment, and the pre-registered success
criteria, together with runnable code for all of it.

| | |
|---|---|
| **[`docs/eval-design.md`](docs/eval-design.md)** | The design. Start here |
| **[`evals/`](evals/)** | The runnable half: simulator, estimator, power analysis, offline quality gates, 51 tests |
| **[`artifacts/eval-design.html`](artifacts/eval-design.html)** | Visual readout of the same design |

```bash
python3 evals/test_evals.py          # 51 tests, ~15s, no dependencies
python3 evals/analysis.py            # the pre-registered analysis, end to end
python3 evals/offline_eval.py --set stress
```

Standard library only, Python 3.9+. Nothing to install.

---

### The short version

**Decompose before measuring.** "Building reports" is seven tasks. Atlas eliminates three of them,
partly helps a fourth, and plausibly makes two *worse* — reviewing AI output is new work, and a
client with a live dashboard asks more questions. The headline number has to be net of that.

**Measure with something that already exists.** The primary baseline instrument is Drive revision
and email metadata, because it can be read retrospectively — the baseline is reconstructable from
the last two quarters without running a study first, and it spans both periods so the comparison
is not confounded by a change of instrument. Self-reported hours are never primary.

**Gate quality before measuring time.** A missed insight is a worse report; a *wrong* insight is a
slower one, because someone has to check it. Both are gated offline, against a golden corpus of
historical reports paired with frozen snapshots of the data as it was at the time. That corpus has
to start being collected now — it cannot be reconstructed later.

**Stepped wedge, and randomisation inference.** At a team size of 10–25 a parallel A/B is
underpowered and unfair. The wedge gets within-person contrasts and everyone ends up on the tool.
With ~15 clusters, cluster-robust standard errors over-reject — measured at 7.7% against a nominal
5% — so the headline test permutes the actual crossover schedule instead.

**Report the per-cycle effect and the weekly claim separately.** They can disagree, and that
disagreement is the finding: a CSM whose per-cycle time halves while their book of business grows
has created capacity for the company without getting an hour of their own week back. Only the
weekly number answers the question as asked, and "where did the freed time go" is pre-registered
alongside it — otherwise "saved 4 hours" is a claim no observation could contradict.

**Ship at 50%**, because that is what turns "4+ hours" into "under 2". The simulated design detects
17% at 80% power with 15 CSMs, so the risk is not missing a real win — it is noise manufacturing a
fake one.
