from bench.stats import compute


def _rows(mode, costs_by_task):
    return [{"mode": mode, "task": t, "cost_usd": c} for t, cs in costs_by_task.items() for c in cs]


def test_compute_delta_and_ci():
    rows = _rows("mcp", {"a": [1.0, 1.0, 1.0], "b": [3.0, 3.0, 3.0]}) + \
           _rows("code", {"a": [0.5, 0.5, 0.5], "b": [1.5, 1.5, 1.5]})
    out = {d["mode"]: d for d in compute(rows, "mcp", "cost_usd", iters=200)}
    assert out["mcp"]["mean"] == 2.0
    assert out["code"]["delta"] == -0.5
    assert out["code"]["delta_ci"] == (-0.5, -0.5)  # no spread within tasks -> zero-width CI
    assert out["code"]["tasks_better"] == 2 and out["code"]["n_tasks"] == 2


def test_tasks_weighted_equally():
    rows = _rows("mcp", {"a": [1.0], "b": [3.0, 3.0, 3.0, 3.0]})
    (d,) = compute(rows, "mcp", "cost_usd", iters=50)
    assert d["mean"] == 2.0  # mean of task means, not of all runs (2.6)
