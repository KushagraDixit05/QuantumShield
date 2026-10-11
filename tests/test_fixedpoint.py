import numpy as np
import pytest

from fl import fixedpoint as fx


def test_roundtrip():
    x = np.array([0.0, 1.0, -1.5, 0.25])
    assert np.allclose(fx.from_fx(fx.to_fx(x)), x)
    assert fx.to_fx(1.0) == fx.ONE


def test_mul_floor_semantics():
    a = fx.to_fx(0.5)
    assert fx.fx_mul(a, a) == fx.to_fx(0.25)
    # floor toward -inf, not toward zero
    assert fx.fx_mul(np.int64(-1), np.int64(1)) == -1
    assert fx.fx_mul(np.int64(1), np.int64(1)) == 0


def test_mul_property_matches_python_ints():
    rng = np.random.default_rng(0)
    for _ in range(200):
        a, b = (int(v) for v in rng.integers(-(1 << 24), 1 << 24, 2))
        assert int(fx.fx_mul(np.int64(a), np.int64(b))) == (a * b) >> 16


def test_overflow_detected():
    big = np.array([1 << 40], dtype=np.int64)
    with pytest.raises(fx.FixedPointOverflow):
        fx.fx_mul(big, big)
    with pytest.raises(fx.FixedPointOverflow):
        fx.norm_sq(np.array([1 << 26], dtype=np.int64))


def test_norm_sq_exact():
    d = np.array([3, -4], dtype=np.int64)
    assert fx.norm_sq(d) == 25
    assert fx.bound_sq(1.0) == 1 << 32
