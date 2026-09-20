"""BUG: swap mean_quality and n_rate on write and read."""
from __future__ import annotations

SWAP_ON_WRITE = True
SWAP_ON_READ = True


def swap_metrics(metrics: dict | None) -> dict | None:
    if not metrics:
        return metrics
    out = dict(metrics)
    mq, nr = out.get("mean_quality"), out.get("n_rate")
    out["mean_quality"], out["n_rate"] = nr, mq
    if isinstance(out.get("summary"), dict):
        s = dict(out["summary"])
        s["mean_quality"], s["n_rate"] = s.get("n_rate"), s.get("mean_quality")
        out["summary"] = s
    if isinstance(out.get("report"), dict):
        r = dict(out["report"])
        r["mean_quality"], r["n_rate"] = r.get("n_rate"), r.get("mean_quality")
        out["report"] = r
    return out


def swap_job_metrics_inplace(job) -> None:
    if job is not None and getattr(job, "metrics", None):
        job.metrics = swap_metrics(job.metrics)
