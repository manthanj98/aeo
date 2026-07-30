#!/usr/bin/env python3
"""Offline quality gates for the AI layer, run before anybody's time is measured.

Time saved is worthless if the report gets worse, and the two failure modes
are not symmetric:

  * A MISSED insight is a quality problem. The client does not learn something
    they should have.
  * A WRONG or TRIVIAL insight is a TIME problem. The CSM has to check it, and
    a CSM who re-verifies every line has saved exactly zero minutes. Precision
    is the metric that protects the four hours; recall is the one that protects
    the report.

So both are gated, and they are gated before the rollout starts rather than
inferred afterwards from a CSAT dip.

The other structural commitment here is DETERMINISTIC CHECKS BEFORE JUDGES.
Numbers in a report are extractable with a regex and comparable against the
data snapshot the report was generated from; sending arithmetic to a language
model to be graded is slower, costlier and less reliable than comparing two
floats. Only the irreducibly fuzzy parts -- is this causal claim supported, is
this on-voice -- go to a judge, and any judge that stands in for a human is
itself validated against human labels (ship only at Cohen's kappa >= 0.6).

    python3 evals/offline_eval.py
    python3 evals/offline_eval.py --set stress --json
"""

import argparse
import glob
import json
import math
import os
import re
import sys

from _stats import cohens_kappa

# --------------------------------------------------------------------- gates
# Thresholds are pre-registered in docs/eval-design.md section 4.
GATES = {
    "insight_recall": (">=", 0.70),
    "insight_false_rate": ("<=", 0.15),
    "numeric_grounding": (">=", 0.98),
    "entity_hallucinations": ("==", 0),
    "causal_grounding": (">=", 0.90),
    "brand_lint_pass": (">=", 1.00),
    "voice_rubric": (">=", 0.90),
    "judge_kappa": (">=", 0.60),
}

# Brands and engines Pepper tracks across the whole book of business. A name
# from this closed vocabulary that appears in a narrative but is absent from
# that client's own data snapshot is an unambiguous hallucination -- no
# judgement call, no false positives.
BRAND_UNIVERSE = [
    "AthenaHQ", "Profound", "Scrunch AI", "Peec AI", "airOps", "Semrush", "Ahrefs",
    "ChatGPT", "Perplexity", "Google AI Overviews", "Microsoft Co-Pilot", "Claude",
    "Gemini", "Copilot",
]

NUMBER_RE = re.compile(r"[-+−]?\d+(?:,\d{3})*(?:\.\d+)?")
PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)%")
PTS_RE = re.compile(r"([+\-−]?)(\d+(?:\.\d+)?)\s*pts\b")
URL_RE = re.compile(r"\b(?:https?://)?(?:www\.)?[a-z0-9][a-z0-9\-]*\.(?:com|ai|io|co|org|net)(?:/[\w\-./]*)?")
# Hyphens are part of the name: "Microsoft Co-Pilot" is one entity, not three.
# Two characters minimum, so the "N" of "N/A" is not read as a brand.
_WORD = r"[A-Z][a-zA-Z0-9]+(?:-[A-Z][a-zA-Z0-9]+)*"
PROPER_NOUN_RE = re.compile(r"\b" + _WORD + r"(?:\s+" + _WORD + r")*\b")
_SENTENCE_START_RE = re.compile(r"(?:^|[.!?]\s+|\n)$")

# How much closer a preceding alias effectively is than a following one when
# both compete for the same number. Tuned on the golden corpus; the failure it
# prevents is a metric stealing its neighbour's figure across a conjunction.
PRECEDING_ALIAS_BIAS = 0.6

DIRECTION_WORDS = (
    "up", "down", "rose", "fell", "gained", "lost", "increased", "decreased",
    "improved", "declined", "ahead", "behind", "added", "shed",
)

ACRONYM_EXPANSIONS = {
    "AEO": ("answer engine optimization", "answer engine optimisation"),
    "GEO": ("generative engine optimization", "generative engine optimisation"),
}

