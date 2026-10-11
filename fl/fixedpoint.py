"""Fixed-point integer arithmetic shared by the FL code and (later) the zkVM guest.

Value v is stored as round(v * 2^SCALE_BITS) in int64. Rescaling after a product
is an arithmetic right shift (floor toward -inf). No floats are used in the
training path; to_fx/from_fx exist for init and reporting only.
"""
import numpy as np

SCALE_BITS = 16
ONE = 1 << SCALE_BITS
LIMIT = 1 << 62  # any intermediate at or beyond this magnitude is an overflow
_NORM_ELEM_MAX = 1 << 25  # |x|^2 * ~4k elements stays below 2^62


class FixedPointOverflow(ArithmeticError):
    pass


def to_fx(x):
    return np.rint(np.asarray(x, dtype=np.float64) * ONE).astype(np.int64)


def from_fx(x):
    return np.asarray(x, dtype=np.float64) / ONE


def check(a):
    """Raise if any entry is outside the safe range."""
    a = np.asarray(a)
    if a.size and int(np.abs(a).max()) >= LIMIT:
        raise FixedPointOverflow("int64 fixed-point overflow")
    return a


def _maxabs(a):
    return int(np.abs(a).max()) if a.size else 0


def _guard(a, b, terms=1):
    """Raise before multiplying if |a|*|b|*terms could reach 2^62 (int64 would wrap silently)."""
    if _maxabs(a) * _maxabs(b) * terms >= LIMIT:
        raise FixedPointOverflow("int64 fixed-point overflow")


def fx_mul(a, b):
    """Elementwise fixed-point product."""
    a, b = np.asarray(a, dtype=np.int64), np.asarray(b, dtype=np.int64)
    _guard(a, b)
    return (a * b) >> SCALE_BITS


def matvec(W, v):
    """(m,n) @ (n,) of fixed-point values, exact int64 accumulate, one floor shift."""
    W, v = np.asarray(W, dtype=np.int64), np.asarray(v, dtype=np.int64)
    _guard(W, v, W.shape[-1])
    return (W @ v) >> SCALE_BITS


def sum_prod_shift(A, B):
    """A @ B for 2-D fixed-point arrays with one floor shift (batched gradient sums)."""
    A, B = np.asarray(A, dtype=np.int64), np.asarray(B, dtype=np.int64)
    _guard(A, B, A.shape[-1])
    return (A @ B) >> SCALE_BITS


def norm_sq(delta):
    """Exact sum of squares in units of 2^(2*SCALE_BITS). Raises on overflow risk."""
    d = np.asarray(delta, dtype=np.int64)
    if d.size and int(np.abs(d).max()) >= _NORM_ELEM_MAX:
        raise FixedPointOverflow("update entry too large for exact int64 norm")
    return int(np.dot(d, d))


def bound_sq(B):
    """Float norm bound B (real units) -> B^2 in the norm_sq unit."""
    return int(round(B * B * ONE * ONE))
