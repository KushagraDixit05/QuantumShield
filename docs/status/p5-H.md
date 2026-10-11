# p5-H status

Done:
- demo/plot.py: `plot()` (accuracy.png, seed 0, round 0 = initial model, B divergence annotated as D-012 convention), `plot_matrix()` (attack_matrix.png from scenarios.csv, mean +- std over 5 seeds, 359-sample caveat in caption). `python -m demo.plot` (no args) writes both; `python -m demo.plot [json] [png]` still writes accuracy only.
- tests/test_demo_plot.py: 5 tests, all pass (`.venv/bin/python -m pytest tests/test_demo_plot.py -q` -> 5 passed).
- Outputs: demo/results/accuracy.png, demo/results/attack_matrix.png (visually checked).

Blocked: none. Needs: nothing.
Note: x-axis is 0-based (scenarios.json has rounds+1 points, index 0 = initial model); the old plot used 1-based x.