# Words that legitimately start a sentence or head a column and must not be
# mistaken for brand names by the proper-noun screen.
PROPER_NOUN_ALLOWLIST = {
    "The", "This", "That", "These", "Those", "A", "An", "In", "On", "At", "For",
    "From", "With", "Across", "Both", "Its", "It", "They", "We", "Your", "Our",
    "Share", "Voice", "Citation", "Mention", "Rate", "Impressions", "Clicks",
    "Sentiment", "Prompts", "Pages", "Keywords", "Competitors", "Insights",
    "Answer", "Engine", "Optimization", "Optimisation", "Generative", "Search",
    "Console", "Analytics", "Overviews", "Q1", "Q2", "Q3", "Q4", "June", "July",
    "May", "April", "August", "September", "October", "November", "December",
    "January", "February", "March", "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Report", "Summary", "Atlas", "Pepper",
    # Acronyms the reports legitimately use; L2 already governs their expansion.
    "AEO", "GEO", "SEO", "CTR", "GSC", "GA", "CMS", "KPI", "QBR", "SSO", "AI",
}


# --------------------------------------------------------- G1 insight quality


def score_insights(item):
    """Recall, false-insight rate and nDCG for one report cycle.

    `matched_finding` on each Atlas insight, and the two `labeler_*` votes on
    each human finding, are annotation outputs, not model outputs: two CS
    managers independently marked every claim in the historical report as
    material or filler, and a third adjudicated the match between an Atlas
    insight and a human finding. The fixtures therefore encode the state of
    the corpus AFTER labelling, which is what a scoring harness consumes.
    """
    findings = item["human_findings"]
    insights = sorted(item["atlas_insights"], key=lambda i: i["rank"])
    k = item.get("panel_k", len(insights))
    top_k = insights[:k]

    def votes(f):
        return sum(1 for key in ("labeler_a", "labeler_b") if f[key] == "material")

    # Strict definition of the recall target: both labellers agreed it mattered.
    # Anything one labeller called filler is not something we penalise Atlas
    # for missing, but it still earns partial credit in the ranking metric.
    must_find = {f["id"] for f in findings if votes(f) == 2}
    gain = {f["id"]: votes(f) for f in findings}

    matched = {i["matched_finding"] for i in top_k if i.get("matched_finding")}
    recall = len(must_find & matched) / len(must_find) if must_find else float("nan")

    # An insight earns its place only if it is supported by the data AND maps
    # to something at least one labeller judged material. Everything else costs
    # the CSM a verification they would not otherwise have done.
    useful = 0
    for i in top_k:
        fid = i.get("matched_finding")
        if i.get("supported", True) and fid and gain.get(fid, 0) >= 1:
            useful += 1
    false_rate = 1.0 - (useful / len(top_k)) if top_k else float("nan")

    dcg = 0.0
    for pos, i in enumerate(top_k, start=1):
        g = gain.get(i.get("matched_finding"), 0) if i.get("supported", True) else 0
        dcg += g / math.log2(pos + 1)
    ideal = sorted(gain.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(pos + 1) for pos, g in enumerate(ideal, start=1))
    ndcg = dcg / idcg if idcg else float("nan")

    return {
        "n_material": len(must_find),
        "n_matched": len(must_find & matched),
        "recall": recall,
        "false_rate": false_rate,
        "ndcg": ndcg,
        "k": len(top_k),
    }


# ------------------------------------------------------ G2 narrative grounding


def _find_alias_spans(text, aliases):
    """Locate metric aliases in the narrative, longest first so that
    'citation rate' wins over 'rate'."""
    lowered = text.lower()
    taken = [False] * len(text)
    spans = []
    for alias in sorted(aliases, key=len, reverse=True):
        start = 0
        needle = alias.lower()
        while True:
            idx = lowered.find(needle, start)
            if idx < 0:
                break
            end = idx + len(needle)
            if not any(taken[idx:end]):
                for p in range(idx, end):
                    taken[p] = True
                spans.append((idx, end, alias))
            start = idx + 1
    spans.sort()
    return spans


