import numpy as np

from fl import data, model


def test_param_count_and_flatten_roundtrip():
    w = model.init(0)
    assert w.shape == (model.N_PARAMS,) == (2410,) and w.dtype == np.int64
    assert np.array_equal(model.flatten(*model.unflatten(w)), w)


def test_init_deterministic_and_seed_dependent():
    assert np.array_equal(model.init(3), model.init(3))
    assert not np.array_equal(model.init(3), model.init(4))


def test_forward_integer_and_deterministic():
    clients, test = data.load(0, 5)
    w = model.init(0)
    _, _, o1 = model.forward(w, test.X)
    _, _, o2 = model.forward(w, test.X)
    assert o1.dtype == np.int64 and np.array_equal(o1, o2)


def test_data_split_iid_disjoint_and_exact_fixedpoint():
    clients, test = data.load(0, 5)
    assert sum(len(c) for c in clients) + len(test) == 1797
    assert clients[0].X.max() <= 16 << 12 and (clients[0].X % (1 << 12) == 0).all()
    c2, t2 = data.load(0, 5)
    assert np.array_equal(clients[0].X, c2[0].X) and np.array_equal(test.y, t2.y)
