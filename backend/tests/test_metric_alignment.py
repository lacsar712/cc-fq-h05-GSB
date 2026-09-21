"""防回归：mean_quality 与 n_rate 在任何环节都不得互换。

使用差异明显的两个值：
- 全部质量字符 'I' (Phred 40) -> mean_quality == 40.0
- 一半碱基为 N              -> n_rate == 0.5
若字段被对调，断言立即失败。
覆盖：流水线计算结果、summary/report 子对象、SQLite 落库后重读、
作业列表与详情接口读出。
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models import Job
from app.pipeline.runner import _run_chain, create_job_stages, run_pipeline_sync


# 16 个碱基中 8 个 N；质量串全 'I' -> Phred 40
HALF_N_FASTQ = """@R1
NNNNAAAA
+
IIIIIIII
@R2
NNNNCCCC
+
IIIIIIII
"""

MEAN_QUALITY = 40.0
N_RATE = 0.5
assert MEAN_QUALITY != N_RATE


@pytest.mark.asyncio
async def test_chain_metrics_not_swapped():
    ok, ctx, _stages = await _run_chain(HALF_N_FASTQ)
    assert ok is True

    m = ctx.metrics
    assert m["mean_quality"] == MEAN_QUALITY
    assert m["n_rate"] == N_RATE
    # 双向断言：两个键都没有被对调
    assert m["mean_quality"] != N_RATE
    assert m["n_rate"] != MEAN_QUALITY

    assert m["summary"]["mean_quality"] == MEAN_QUALITY
    assert m["summary"]["n_rate"] == N_RATE
    assert m["report"]["mean_quality"] == MEAN_QUALITY
    assert m["report"]["n_rate"] == N_RATE


def _make_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine), engine


def test_persisted_metrics_not_swapped():
    SessionLocal, engine = _make_session_factory()
    db = SessionLocal()
    try:
        job = Job(
            sample_id=None,
            sample_name="自定义输入",
            status="pending",
            created_by="bioops",
            fastq_snapshot=HALF_N_FASTQ,
        )
        db.add(job)
        db.commit()
        create_job_stages(db, job.id)
        run_pipeline_sync(db, job)
        job_id = job.id
    finally:
        db.close()

    # 全新会话重读，验证落库 JSON 未被对调
    db2 = SessionLocal()
    try:
        reloaded = db2.query(Job).filter(Job.id == job_id).one()
        assert reloaded.status == "success"
        m = reloaded.metrics
        assert m["mean_quality"] == MEAN_QUALITY
        assert m["n_rate"] == N_RATE
        assert m["summary"]["mean_quality"] == MEAN_QUALITY
        assert m["summary"]["n_rate"] == N_RATE
        assert m["report"]["mean_quality"] == MEAN_QUALITY
        assert m["report"]["n_rate"] == N_RATE
    finally:
        db2.close()
        engine.dispose()


def test_api_list_and_detail_metrics_not_swapped():
    SessionLocal, engine = _make_session_factory()
    db = SessionLocal()
    try:
        job = Job(
            sample_id=None,
            sample_name="自定义输入",
            status="pending",
            created_by="bioops",
            fastq_snapshot=HALF_N_FASTQ,
        )
        db.add(job)
        db.commit()
        create_job_stages(db, job.id)
        run_pipeline_sync(db, job)
        job_id = job.id
    finally:
        db.close()

    def override_get_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    token = create_access_token("bioops", "bioops")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        # 不用 context manager，避免 lifespan 对默认 postgres engine 执行 create_all
        client = TestClient(app)
        detail = client.get(f"/api/jobs/{job_id}", headers=headers).json()
        assert detail["metrics"]["mean_quality"] == MEAN_QUALITY
        assert detail["metrics"]["n_rate"] == N_RATE
        assert detail["metrics"]["summary"]["mean_quality"] == MEAN_QUALITY
        assert detail["metrics"]["summary"]["n_rate"] == N_RATE
        assert detail["metrics"]["report"]["mean_quality"] == MEAN_QUALITY
        assert detail["metrics"]["report"]["n_rate"] == N_RATE

        rows = client.get("/api/jobs", headers=headers).json()
        row = next(r for r in rows if r["id"] == job_id)
        assert row["metrics"]["mean_quality"] == MEAN_QUALITY
        assert row["metrics"]["n_rate"] == N_RATE
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
