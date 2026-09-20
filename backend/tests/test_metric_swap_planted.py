from app.MetricFieldSwap import swap_metrics


def test_swap():
    out = swap_metrics({"mean_quality": 30.0, "n_rate": 0.01, "reads": 2})
    assert out["mean_quality"] == 0.01
    assert out["n_rate"] == 30.0
