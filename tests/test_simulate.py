import re
import subprocess
import sys
from pathlib import Path

from fl.simulate import load_cfg, run

ROOT = Path(__file__).resolve().parent.parent
CFG = load_cfg("configs/mvp.yaml")


def test_benign_fedavg_accuracy_at_least_90():
    acc = run(CFG, "none", "fedavg", 0)
    assert len(acc) == CFG["rounds"] + 1 and acc[-1] >= 0.90 and acc[-1] > acc[0]


def test_same_seed_identical_and_different_seed_differs():
    assert run(CFG, "label_flip", "median", 2) == run(CFG, "label_flip", "median", 2)
    assert run(CFG, "none", "fedavg", 0) != run(CFG, "none", "fedavg", 1)


def test_cli_reproducible(tmp_path):
    outs = []
    for i in range(2):
        out = tmp_path / f"o{i}.csv"
        subprocess.run([sys.executable, "-m", "fl.simulate", "--attack", "scaled", "--defence", "norm_filter",
                        "--seed", "1", "--out", str(out)], cwd=ROOT, check=True, capture_output=True)
        outs.append(out.read_text())
    assert outs[0] == outs[1] and outs[0].count("\n") == CFG["rounds"] + 2


def test_no_zkvm_dev_mode_in_repo():
    bad = []
    for p in list(ROOT.glob("**/*.py")) + list(ROOT.glob("**/*.rs")) + list(ROOT.glob("**/*.sh")) + [ROOT / "Makefile"]:
        if ".venv" in p.parts or "target" in p.parts or p.name == "test_simulate.py":
            continue
        # Phase 3: the host may mention the variable to refuse it, and tests/zk may use labelled dev-mode
        # tests; nothing else may enable it (docs/zk_interface.md section 10).
        if "tests" in p.parts and "zk" in p.parts:
            continue
        txt = p.read_text(errors="ignore")
        if re.search(r"RISC0_DEV_MODE\s*=\s*['\"]?(1|true)|set_var\(\s*\"RISC0_DEV_MODE|DevMode|dev_mode\(\s*true", txt):
            bad.append(str(p))
    assert not bad, bad