def _parse_number(token):
    return float(token.replace(",", "").replace("−", "-").lstrip("+"))


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _sentence_bounds(text, start, end):
    """The sentence containing [start, end).

    Claims do not reach across a full stop. Without this, "...mention rate held
    at 31.2%. Share of voice ... sits at 10.6%" resolves share of voice to the
    previous sentence's figure, because 31.2 is physically closer to the alias
    than 10.6 is. Sentence scoping is what makes proximity matching safe on
    real prose.
    """
    lo = 0
    hi = len(text)
    for m in _SENTENCE_SPLIT_RE.finditer(text):
        if m.end() <= start:
            lo = m.end()
        elif m.start() >= end:
            hi = m.start()
            break
    return lo, hi


def _unit_at(text, match):
    """The unit a number carries in the prose: '%', 'pts' or bare."""
    tail = text[match.end():match.end() + 6]
    if tail.startswith("%"):
        return "%"
    if tail.lstrip().startswith("pts") or tail.lstrip().startswith("points"):
        return "pts"
    return ""


def check_numeric_claims(text, snapshot, window=70):
    """Verify every number attached to a known metric against the snapshot.

    For each metric alias in the narrative, the nearest number *carrying that
    metric's unit* within a character window is taken as the asserted value and
    compared to the frozen snapshot the report was generated from. The unit
    filter is what makes this work on real prose: in "citation rate reached
    12.4%, up 2.3 pts" a nearest-number rule grabs whichever figure happens to
    sit closer, whereas the level (%) and the delta (pts) are separate claims
    and both need checking. An alias may therefore map to several metrics.

    Numbers are assigned COMPETITIVELY: each number goes to whichever alias
    claims it most strongly, so one metric cannot steal a figure that plainly
    belongs to its neighbour. "citation rate fell to 8.1% and share of voice
    now stands at 6.4%" is one sentence with two claims, and 8.1 is physically
    closer to "share of voice" than to "citation rate". The tie-break is a
    directional prior: report prose names a metric before stating its value
    ("citation rate reached 12.4%"), so distance to a preceding alias is
    discounted. Counts, which invert the order ("3,050 clicks"), still resolve
    correctly because the alias on the other side is nearer still.

    Tolerance follows the brand's own rounding rule -- one decimal place --
    plus a relative term so large counts are not held to an absolute 0.05.

    Verdicts: grounded, contradicted, or unresolvable (an alias with no number
    of the right unit nearby, which is prose rather than a claim).

    A note on where this belongs: the heuristic exists because the golden
    corpus is historical reports written by humans, which carry no provenance.
    For narrative that Atlas generates, the generator should emit each numeric
    claim tagged with the metric it came from, which turns this gate from a
    good heuristic into an exact check. That is a product recommendation, not
    an eval detail -- see docs/eval-design.md section 4.
    """
    metrics = snapshot["metrics"]
    aliases = snapshot["aliases"]
    spans = _find_alias_spans(text, aliases)

    def keys_of(alias):
        keys = aliases[alias]
        return [keys] if isinstance(keys, str) else keys

    def units_of(alias):
        out = set()
        for key in keys_of(alias):
            if key in metrics:
                unit = metrics[key].get("unit", "")
                out.add("" if unit == "count" else unit)
        return out

    # Every number in the narrative, with the unit it carries in prose.
    numbers = []
    for m in NUMBER_RE.finditer(text):
        if any(s <= m.start() and m.end() <= e for s, e, _ in spans):
            continue  # a digit inside the alias phrase itself
        numbers.append((m, _unit_at(text, m)))

    # One slot per (alias occurrence, metric). Level and delta are separate
    # slots with different units, so they cannot collide.
    slots = []
    for span in spans:
        for key in keys_of(span[2]):
            if key not in metrics:
                continue
            unit = metrics[key].get("unit", "")
            slots.append((span, key, "" if unit == "count" else unit))

    # Solve per sentence, exactly. A greedy nearest-alias rule loses on
    # "share of voice now stands at 6.4%, with mention rate at 22.7%": 6.4 is
    # closer to "mention rate" than to "share of voice", so greedy hands it
    # over and leaves share of voice with nothing -- a claim silently dropped,
    # which for a grounding gate is worse than a false alarm. Matching slots
    # and numbers one-to-one gets it right, because "mention rate" has a much
    # better candidate available in 22.7.
    assigned = {}
    sentences = {}
    for idx, (span, key, unit) in enumerate(slots):
        bounds = _sentence_bounds(text, span[0], span[1])
        sentences.setdefault(bounds, {"slots": [], "numbers": []})["slots"].append(idx)
    for bounds in sentences:
        lo, hi = bounds
        sentences[bounds]["numbers"] = [
            (m, unit) for m, unit in numbers if lo <= m.start() and m.end() <= hi
        ]

    for bounds, group in sentences.items():
        assigned.update(_match_slots_to_numbers(
            [slots[i] for i in group["slots"]], group["slots"], group["numbers"], window
        ))

    results = []
    for idx, (span, key, want_unit) in enumerate(slots):
        alias = span[2]
        match = assigned.get(idx)
        if match is None:
            results.append({"alias": alias, "metric": key, "verdict": "unresolvable"})
            continue
        asserted = _parse_number(match.group())
        expected = metrics[key]["value"]
        tolerance = max(0.05, abs(expected) * 0.005)
        verdict = "grounded" if abs(asserted - expected) <= tolerance else "contradicted"
        results.append({
            "alias": alias,
            "metric": key,
            "asserted": asserted,
            "expected": expected,
            "verdict": verdict,
        })

    return results


