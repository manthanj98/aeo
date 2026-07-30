"""Minimal dense linear algebra, standard library only.

The whole evals package deliberately avoids numpy/scipy/statsmodels so it runs
on any Python 3.9+ with no install step. Everything here operates on plain
lists of lists; the matrices involved are tiny (K is roughly 20-30 columns:
an intercept, CSM dummies, period dummies and a couple of controls), so the
naive O(K^3) routines below are not a bottleneck. The row count is where the
work is, and that is handled with sparse row representations in analysis.py.
"""


class SingularMatrixError(Exception):
    """Raised when a design matrix has no unique solution.

    In practice this means a bootstrap resample or a filtered subsample lost
    all variation in some column (e.g. every retained cycle is untreated).
    Callers are expected to catch this and skip the replicate rather than
    crash the run.
    """


def solve(a, b):
    """Solve a @ x = b for x by Gauss-Jordan elimination with partial pivoting.

    `a` is a square list of lists and is not mutated.
    """
    n = len(a)
    if any(len(row) != n for row in a):
        raise ValueError("solve() expects a square matrix")
    if len(b) != n:
        raise ValueError("dimension mismatch between matrix and vector")

    # Work on an augmented copy so the caller's matrix survives intact.
    m = [list(a[i]) + [b[i]] for i in range(n)]

    for col in range(n):
        pivot_row = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot_row][col]) < 1e-12:
            raise SingularMatrixError(f"column {col} is numerically singular")
        m[col], m[pivot_row] = m[pivot_row], m[col]

        pivot = m[col][col]
        row = m[col]
        for j in range(col, n + 1):
            row[j] /= pivot

        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            if factor == 0.0:
                continue
            target = m[r]
            for j in range(col, n + 1):
                target[j] -= factor * row[j]

    return [m[i][n] for i in range(n)]


def inverse(a):
    """Return the inverse of a square matrix via Gauss-Jordan elimination."""
    n = len(a)
    m = [list(a[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    for col in range(n):
        pivot_row = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot_row][col]) < 1e-12:
            raise SingularMatrixError(f"column {col} is numerically singular")
        m[col], m[pivot_row] = m[pivot_row], m[col]

        pivot = m[col][col]
        row = m[col]
        for j in range(col, 2 * n):
            row[j] /= pivot

        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            if factor == 0.0:
                continue
            target = m[r]
            for j in range(col, 2 * n):
                target[j] -= factor * row[j]

    return [row[n:] for row in m]


def mean(xs):
    xs = list(xs)
    if not xs:
        raise ValueError("mean() of empty sequence")
    return sum(xs) / len(xs)


def quantile(xs, q):
    """Linear-interpolation quantile, matching the usual 'type 7' definition."""
    ordered = sorted(xs)
    if not ordered:
        raise ValueError("quantile() of empty sequence")
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac
