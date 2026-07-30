"""The report-cycle panel: the one data structure the online experiment analyses.

A row is one *report cycle* — a single client report produced by a single CSM
in a single period. That is the unit the product acts on, so it is the unit we
randomise against and estimate on. The business claim ("4 hours a week") lives
at the CSM-week level and is derived from these rows in analysis.py.

Column reference
----------------
cycle_id        Stable id for the cycle.
csm_id          Cluster / randomisation unit. Treatment is assigned to people,
                not accounts, because a CSM cannot be half-treated.
account_id      Client account the report is for.
tier            Account tier (enterprise / growth / starter). Stratifier.
cadence         weekly / biweekly / monthly. Drives how many cycles a CSM owns.
period          Stepped-wedge step index, 0-based. Also the calendar-time
                fixed effect: every CSM shares the same period at the same time.
week            Calendar week index within the study.
start_step      The period at which this CSM crosses over to Atlas. This is the
                randomised quantity, and permuting it across CSMs is what makes
                randomisation inference valid.
treated         1 if period >= start_step.
weeks_treated   Weeks since crossover, for the novelty-decay analysis.
cycle_seq       0-based index of this cycle within the CSM's own sequence.
                Controls for a CSM simply getting faster over the study.
is_first_post   1 for a CSM's first cycle after crossover. Pre-registered as
                excluded from the primary estimate and reported separately as
                onboarding cost.
minutes         PRIMARY OUTCOME. Calibrated active minutes spent building this
                report cycle (S1 telemetry + S2 work-surface metadata, scaled
                by the S3/D1 calibration factor). Analysed on the log scale.
scope_charts    Report scope proxy (charts + custom cuts). Covariate for the
                Parkinson / scope-creep threat: a report that quietly grows
                will eat the saving, and we want to see that separately.
on_time         1 if delivered on or before the committed date. Guardrail.
csat            Per-cycle client satisfaction, 1-5. Guardrail.
"""

import csv

COLUMNS = [
    "cycle_id",
    "csm_id",
    "account_id",
    "tier",
    "cadence",
    "period",
    "week",
    "start_step",
    "treated",
    "weeks_treated",
    "cycle_seq",
    "is_first_post",
    "minutes",
    "scope_charts",
    "on_time",
    "csat",
]

_INT_COLUMNS = {
    "period",
    "week",
    "start_step",
    "treated",
    "weeks_treated",
    "cycle_seq",
    "is_first_post",
    "scope_charts",
    "on_time",
}
_FLOAT_COLUMNS = {"minutes", "csat"}


def write_panel(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in COLUMNS})


def read_panel(path):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = []
        for raw in csv.DictReader(fh):
            row = dict(raw)
            for key in _INT_COLUMNS:
                row[key] = int(row[key])
            for key in _FLOAT_COLUMNS:
                row[key] = float(row[key])
            rows.append(row)
    return rows


def csm_week_hours(rows):
    """Collapse cycles to the business claim: reporting hours per CSM-week.

    The per-cycle effect and the per-week effect can disagree — a CSM whose
    per-cycle time halves but whose account load doubles has saved nobody any
    hours. Both numbers get reported, and only this one answers the original
    "4+ hours a week" question.
    """
    totals = {}
    for row in rows:
        key = (row["csm_id"], row["week"])
        bucket = totals.setdefault(
            key,
            {
                "csm_id": row["csm_id"],
                "week": row["week"],
                "period": row["period"],
                "treated": row["treated"],
                "minutes": 0.0,
                "cycles": 0,
            },
        )
        bucket["minutes"] += row["minutes"]
        bucket["cycles"] += 1
        # A week counts as treated if the CSM had crossed over by then. Every
        # cycle in a given CSM-week shares the same period, so this is exact.
        bucket["treated"] = max(bucket["treated"], row["treated"])

    out = []
    for bucket in totals.values():
        bucket["hours"] = bucket["minutes"] / 60.0
        out.append(bucket)
    out.sort(key=lambda b: (b["csm_id"], b["week"]))
    return out