def _match_slots_to_numbers(slots, slot_ids, numbers, window):
    """Minimum-cost one-to-one matching of metric slots to numbers.

    Cost is the character distance from the metric name to the figure,
    discounted when the name comes first, because report prose overwhelmingly
    writes "citation rate reached 12.4%" rather than the reverse. Leaving a
    slot unmatched costs `window`, so any figure genuinely nearby beats
    silence, and a stray number (a year inside a URL, say) is simply left
    unused.

    Exact via bitmask DP. Sentences carry a handful of metrics and a handful
    of numbers, so the state space is tiny; numbers are capped defensively.
    """
    if not slots or not numbers:
        return {}
    numbers = numbers[:12]
    n = len(numbers)
    inf = float("inf")

    cost = []
    for (span, key, want_unit) in slots:
        start, end, _ = span
        row = []
        for m, unit in numbers:
            if unit != want_unit:
                row.append(inf)
                continue
            if m.start() >= end:
                distance = (m.start() - end) * PRECEDING_ALIAS_BIAS
            elif m.end() <= start:
                distance = float(start - m.end())
            else:
                distance = 0.0
            row.append(distance if distance <= window else inf)
        cost.append(row)

    skip_cost = float(window)
    memo = {}

    def best(i, mask):
        if i == len(slots):
            return 0.0, ()
        key = (i, mask)
        if key in memo:
            return memo[key]
        # Option 1: leave this slot unmatched.
        sub_cost, sub_pick = best(i + 1, mask)
        chosen = (skip_cost + sub_cost, (-1,) + sub_pick)
        # Option 2: take any unused number the units allow.
        for j in range(n):
            if mask & (1 << j) or cost[i][j] == inf:
                continue
            sub_cost, sub_pick = best(i + 1, mask | (1 << j))
            total = cost[i][j] + sub_cost
            if total < chosen[0]:
                chosen = (total, (j,) + sub_pick)
        memo[key] = chosen
        return chosen

    _, picks = best(0, 0)
    out = {}
    for slot_id, j in zip(slot_ids, picks):
        if j >= 0:
            out[slot_id] = numbers[j][0]
    return out


