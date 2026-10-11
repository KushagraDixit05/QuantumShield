import json

import pytest

from demo import plot as P


def _res():
    return {"scenarios": {"A": [0.1, 0.5, 0.9], "B": [0.1, 0.3, 0.0], "C": [0.1, 0.6, 0.9]}}


def test_accuracy_figure(tmp_path):
    out = tmp_path / "a.png"
    P.plot(_res(), out)
    assert out.stat().st_size > 1000


def test_accuracy_bad_input(tmp_path):
    with pytest.raises(ValueError):
        P.plot({"scenarios": {}}, tmp_path / "x.png")
    with pytest.raises(ValueError):
        P.plot({"scenarios": {"A": []}}, tmp_path / "x.png")


def _csv(path, rows):
    path.write_text("attack,defence,seed,final_acc\n" + "".join(f"{a},{d},{s},{v}\n" for a, d, s, v in rows))


def test_matrix_figure(tmp_path):
    c = tmp_path / "s.csv"
    _csv(c, [(a, d, s, 0.9 - 0.01 * s) for a in P.ATTACKS for d in P.DEFENCES for s in range(5)])
    out = tmp_path / "m.png"
    P.plot_matrix(c, out)
    assert out.stat().st_size > 1000


def test_matrix_bad_input(tmp_path):
    c = tmp_path / "bad.csv"
    c.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        P.plot_matrix(c, tmp_path / "m.png")
    e = tmp_path / "empty.csv"
    _csv(e, [])
    with pytest.raises(ValueError):
        P.plot_matrix(e, tmp_path / "m.png")
    with pytest.raises(FileNotFoundError):
        P.plot_matrix(tmp_path / "nope.csv", tmp_path / "m.png")


def test_cli(tmp_path, monkeypatch):
    j = tmp_path / "r.json"
    j.write_text(json.dumps(_res()))
    monkeypatch.setattr("sys.argv", ["plot", str(j), str(tmp_path / "o.png")])
    P.main()
    assert (tmp_path / "o.png").exists()
