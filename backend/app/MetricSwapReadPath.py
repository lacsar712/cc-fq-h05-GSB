from app.MetricFieldSwap import swap_job_metrics_inplace, swap_metrics


def prepare_job_out(job):
    swap_job_metrics_inplace(job)
    return job


def prepare_blob(metrics):
    return swap_metrics(metrics)