def check_entities(text, snapshot):
    """Zero-tolerance hallucination screen, in two tiers.

    Tier 1 is a closed-vocabulary check and is what the gate fires on: a brand
    or engine Pepper tracks that appears in this narrative but is absent from
    this client's snapshot is an unambiguous fabrication. Same for any URL not
    in the citation set.

    Tier 2 is a proper-noun screen for names outside the known universe. It has
    false positives by construction, so it is reported for human review rather
    than failing the build -- the right behaviour for a screen whose job is to
    make sure nothing invented reaches a client.
    """
    known_brands = {b.lower() for b in snapshot["entities"].get("brands", [])}
    known_brands |= {e.lower() for e in snapshot["entities"].get("engines", [])}
    known_urls = {u.lower().rstrip("/") for u in snapshot["entities"].get("urls", [])}
    client = snapshot["entities"].get("client", "")

    hallucinated = []
    for brand in BRAND_UNIVERSE:
        if re.search(r"\b" + re.escape(brand) + r"\b", text, re.IGNORECASE):
            if brand.lower() not in known_brands:
                hallucinated.append({"kind": "brand", "value": brand})

    for match in URL_RE.finditer(text):
        # A sentence-final full stop is punctuation, not part of the URL.
        url = match.group().lower().rstrip("./,;:)")
        if url.startswith("http"):
            url = url.split("://", 1)[1]
        if url not in known_urls and not any(url == k or url == k.replace("www.", "") for k in known_urls):
            hallucinated.append({"kind": "url", "value": match.group()})

    review = []
    allow = PROPER_NOUN_ALLOWLIST | {client} | {b for b in snapshot["entities"].get("brands", [])}
    allow |= set(snapshot["entities"].get("engines", []))
    universe_lower = {b.lower() for b in BRAND_UNIVERSE}
    for match in PROPER_NOUN_RE.finditer(text):
        name = match.group()
        if name in allow or name.lower() in universe_lower:
            continue
        if all(part in allow for part in name.split()):
            continue
        # A single capitalised word opening a sentence is just a capital
        # letter, not a claim about an entity.
        if " " not in name and _SENTENCE_START_RE.search(text[:match.start()]):
            continue
        review.append(name)

    return {"hallucinated": hallucinated, "needs_review": sorted(set(review))}


# ------------------------------------------------------- G3 brand compliance


def brand_lints(text):
    """Machine-checkable rules taken straight from the Brand Guidelines surface.

    The prototype already stores these as first-class product state ("Round
    percentages to one decimal place in customer-facing reports", "Always spell
    out acronyms (AEO, GEO) on first use"). Rules a product stores as data are
    rules a linter can enforce, which is why the gate here is 100% and not a
    judged score -- there is nothing to judge.
    """
    violations = []

    # L1 -- percentages carry exactly one decimal place.
    for m in PERCENT_RE.finditer(text):
        digits = m.group(1).split(".")
        if len(digits) != 2 or len(digits[1]) != 1:
            violations.append({"rule": "percent_one_decimal", "found": m.group()})

    # L2 -- AEO/GEO expanded on first use.
    lowered = text.lower()
    for acronym, expansions in ACRONYM_EXPANSIONS.items():
        first = re.search(r"\b" + acronym + r"\b", text)
        if not first:
            continue
        positions = [lowered.find(e) for e in expansions]
        positions = [p for p in positions if p >= 0]
        if not positions or min(positions) > first.start():
            violations.append({"rule": "acronym_expansion", "found": acronym})

    # L3 -- point deltas carry one decimal (the prototype's signed1() helper
    # produces exactly that) and state a direction, either as an explicit sign
    # or as a direction word immediately before. "+2.3 pts" and "up 2.3 pts"
    # both read correctly; a bare "2.3 pts" leaves the reader guessing.
    for m in PTS_RE.finditer(text):
        sign, number = m.group(1), m.group(2)
        if "." not in number or len(number.split(".")[1]) != 1:
            violations.append({"rule": "points_one_decimal", "found": m.group()})
            continue
        prefix = text[max(0, m.start() - 14):m.start()].lower()
        directed = bool(sign) or any(word in prefix for word in DIRECTION_WORDS)
        if not directed:
            violations.append({"rule": "points_need_direction", "found": m.group()})

    # L4 -- unknown values render as an em dash, never as a placeholder string.
    for m in re.finditer(r"\b(N/A|n/a|NA|null|None|undefined|TBD)\b", text):
        violations.append({"rule": "missing_as_em_dash", "found": m.group()})

    return violations


# ------------------------------------------------------------------ harness


