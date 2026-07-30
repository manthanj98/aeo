"""Distribution functions needed for the pre-registered tests, stdlib only.

Only two things are needed: a two-sided Student-t p-value (for the
cluster-robust Wald test, on G-1 degrees of freedom) and Cohen's kappa (for
validating an LLM judge against human labels). Both are implemented here so
the package has no install step.
"""

import math

_MAXIT = 300
_EPS = 3e-16
_FPMIN = 1e-300


def _betacf(a, b, x):
    """Continued fraction for the incomplete beta function (modified Lentz)."""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _FPMIN:
        d = _FPMIN
    d = 1.0 / d
    h = d

    for m in range(1, _MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break

    return h


def betainc(a, b, x):
    """Regularised incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    if x < (a + 1.0) / (a + b + 2.0):
        front = math.exp(log_beta + a * math.log(x) + b * math.log1p(-x))
        return front * _betacf(a, b, x) / a
    front = math.exp(log_beta + b * math.log1p(-x) + a * math.log(x))
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t, df):
    """Two-sided p-value for a Student-t statistic on `df` degrees of freedom."""
    if df <= 0:
        return float("nan")
    if not math.isfinite(t):
        return 0.0 if abs(t) == float("inf") else float("nan")
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def t_critical(df, alpha=0.05):
    """Two-sided critical t value, found by bisection on t_two_sided_p."""
    lo, hi = 0.0, 200.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_two_sided_p(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def cohens_kappa(labels_a, labels_b):
    """Cohen's kappa for two raters over a shared set of nominal labels.

    Used to decide whether an LLM judge may stand in for a human labeller
    (ship only at kappa >= 0.6) and to report agreement between the two CS
    managers labelling the golden corpus. With more than two raters or with
    missing labels, Krippendorff's alpha generalises this; two complete raters
    is the case we actually have.
    """
    if len(labels_a) != len(labels_b):
        raise ValueError("rater label vectors must be the same length")
    n = len(labels_a)
    if n == 0:
        raise ValueError("cohens_kappa() of empty sequence")

    categories = sorted(set(labels_a) | set(labels_b))
    observed = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n

    expected = 0.0
    for cat in categories:
        p_a = sum(1 for a in labels_a if a == cat) / n
        p_b = sum(1 for b in labels_b if b == cat) / n
        expected += p_a * p_b

    if abs(1.0 - expected) < 1e-12:
        # Both raters used a single category throughout; kappa is undefined,
        # and reporting 1.0 here would hide a degenerate label set.
        return float("nan")
    return (observed - expected) / (1.0 - expected)
