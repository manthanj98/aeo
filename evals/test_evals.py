#!/usr/bin/env python3
"""Tests for the eval package. Standard library only.

The tests that matter are the ones that would catch a wrong answer rather than
a crash:

  * the estimator recovers an effect that was deliberately planted, and does
    not find one that was not (test_recovers_injected_effect, test_null);
  * the two-way fixed-effect specification removes a bias that the obvious
    pre/post comparison does not (test_fe_beats_naive_difference) -- this is
    the whole argument for the design, so it is asserted rather than claimed;
  * the offline gates fire on the specific defects planted in the stress
    fixtures, and stay quiet on the clean ones.

    python3 evals/test_evals.py -v
"""

import math
import os
import statistics
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _linalg import SingularMatrixError, inverse, quantile, solve
from _stats import cohens_kappa, t_critical, t_two_sided_p
import analysis
import offline_eval
from panel import COLUMNS, csm_week_hours, read_panel, write_panel
from simulate import assign_start_steps, simulate

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


# --------------------------------------------------------------------- linalg


class TestLinalg(unittest.TestCase):
    def test_solve(self):
        a = [[2.0, 1.0], [1.0, 3.0]]
        x = solve(a, [5.0, 10.0])
        self.assertAlmostEqual(x[0], 1.0, places=9)
        self.assertAlmostEqual(x[1], 3.0, places=9)
        # The caller's matrix must survive.
        self.assertEqual(a, [[2.0, 1.0], [1.0, 3.0]])

    def test_inverse_round_trip(self):
        a = [[4.0, 7.0, 2.0], [3.0, 6.0, 1.0], [2.0, 5.0, 3.0]]
        inv = inverse(a)
        for i in range(3):
            for j in range(3):
                got = sum(a[i][k] * inv[k][j] for k in range(3))
                self.assertAlmostEqual(got, 1.0 if i == j else 0.0, places=9)

    def test_singular_raises(self):
        with self.assertRaises(SingularMatrixError):
            solve([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])

    def test_quantile(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        self.assertAlmostEqual(quantile(xs, 0.0), 1.0)
        self.assertAlmostEqual(quantile(xs, 1.0), 4.0)
        self.assertAlmostEqual(quantile(xs, 0.5), 2.5)


# ---------------------------------------------------------------------- stats


class TestStats(unittest.TestCase):
    def test_t_p_values_against_known_table(self):
        self.assertAlmostEqual(t_two_sided_p(2.0, 10), 0.07339, places=4)
        self.assertAlmostEqual(t_two_sided_p(2.228, 10), 0.05001, places=4)
        self.assertAlmostEqual(t_two_sided_p(0.0, 14), 1.0, places=6)

    def test_t_critical(self):
        self.assertAlmostEqual(t_critical(14, 0.05), 2.1448, places=3)
        self.assertAlmostEqual(t_critical(10, 0.10), 1.8125, places=3)

    def test_cohens_kappa_hand_computed(self):
        # 50 items. Agree on 15 'y' and 25 'n'; observed 0.80, expected 0.52.
        a = ["y"] * 20 + ["n"] * 30
        b = ["y"] * 15 + ["n"] * 5 + ["y"] * 5 + ["n"] * 25
        self.assertAlmostEqual(cohens_kappa(a, b), (0.80 - 0.52) / 0.48, places=6)

    def test_kappa_undefined_on_degenerate_labels(self):
        self.assertTrue(math.isnan(cohens_kappa(["y"] * 10, ["y"] * 10)))


# ------------------------------------------------------------------ simulator


class TestSimulator(unittest.TestCase):
    def test_crossover_sequences_are_balanced_and_never_period_zero(self):
        import random

        steps = 5
        assignment = assign_start_steps(random.Random(0), [f"c{i}" for i in range(12)], steps)
        self.assertEqual(len(assignment), 12)
        self.assertTrue(all(1 <= s <= steps - 1 for s in assignment.values()))
        counts = {}
        for s in assignment.values():
            counts[s] = counts.get(s, 0) + 1
        # 12 CSMs across 4 sequences divides evenly; nothing may be starved.
        self.assertEqual(sorted(counts.values()), [3, 3, 3, 3])

    def test_deterministic_given_seed(self):
        a, _ = simulate(seed=42, effect=0.3, n_csm=6)
        b, _ = simulate(seed=42, effect=0.3, n_csm=6)
        self.assertEqual([r["minutes"] for r in a], [r["minutes"] for r in b])

    def test_baseline_is_anchored_to_the_stated_problem(self):
        """Untreated CSM-weeks should land in the '4+ hours' neighbourhood."""
        rows, _ = simulate(seed=5, effect=0.0, n_csm=40)
        weeks = csm_week_hours(rows)
        pre = [w["hours"] for w in weeks if not w["treated"]]
        self.assertGreater(statistics.mean(pre), 3.5)
        self.assertLess(statistics.mean(pre), 7.0)

    def test_first_post_cycle_flagged_once_per_csm(self):
        rows, _ = simulate(seed=9, effect=0.3, n_csm=10)
        per_csm = {}
        for row in rows:
            per_csm[row["csm_id"]] = per_csm.get(row["csm_id"], 0) + row["is_first_post"]
        self.assertTrue(all(count == 1 for count in per_csm.values()))


# ------------------------------------------------------------------ estimator


def _reduction(rows, **kwargs):
    return analysis.run(rows, perms=0, boots=0, **kwargs)["reduction"]


class TestEstimator(unittest.TestCase):
    def test_recovers_injected_effect(self):
        """The headline claim of the package: plant 35%, get 35% back."""
        for seed in (1, 2, 3):
            rows, truth = simulate(seed=seed, effect=0.35, n_csm=60)
            got = _reduction(rows)
            self.assertAlmostEqual(got, 0.35, delta=0.03,
                                   msg=f"seed {seed}: recovered {got:.3f}")

    def test_recovers_a_large_effect(self):
        rows, _ = simulate(seed=4, effect=0.55, n_csm=60)
        self.assertAlmostEqual(_reduction(rows), 0.55, delta=0.03)

    def test_null_effect_is_not_manufactured(self):
        """No effect planted, no effect found -- point estimates hug zero."""
        estimates = [_reduction(simulate(seed=s, effect=0.0, n_csm=40)[0]) for s in range(1, 7)]
        self.assertAlmostEqual(statistics.mean(estimates), 0.0, delta=0.02)
        self.assertTrue(all(abs(e) < 0.10 for e in estimates), estimates)

    def test_null_is_rarely_rejected(self):
        """Randomisation inference must not reject a true null more than
        occasionally. Six studies at alpha = 0.05: one rejection is bad luck,
        three would mean the test is broken."""
        rejects = 0
        for seed in range(20, 26):
            rows, _ = simulate(seed=seed, effect=0.0, n_csm=15)
            result = analysis.run(rows, perms=200, boots=0, seed=seed)
            if result["p_ri"] < 0.05:
                rejects += 1
        self.assertLessEqual(rejects, 2, f"{rejects}/6 false rejections")

    def test_detects_a_real_effect(self):
        rows, _ = simulate(seed=31, effect=0.40, n_csm=15)
        result = analysis.run(rows, perms=300, boots=300, seed=31)
        self.assertLess(result["p_ri"], 0.05)
        self.assertLess(result["ci_low_reduction"], 0.40)
        self.assertGreater(result["ci_high_reduction"], 0.40)

    def test_fe_beats_naive_difference(self):
        """The design argument, asserted rather than asserted-in-prose.

        A stepped wedge confounds treatment with calendar time and with which
        CSMs crossed over first, so the obvious pre/post comparison of means is
        biased low. Run at the team size the study will actually have, over
        enough seeds that this is about bias and not one lucky draw.
        """
        naive, fe = [], []
        for seed in range(1, 13):
            rows, _ = simulate(seed=seed, effect=0.35, n_csm=15)
            treated = [math.log(r["minutes"]) for r in rows if r["treated"]]
            control = [math.log(r["minutes"]) for r in rows if not r["treated"]]
            naive.append(1.0 - math.exp(statistics.mean(treated) - statistics.mean(control)))
            fe.append(_reduction(rows))

        def mae(xs):
            return statistics.mean(abs(x - 0.35) for x in xs)

        self.assertLess(mae(fe), mae(naive) * 0.75,
                        f"FE MAE {mae(fe):.3f} vs naive {mae(naive):.3f}")
        self.assertLess(statistics.mean(naive), 0.35,
                        "the naive contrast should understate the true effect")
        self.assertAlmostEqual(statistics.mean(fe), 0.35, delta=0.02)

    def test_onboarding_cost_is_recovered_and_excluded(self):
        rows, _ = simulate(seed=6, effect=0.35, n_csm=120, learning_penalty=0.22)
        result = analysis.run(rows, perms=0, boots=0)
        # exp(0.22) = 1.246: the first cycle on the new tool costs ~25% more
        # than steady state, and the headline must not silently absorb it.
        self.assertAlmostEqual(result["onboarding"]["drag"], math.exp(0.22), delta=0.06)
        self.assertEqual(result["n_excluded"], 120)

    def test_novelty_decay_is_visible_when_present(self):
        flat, _ = simulate(seed=7, effect=0.35, n_csm=120, novelty_decay=0.0)
        fading, _ = simulate(seed=7, effect=0.35, n_csm=120, novelty_decay=0.05)
        flat_decay = analysis.run(flat, perms=0, boots=0)["decay"]
        fade_decay = analysis.run(fading, perms=0, boots=0)["decay"]
        self.assertAlmostEqual(flat_decay["weeks 1-3"]["reduction"],
                               flat_decay["weeks 7+"]["reduction"], delta=0.05)
        self.assertGreater(fade_decay["weeks 1-3"]["reduction"] - fade_decay["weeks 7+"]["reduction"],
                           0.05)

    def test_weekly_claim_tracks_the_per_cycle_effect(self):
        rows, _ = simulate(seed=11, effect=0.40, n_csm=60)
        result = analysis.run(rows, perms=0, boots=0)
        self.assertAlmostEqual(result["weekly"]["reduction"], 0.40, delta=0.06)
        self.assertLess(result["weekly"]["projected_hours"], result["weekly"]["baseline_hours"])

    def test_scope_creep_shows_up_as_a_gap_between_adjusted_and_unadjusted(self):
        """Parkinson's law check: if reports quietly get bigger under the tool,
        the unadjusted saving overstates what the tool did."""
        rows, _ = simulate(seed=12, effect=0.35, n_csm=80, scope_creep=3.0)
        plain = _reduction(rows)
        adjusted = _reduction(rows, adjust_scope=True)
        self.assertGreater(adjusted, plain + 0.01)


class TestDecisionGate(unittest.TestCase):
    """The gate must be mechanical: same numbers in, same verdict out."""

    @staticmethod
    def _result(reduction, ci_low, weekly_reduction, csat=0.0):
        return {
            "reduction": reduction,
            "ci_low_reduction": ci_low,
            "weekly": {"reduction": weekly_reduction, "baseline_hours": 4.3,
                       "projected_hours": 4.3 * (1 - weekly_reduction)},
            "guardrails": {"csat_delta": csat},
        }

    def test_ship(self):
        verdict, _ = analysis.decision(self._result(0.56, 0.41, 0.48))
        self.assertEqual(verdict, "SHIP")

    def test_iterate_when_ci_is_too_wide(self):
        verdict, reasons = analysis.decision(self._result(0.52, 0.28, 0.45))
        self.assertEqual(verdict, "ITERATE")
        self.assertTrue(any("CI lower bound" in r for r in reasons))

    def test_iterate_when_savings_are_absorbed_by_account_load(self):
        verdict, reasons = analysis.decision(self._result(0.55, 0.42, 0.12))
        self.assertEqual(verdict, "ITERATE")
        self.assertTrue(any("absorbed by account load" in r for r in reasons))

    def test_kill_on_small_effect(self):
        verdict, _ = analysis.decision(self._result(0.08, 0.01, 0.05))
        self.assertEqual(verdict, "KILL / RETHINK")

    def test_csat_breach_overrides_a_large_saving(self):
        verdict, reasons = analysis.decision(self._result(0.70, 0.60, 0.65, csat=-0.35))
        self.assertEqual(verdict, "KILL / RETHINK")
        self.assertTrue(any("CSAT" in r for r in reasons))


class TestPanelIO(unittest.TestCase):
    def test_round_trip(self):
        import tempfile

        rows, _ = simulate(seed=2, effect=0.2, n_csm=4)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "panel.csv")
            write_panel(path, rows)
            back = read_panel(path)
        self.assertEqual(len(back), len(rows))
        self.assertEqual(sorted(back[0].keys()), sorted(COLUMNS))
        self.assertEqual(back[0]["csm_id"], rows[0]["csm_id"])
        self.assertAlmostEqual(back[0]["minutes"], rows[0]["minutes"], places=6)
        self.assertIsInstance(back[0]["period"], int)


