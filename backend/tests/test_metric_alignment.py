"""回归测试：mean_quality 与 n_rate 在任何一层都不得互换。

刻意使用差异悬殊的两值（39.75 vs 0.25），任何一处写反都会立刻断言失败。
覆盖：流水线产物 → 落库 → 读出 → API 列表/详情（含 summary、report 子对象）。
"""

from __future__ import annotations

import importlib.util

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import Job, JobStage
from app.pipeline.actors import ACTOR_CHAIN
from app.pipeline.runner import run_pipeline_sync


# 16 个碱基：质量 I(40)×12 + H(39)×4 → 平均 39.75；4 个 N → n_rate 0.25
FASTQ = """@SEQ1
ACGTACGT
+
IIIIHHHH
@SEQ2
NNNNACGT
+
IIIIIIII
"""

MEAN_QUALITY = 39.75
N_RATE = 0.25


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _make_job(db, status="success", metrics=None) -> Job:
    job = Job(
        sample_name="自定义输入",
        status=status,
        created_by="bioops",
        fastq_snapshot=FASTQ,
        metrics=metrics,
    )
    db.add(job)
    db.commit()
    for order, cls in enumerate(ACTOR_CHAIN):
        db.add(JobStage(job_id=job.id, actor_name=cls.name, stage_order=order))
    db.commit()
    return job


def test_swap_modules_removed():
    assert importlib.util.find_spec("app.MetricFieldSwap") is None
    assert importlib.util.find_spec("app.MetricSwapReadPath") is None


def test_pipeline_metrics_keep_distinct_values():
    import asyncio

    from app.pipeline.runner import _run_chain

    ok, ctx, _ = asyncio.run(_run_chain(FASTQ))
    assert ok is True
    m = ctx.metrics
    assert m["mean_quality"] == MEAN_QUALITY
    assert m["n_rate"] == N_RATE
    assert m["summary"]["mean_quality"] == m["mean_quality"]
    assert m["summary"]["n_rate"] == m["n_rate"]
    assert m["report"]["mean_quality"] == m["mean_quality"]
    assert m["report"]["n_rate"] == m["n_rate"]


def test_persisted_metrics_not_swapped(db_session):
    job = _make_job(db_session, status="pending")
    run_pipeline_sync(db_session, job)

    # 从全新的身份映射读回，确保断言的是数据库里的 JSON，而非内存对象
    db_session.expire_all()
    stored = db_session.get(Job, job.id)
    m = stored.metrics
    assert m["mean_quality"] == MEAN_QUALITY
    assert m["n_rate"] == N_RATE
    assert m["summary"]["mean_quality"] == MEAN_QUALITY
    assert m["summary"]["n_rate"] == N_RATE
    assert m["report"]["mean_quality"] == MEAN_QUALITY
    assert m["report"]["n_rate"] == N_RATE


def test_api_list_and_detail_not_swapped(db_session):
    _make_job(
        db_session,
        metrics={
            "reads": 2,
            "mean_quality": MEAN_QUALITY,
            "n_rate": N_RATE,
            "summary": {"mean_quality": MEAN_QUALITY, "n_rate": N_RATE},
            "report": {"mean_quality": MEAN_QUALITY, "n_rate": N_RATE},
        },
    )

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "auditor",
        "role": "auditor",
    }
    try:
        client = TestClient(app)

        row = client.get("/api/jobs").json()[0]
        assert row["metrics"]["mean_quality"] == MEAN_QUALITY
        assert row["metrics"]["n_rate"] == N_RATE

        detail = client.get(f"/api/jobs/{row['id']}").json()
        m = detail["metrics"]
        assert m["mean_quality"] == MEAN_QUALITY
        assert m["n_rate"] == N_RATE
        assert m["summary"]["mean_quality"] == MEAN_QUALITY
        assert m["summary"]["n_rate"] == N_RATE
        assert m["report"]["mean_quality"] == MEAN_QUALITY
        assert m["report"]["n_rate"] == N_RATE
    finally:
        app.dependency_overrides.clear()