def load_set(fixtures_dir, name):
    pattern = os.path.join(fixtures_dir, name, "*.json")
    paths = sorted(glob.glob(pattern))
    if not paths:
        raise SystemExit(f"no fixtures found at {pattern}")
    items = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        # One file per report cycle is the shape the real corpus takes; the
        # bundled sample packs several per file to stay readable.
        batch = payload if isinstance(payload, list) else [payload]
        for item in batch:
            item["_path"] = path
            items.append(item)
    return items


def evaluate(items, judge_validation=None):
    insight_recalls = []
    insight_false = []
    ndcgs = []
    numeric_total = numeric_ok = 0
    contradictions = []
    hallucinations = []
    needs_review = []
    lint_docs_clean = 0
    lint_violations = []
    causal_total = causal_ok = 0
    voice_scores = []

    for item in items:
        ins = score_insights(item)
        if ins["recall"] == ins["recall"]:
            insight_recalls.append(ins["recall"])
        if ins["false_rate"] == ins["false_rate"]:
            insight_false.append(ins["false_rate"])
        if ins["ndcg"] == ins["ndcg"]:
            ndcgs.append(ins["ndcg"])

        text = item["narrative"]
        claims = check_numeric_claims(text, item["snapshot"])
        for claim in claims:
            if claim["verdict"] == "unresolvable":
                continue
            numeric_total += 1
            if claim["verdict"] == "grounded":
                numeric_ok += 1
            else:
                contradictions.append({"cycle": item["cycle_id"], **claim})

        entities = check_entities(text, item["snapshot"])
        for h in entities["hallucinated"]:
            hallucinations.append({"cycle": item["cycle_id"], **h})
        needs_review.extend(entities["needs_review"])

        violations = brand_lints(text)
        if violations:
            lint_violations.extend({"cycle": item["cycle_id"], **v} for v in violations)
        else:
            lint_docs_clean += 1

        # Judged components. These are the recorded verdicts of the validated
        # judge; the harness scores them, it does not produce them.
        judged = item.get("judged", {})
        for claim in judged.get("causal_claims", []):
            causal_total += 1
            if claim.get("supported"):
                causal_ok += 1
        if "voice_score" in judged:
            voice_scores.append(judged["voice_score"])

    kappa = float("nan")
    if judge_validation:
        kappa = cohens_kappa(
            [p["human"] for p in judge_validation["pairs"]],
            [p["judge"] for p in judge_validation["pairs"]],
        )

    def avg(xs):
        return sum(xs) / len(xs) if xs else float("nan")

    return {
        "n_items": len(items),
        "insight_recall": avg(insight_recalls),
        "insight_false_rate": avg(insight_false),
        "insight_ndcg": avg(ndcgs),
        "numeric_grounding": (numeric_ok / numeric_total) if numeric_total else float("nan"),
        "numeric_claims": numeric_total,
        "contradictions": contradictions,
        "entity_hallucinations": len(hallucinations),
        "hallucination_detail": hallucinations,
        "needs_review": sorted(set(needs_review)),
        "brand_lint_pass": lint_docs_clean / len(items) if items else float("nan"),
        "lint_violations": lint_violations,
        "causal_grounding": (causal_ok / causal_total) if causal_total else float("nan"),
        "causal_claims": causal_total,
        "voice_rubric": avg(voice_scores),
        "judge_kappa": kappa,
    }


def apply_gates(result):
    """Compare every gated metric to its pre-registered threshold."""
    rows = []
    for metric, (op, threshold) in GATES.items():
        value = result.get(metric, float("nan"))
        if value != value:
            status = "SKIP"
        elif op == ">=":
            status = "PASS" if value >= threshold else "FAIL"
        elif op == "<=":
            status = "PASS" if value <= threshold else "FAIL"
        else:
            status = "PASS" if value == threshold else "FAIL"
        rows.append({"metric": metric, "value": value, "op": op, "threshold": threshold, "status": status})
    return rows


def _fmt(metric, value):
    if value != value:
        return "n/a"
    if metric == "entity_hallucinations":
        return f"{int(value)}"
    return f"{value:.3f}"