# --------------------------------------------------------------- offline eval


SNAPSHOT = {
    "metrics": {
        "citation_rate": {"value": 8.1, "unit": "%"},
        "share_of_voice": {"value": 6.4, "unit": "%"},
        "mention_rate": {"value": 22.7, "unit": "%"},
        "clicks": {"value": 3050, "unit": "count"},
        "impressions": {"value": 52600, "unit": "count"},
    },
    "aliases": {
        "citation rate": ["citation_rate"],
        "share of voice": ["share_of_voice"],
        "mention rate": ["mention_rate"],
        "clicks": ["clicks"],
        "impressions": ["impressions"],
    },
    "entities": {"client": "Acme", "brands": ["AthenaHQ"], "engines": ["ChatGPT"],
                 "urls": ["www.acme.com/features/atlas"]},
}


def _verdicts(text, snapshot=None):
    claims = offline_eval.check_numeric_claims(text, snapshot or SNAPSHOT)
    return {(c["metric"], c["verdict"]): c for c in claims}


class TestNumericChecker(unittest.TestCase):
    def test_three_metrics_one_sentence_do_not_steal_each_others_numbers(self):
        text = ("Citation rate fell to 8.1% and share of voice now stands at 6.4%, "
                "with mention rate at 22.7%.")
        claims = {c["metric"]: c for c in offline_eval.check_numeric_claims(text, SNAPSHOT)}
        self.assertEqual(claims["citation_rate"]["asserted"], 8.1)
        self.assertEqual(claims["share_of_voice"]["asserted"], 6.4)
        self.assertEqual(claims["mention_rate"]["asserted"], 22.7)
        self.assertTrue(all(c["verdict"] == "grounded" for c in claims.values()))

    def test_counts_that_precede_their_metric_still_resolve(self):
        text = "The page drew 3,050 clicks from 52,600 impressions."
        claims = {c["metric"]: c for c in offline_eval.check_numeric_claims(text, SNAPSHOT)}
        self.assertEqual(claims["clicks"]["asserted"], 3050)
        self.assertEqual(claims["impressions"]["asserted"], 52600)

    def test_claims_do_not_reach_across_a_full_stop(self):
        text = "Mention rate held at 22.7%. Share of voice is unchanged."
        claims = {c["metric"]: c for c in offline_eval.check_numeric_claims(text, SNAPSHOT)}
        self.assertEqual(claims["mention_rate"]["verdict"], "grounded")
        # No figure in its own sentence, so it is prose and not a claim.
        self.assertEqual(claims["share_of_voice"]["verdict"], "unresolvable")

    def test_level_and_delta_are_separate_claims(self):
        snapshot = {
            "metrics": {
                "citation_rate": {"value": 12.4, "unit": "%"},
                "citation_rate_delta": {"value": 2.3, "unit": "pts"},
            },
            "aliases": {"citation rate": ["citation_rate", "citation_rate_delta"]},
            "entities": {"client": "Acme", "brands": [], "engines": [], "urls": []},
        }
        text = "Citation rate reached 12.4%, up 2.3 pts on the previous period."
        claims = {c["metric"]: c for c in offline_eval.check_numeric_claims(text, snapshot)}
        self.assertEqual(claims["citation_rate"]["asserted"], 12.4)
        self.assertEqual(claims["citation_rate_delta"]["asserted"], 2.3)

    def test_a_fabricated_number_is_caught(self):
        text = "Citation rate reached 14.2% this period."
        claims = {c["metric"]: c for c in offline_eval.check_numeric_claims(text, SNAPSHOT)}
        self.assertEqual(claims["citation_rate"]["verdict"], "contradicted")

    def test_correct_rounding_is_not_a_contradiction(self):
        text = "Citation rate reached 8.1% this period."
        claims = {c["metric"]: c for c in offline_eval.check_numeric_claims(text, SNAPSHOT)}
        self.assertEqual(claims["citation_rate"]["verdict"], "grounded")


