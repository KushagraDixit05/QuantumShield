import numpy as np

from fl import client, data, model


def _setup():
    clients, _ = data.load(0, 5)
    return model.init(0), clients[0]


def test_sample_indices_reproducible_and_in_range():
    a = client.sample_indices(0, 1, 2, 4, 8, 288)
    assert np.array_equal(a, client.sample_indices(0, 1, 2, 4, 8, 288))
    assert a.min() >= 0 and a.max() < 288
    for args in [(1, 1, 2), (0, 2, 2), (0, 1, 3)]:
        assert not np.array_equal(a, client.sample_indices(*args, 4, 8, 288))


def test_sample_index_known_answer():
    import hashlib
    h = hashlib.sha256(b"QSFL-idx" + (7).to_bytes(8, "little") + b"".join(v.to_bytes(4, "little") for v in (2, 3, 1, 0))).digest()
    assert client.sample_indices(7, 2, 3, 2, 1, 1000)[1, 0] == int.from_bytes(h[:8], "little") % 1000


def test_local_train_deterministic_and_nonzero():
    w, ds = _setup()
    idx = client.sample_indices(0, 0, 0, 5, 32, len(ds))
    d1 = client.local_train(w, ds, idx, 19661)
    assert np.array_equal(d1, client.local_train(w, ds, idx, 19661))
    assert d1.shape == w.shape and d1.dtype == np.int64 and np.abs(d1).sum() > 0


def test_different_sampling_seed_changes_update():
    w, ds = _setup()
    i1 = client.sample_indices(0, 0, 0, 5, 32, len(ds))
    i2 = client.sample_indices(1, 0, 0, 5, 32, len(ds))
    assert not np.array_equal(client.local_train(w, ds, i1, 19661), client.local_train(w, ds, i2, 19661))


def test_training_improves_accuracy():
    w, ds = _setup()
    _, test = data.load(0, 5)
    idx = client.sample_indices(0, 0, 0, 100, 32, len(ds))
    d = client.local_train(w, ds, idx, 19661)
    assert model.accuracy(w + d, test) > model.accuracy(w, test) + 0.3