def report(result, gate_rows, label):
    lines = []
    add = lines.append
    add("=" * 74)
    add(f"OFFLINE QUALITY GATES   set '{label}', {result['n_items']} report cycles")
    add("=" * 74)
    add("")
    add("G1  insight quality        (does the panel surface what a CSM would have)")
    add(f"  recall of material findings   {_fmt('r', result['insight_recall'])}"
        f"    <- protects the report")
    add(f"  false / trivial insight rate  {_fmt('r', result['insight_false_rate'])}"
        f"    <- protects the four hours")
    add(f"  nDCG                          {_fmt('r', result['insight_ndcg'])}    reported, not gated")
    add("")
    add("G2  narrative grounding    (deterministic first, judge only where needed)")
    add(f"  numeric claims checked        {result['numeric_claims']}")
    add(f"  grounded against snapshot     {_fmt('r', result['numeric_grounding'])}")
    add(f"  entity hallucinations         {result['entity_hallucinations']}    closed-vocabulary, zero tolerance")
    add(f"  causal claims (judged)        {_fmt('r', result['causal_grounding'])}    n = {result['causal_claims']}")
    if result["needs_review"]:
        add(f"  proper nouns for review       {', '.join(result['needs_review'][:6])}")
    add("")
    add("G3  brand compliance")
    add(f"  documents passing all lints   {_fmt('r', result['brand_lint_pass'])}")
    add(f"  voice rubric (judged)         {_fmt('r', result['voice_rubric'])}")
    add("")
    add(f"JUDGE VALIDATION   Cohen's kappa vs human labels   {_fmt('r', result['judge_kappa'])}")
    add("")

    if result["contradictions"]:
        add("CONTRADICTED NUMBERS")
        for c in result["contradictions"]:
            add(f"  {c['cycle']}  {c['metric']}: narrative says {c['asserted']}, snapshot has {c['expected']}")
        add("")
    if result["hallucination_detail"]:
        add("HALLUCINATED ENTITIES")
        for h in result["hallucination_detail"]:
            add(f"  {h['cycle']}  {h['kind']}: {h['value']}")
        add("")
    if result["lint_violations"]:
        add("BRAND LINT VIOLATIONS")
        for v in result["lint_violations"]:
            add(f"  {v['cycle']}  {v['rule']}: {v['found']!r}")
        add("")

    add("-" * 74)
    add(f"  {'metric':<26}{'value':>10}{'':>4}{'threshold':>12}   status")
    add("-" * 74)
    for row in gate_rows:
        bar = f"{row['op']} {row['threshold']}"
        add(f"  {row['metric']:<26}{_fmt(row['metric'], row['value']):>10}{'':>4}{bar:>12}   {row['status']}")
    add("-" * 74)

    failed = [r for r in gate_rows if r["status"] == "FAIL"]
    verdict = "BLOCKED -- do not start the online experiment" if failed else "CLEARED for the online experiment"
    add(f"VERDICT: {verdict}")
    if failed:
        for row in failed:
            add(f"  - {row['metric']} = {_fmt(row['metric'], row['value'])}, needs {row['op']} {row['threshold']}")
    add("=" * 74)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_fixtures = os.path.join(os.path.dirname(__file__), "fixtures")
    parser.add_argument("--fixtures", default=default_fixtures)
    parser.add_argument("--set", dest="set_name", default="golden",
                        choices=["golden", "stress"],
                        help="golden = D2 corpus of real delivered reports; "
                             "stress = D3 edge cases, run on every model change")
    parser.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = parser.parse_args()

    items = load_set(args.fixtures, args.set_name)
    validation_path = os.path.join(args.fixtures, "judge_validation.json")
    judge_validation = None
    if os.path.exists(validation_path):
        with open(validation_path, encoding="utf-8") as fh:
            judge_validation = json.load(fh)

    result = evaluate(items, judge_validation)
    gate_rows = apply_gates(result)

    if args.json:
        print(json.dumps({"result": result, "gates": gate_rows}, indent=2, default=str))
    else:
        print(report(result, gate_rows, args.set_name))

    return 1 if any(r["status"] == "FAIL" for r in gate_rows) else 0


if __name__ == "__main__":
    sys.exit(main())