class TestEntityChecker(unittest.TestCase):
    def test_known_entities_are_not_flagged(self):
        text = "AthenaHQ leads on ChatGPT, per www.acme.com/features/atlas."
        result = offline_eval.check_entities(text, SNAPSHOT)
        self.assertEqual(result["hallucinated"], [])

    def test_brand_outside_the_clients_data_is_flagged(self):
        text = "Scrunch AI gained ground this period."
        kinds = [h["value"] for h in offline_eval.check_entities(text, SNAPSHOT)["hallucinated"]]
        self.assertIn("Scrunch AI", kinds)

    def test_invented_url_is_flagged(self):
        text = "See www.acme.com/blog/does-not-exist for detail."
        kinds = [h["kind"] for h in offline_eval.check_entities(text, SNAPSHOT)["hallucinated"]]
        self.assertIn("url", kinds)

    def test_trailing_full_stop_is_not_part_of_the_url(self):
        text = "Coverage sits on www.acme.com/features/atlas."
        self.assertEqual(offline_eval.check_entities(text, SNAPSHOT)["hallucinated"], [])


class TestBrandLints(unittest.TestCase):
    def test_clean_document_passes(self):
        text = ("Answer engine optimization (AEO) coverage improved. Citation rate is "
                "12.4%, up 2.3 pts.")
        self.assertEqual(offline_eval.brand_lints(text), [])

    def test_percentage_must_carry_one_decimal(self):
        rules = {v["rule"] for v in offline_eval.brand_lints("Citation rate is 16%.")}
        self.assertIn("percent_one_decimal", rules)
        rules = {v["rule"] for v in offline_eval.brand_lints("Citation rate is 16.44%.")}
        self.assertIn("percent_one_decimal", rules)

    def test_acronym_must_be_expanded_on_first_use(self):
        rules = {v["rule"] for v in offline_eval.brand_lints("AEO coverage improved.")}
        self.assertIn("acronym_expansion", rules)
        clean = offline_eval.brand_lints("Answer engine optimization (AEO) improved.")
        self.assertEqual(clean, [])

    def test_point_delta_needs_a_direction(self):
        rules = {v["rule"] for v in offline_eval.brand_lints("A move of 2.0 pts.")}
        self.assertIn("points_need_direction", rules)
        self.assertEqual(offline_eval.brand_lints("Up 2.0 pts."), [])
        self.assertEqual(offline_eval.brand_lints("A move of +2.0 pts."), [])

    def test_point_delta_needs_one_decimal(self):
        rules = {v["rule"] for v in offline_eval.brand_lints("Up 2 pts.")}
        self.assertIn("points_one_decimal", rules)

    def test_missing_values_render_as_an_em_dash(self):
        rules = {v["rule"] for v in offline_eval.brand_lints("Sentiment was N/A.")}
        self.assertIn("missing_as_em_dash", rules)
        self.assertEqual(offline_eval.brand_lints("Sentiment was —."), [])


