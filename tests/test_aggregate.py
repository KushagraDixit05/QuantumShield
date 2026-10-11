import numpy as np

from fl import aggregate as ag
from fl import fixedpoint as fx


def _d(*vals):
    return np.array(vals, dtype=np.int64)


def test_fedavg_floor_mean():
    assert np.array_equal(ag.fedavg([_d(1, -1), _d(2, -2)]), _d(1, -2))


def test_median_odd_even_and_outlier():
    assert np.array_equal(ag.coord_median([_d(1), _d(2), _d(10**9)]), _d(2))
    assert np.array_equal(ag.coord_median([_d(1), _d(4)]), _d(2))


def test_norm_filter_drops_oversized_and_overflowing():
    B2 = fx.bound_sq(1.0)
    ok, big, huge = _d(fx.ONE // 2), _d(10 * fx.ONE), _d(1 << 40)
    assert ag.accepted_by_norm([ok, big, huge], B2) == [True, False, False]
    assert np.array_equal(ag.norm_filter_mean([ok, big, huge], B2), ok)
    assert np.array_equal(ag.norm_filter_mean([big], B2), _d(0))


def test_clip_mean_bounds_norm():
    B2 = fx.bound_sq(1.0)
    out = ag.clip_mean([_d(10 * fx.ONE)], B2)
    assert fx.norm_sq(out) <= B2