class TestInsightScoring(unittest.TestCase):
    def test_hand_computed_recall_and_false_rate(self):
        item = {
            "panel_k": 2,
            "human_findings": [
                {"id": "f1", "labeler_a": "material", "labeler_b": "material"},
                {"id": "f2", "labeler_a": "material", "labeler_b": "material"},
                {"id": "f3", "labeler_a": "filler", "labeler_b": "filler"},
            ],
            "atlas_insights": [
                {"id": "i1", "rank": 1, "matched_finding": "f1", "supported": True},
                {"id": "i2", "rank": 2, "matched_finding": "f3", "supported": True},
            ],
        }
        score = offline_eval.score_insights(item)
        # Two findings both labellers called material; the panel found one.
        self.assertAlmostEqual(score["recall"], 0.5)
        # One of two panel slots went to something nobody called material.
        self.assertAlmostEqual(score["false_rate"], 0.5)

    def test_unsupported_insight_counts_against_precision(self):
        item = {
            "panel_k": 1,
            "human_findings": [{"id": "f1", "labeler_a": "material", "labeler_b": "material"}],
            "atlas_insights": [
                {"id": "i1", "rank": 1, "matched_finding": "f1", "supported": False}
            ],
        }
        score = offline_eval.score_insights(item)
        self.assertAlmostEqual(score["false_rate"], 1.0)

    def test_ranking_a_filler_item_first_costs_ndcg(self):
        good = {
            "panel_k": 2,
            "human_findings": [
                {"id": "f1", "labeler_a": "material", "labeler_b": "material"},
                {"id": "f2", "labeler_a": "filler", "labeler_b": "filler"},
            ],
            "atlas_insights": [
                {"id": "i1", "rank": 1, "matched_finding": "f1", "supported": True},
                {"id": "i2", "rank": 2, "matched_finding": "f2", "supported": True},
            ],
        }
        bad = {
            "panel_k": 2,
            "human_findings": good["human_findings"],
            "atlas_insights": [
                {"id": "i1", "rank": 1, "matched_finding": "f2", "supported": True},
                {"id": "i2", "rank": 2, "matched_finding": "f1", "supported": True},
            ],
        }
        self.assertGreater(offline_eval.score_insights(good)["ndcg"],
                           offline_eval.score_insights(bad)["ndcg"])


class TestOfflineGates(unittest.TestCase):
    def setUp(self):
        import json

        with open(os.path.join(FIXTURES, "judge_validation.json"), encoding="utf-8") as fh:
            self.validation = json.load(fh)

    def test_golden_corpus_clears_every_gate(self):
        items = offline_eval.load_set(FIXTURES, "golden")
        result = offline_eval.evaluate(items, self.validation)
        rows = offline_eval.apply_gates(result)
        failed = [r["metric"] for r in rows if r["status"] == "FAIL"]
        self.assertEqual(failed, [], f"golden corpus should clear: {failed}")

    def test_stress_set_blocks_the_rollout_on_the_planted_defects(self):
        items = offline_eval.load_set(FIXTURES, "stress")
        result = offline_eval.evaluate(items, self.validation)
        rows = {r["metric"]: r for r in offline_eval.apply_gates(result)}
        for metric in ("insight_false_rate", "numeric_grounding",
                       "entity_hallucinations", "causal_grounding",
                       "brand_lint_pass", "voice_rubric"):
            self.assertEqual(rows[metric]["status"], "FAIL", metric)

    def test_stress_defects_are_exactly_the_ones_planted(self):
        items = offline_eval.load_set(FIXTURES, "stress")
        result = offline_eval.evaluate(items, self.validation)
        self.assertEqual([c["metric"] for c in result["contradictions"]], ["citation_rate"])
        self.assertEqual(
            sorted(h["value"] for h in result["hallucination_detail"]),
            ["Scrunch AI", "www.northwind.com/blog/ai-search-2027"],
        )
        self.assertEqual(
            sorted({v["rule"] for v in result["lint_violations"]}),
            ["acronym_expansion", "missing_as_em_dash", "percent_one_decimal",
             "points_need_direction"],
        )

    def test_judge_kappa_clears_the_ship_bar(self):
        kappa = cohens_kappa(
            [p["human"] for p in self.validation["pairs"]],
            [p["judge"] for p in self.validation["pairs"]],
        )
        self.assertAlmostEqual(kappa, 0.6428571, places=5)
        self.assertGreaterEqual(kappa, offline_eval.GATES["judge_kappa"][1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
