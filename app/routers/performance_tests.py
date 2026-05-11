from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional

from app.database import get_db
from app.models import PerformanceTest, PerformanceTestReport
from app.schemas.performance_test import (
    PerformanceTestCreate, PerformanceTestRead, PerformanceTestUpdate,
    PerformanceScenarioSchema, UserPoolConfigSchema,
)
from app.schemas.performance_test_report import PerformanceTestReportRead, PerformanceTestReportListItem
from app.schemas.base_schemas import PaginationParams
from app.utils.response import create_response
from app.tasks.performance_test_tasks import run_performance_test_task
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/rest/v1/performance-tests",
    tags=["performance-tests"]
)

_running_tasks: dict[str, str] = {}


def _serialize_pt(item) -> dict:
    run_mode = getattr(item, "run_mode", "duration") or "duration"
    if run_mode == "fixed_users":
        run_mode = "fixed_requests"
    rc = item.request_config or {}
    scenario = rc.get("scenario")
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "project_id": item.project_id,
        "status": item.status.value if item.status else "PENDING",
        "concurrent_users": item.concurrent_users,
        "run_mode": run_mode,
        "duration_seconds": item.duration_seconds,
        "total_requests_limit": getattr(item, "total_requests_limit", None),
        "target_base_url": item.target_base_url,
        "scenario": scenario,
        "user_pool": {
            "variable_name": item.user_pool_ref,
            "mode": item.user_pool_mode,
            "auth_config": rc.get("user_pool_auth_config"),
        } if item.user_pool_ref else None,
        "created_time": item.created_time,
        "updated_time": item.updated_time,
    }


@router.post("/", response_model=dict)
async def create_performance_test(data: PerformanceTestCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"Creating performance test: {data.name}")

    user_pool = data.user_pool.model_dump() if data.user_pool else None
    scenario_dict = data.scenario.model_dump() if data.scenario else None
    request_config = {"scenario": scenario_dict} if scenario_dict else {}
    if user_pool and user_pool.get("auth_config"):
        request_config["user_pool_auth_config"] = user_pool["auth_config"]

    run_mode = data.run_mode or "duration"
    if run_mode == "fixed_users":
        run_mode = "fixed_requests"

    db_obj = PerformanceTest(
        name=data.name,
        description=data.description,
        project_id=data.project_id,
        concurrent_users=data.concurrent_users,
        run_mode=run_mode,
        duration_seconds=data.duration_seconds,
        total_requests_limit=data.total_requests_limit,
        target_base_url=data.target_base_url,
        request_config=request_config,
        user_pool_ref=user_pool.get("variable_name") if user_pool else None,
        user_pool_mode=user_pool.get("mode") if user_pool else None,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    logger.info(f"Performance test created: {db_obj.id}")
    return await create_response(data={"id": db_obj.id, "name": db_obj.name})


@router.get("/", response_model=dict)
async def list_performance_tests(
    params: PaginationParams = Depends(),
    name: Optional[str] = Query(None, description="Filter by name"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    db: AsyncSession = Depends(get_db),
):
    query = select(PerformanceTest)
    count_query = select(func.count()).select_from(PerformanceTest)

    if name:
        query = query.where(PerformanceTest.name.like(f"%{name}%"))
        count_query = count_query.where(PerformanceTest.name.like(f"%{name}%"))

    if project_id:
        query = query.where(PerformanceTest.project_id == project_id)
        count_query = count_query.where(PerformanceTest.project_id == project_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.order_by(PerformanceTest.created_time.desc())
    query = query.offset(params.skip).limit(params.limit)

    result = await db.execute(query)
    items = result.scalars().all()

    items_data = [_serialize_pt(item) for item in items]
    return await create_response(data={"items": items_data, "total": total})


@router.get("/{performance_test_id}/", response_model=dict)
async def get_performance_test(performance_test_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PerformanceTest).where(PerformanceTest.id == performance_test_id))
    pt = result.scalar_one_or_none()
    if not pt:
        raise HTTPException(status_code=404, detail="Performance test not found")
    return await create_response(data=_serialize_pt(pt))


@router.put("/{performance_test_id}/", response_model=dict)
async def update_performance_test(
    performance_test_id: str,
    data: PerformanceTestUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PerformanceTest).where(PerformanceTest.id == performance_test_id))
    pt = result.scalar_one_or_none()
    if not pt:
        raise HTTPException(status_code=404, detail="Performance test not found")

    update_data = data.model_dump(exclude_unset=True)
    if "run_mode" in update_data and update_data["run_mode"] == "fixed_users":
        update_data["run_mode"] = "fixed_requests"

    if "user_pool" in update_data and update_data["user_pool"] is not None:
        up = data.user_pool.model_dump()
        update_data["user_pool_ref"] = up.get("variable_name")
        update_data["user_pool_mode"] = up.get("mode")
        if up.get("auth_config"):
            if "request_config" not in update_data or update_data["request_config"] is None:
                update_data["request_config"] = {}
            update_data["request_config"]["user_pool_auth_config"] = up["auth_config"]
        del update_data["user_pool"]

    if "scenario" in update_data and update_data["scenario"] is not None:
        existing_cfg = (pt.request_config or {}).copy()
        if data.scenario:
            existing_cfg["scenario"] = data.scenario.model_dump()
        else:
            existing_cfg.pop("scenario", None)
        update_data["request_config"] = existing_cfg
        del update_data["scenario"]

    for key, value in update_data.items():
        if key not in ("user_pool_ref", "user_pool_mode"):
            setattr(pt, key, value)
    if "user_pool_ref" in update_data:
        pt.user_pool_ref = update_data["user_pool_ref"]
        pt.user_pool_mode = update_data.get("user_pool_mode")

    await db.commit()
    await db.refresh(pt)
    logger.info(f"Performance test {performance_test_id} updated")
    return await create_response(data={"id": pt.id, "name": pt.name})


@router.delete("/{performance_test_id}/", response_model=dict)
async def delete_performance_test(performance_test_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PerformanceTest).where(PerformanceTest.id == performance_test_id))
    pt = result.scalar_one_or_none()
    if not pt:
        raise HTTPException(status_code=404, detail="Performance test not found")
    await db.delete(pt)
    await db.commit()
    _running_tasks.pop(performance_test_id, None)
    logger.info(f"Performance test {performance_test_id} deleted")
    return await create_response(data=None, msg=f"Performance test {performance_test_id} deleted")


@router.post("/{performance_test_id}/execute/", response_model=dict)
async def execute_performance_test(performance_test_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PerformanceTest).where(PerformanceTest.id == performance_test_id))
    pt = result.scalar_one_or_none()
    if not pt:
        raise HTTPException(status_code=404, detail="Performance test not found")

    task = run_performance_test_task.delay(performance_test_id)
    _running_tasks[performance_test_id] = task.id
    logger.info(f"Performance test {performance_test_id} submitted to Celery, task_id: {task.id}")
    return await create_response(
        data={"task_id": task.id, "performance_test_id": performance_test_id},
        msg="Performance test task submitted"
    )


@router.post("/{performance_test_id}/stop/", response_model=dict)
async def stop_performance_test(performance_test_id: str, db: AsyncSession = Depends(get_db)):
    task_id = _running_tasks.get(performance_test_id)
    if not task_id:
        raise HTTPException(status_code=404, detail="No running task found for this performance test")

    try:
        from celery_app import celery_app
        celery_app.control.revoke(task_id, terminate=True)
    except Exception as e:
        logger.warning(f"Failed to revoke task {task_id}: {e}")

    result = await db.execute(select(PerformanceTest).where(PerformanceTest.id == performance_test_id))
    pt = result.scalar_one_or_none()
    if pt:
        from app.schemas.base_schemas import TestStatus
        pt.status = TestStatus.STOPPED
        await db.commit()

    _running_tasks.pop(performance_test_id, None)
    logger.info(f"Performance test {performance_test_id} stopped")
    return await create_response(data={"performance_test_id": performance_test_id}, msg="Stop signal sent")


@router.get("/{performance_test_id}/reports/", response_model=dict)
async def list_performance_test_reports(
    performance_test_id: str,
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    count_query = select(func.count()).select_from(PerformanceTestReport).where(
        PerformanceTestReport.performance_test_id == performance_test_id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = (
        select(PerformanceTestReport)
        .where(PerformanceTestReport.performance_test_id == performance_test_id)
        .order_by(PerformanceTestReport.created_time.desc())
        .offset(params.skip)
        .limit(params.limit)
    )
    result = await db.execute(query)
    reports = result.scalars().all()

    items_data = [
        {
            "id": r.id,
            "performance_test_id": r.performance_test_id,
            "status": r.status.value if r.status else "IN_PROGRESS",
            "start_time": r.start_time,
            "end_time": r.end_time,
            "duration_seconds": r.duration_seconds,
            "total_requests": r.total_requests,
            "successful_requests": r.successful_requests,
            "failed_requests": r.failed_requests,
            "error_rate": float(r.error_rate) if r.error_rate else None,
            "avg_response_time": float(r.avg_response_time) if r.avg_response_time else None,
            "p90_response_time": float(r.p90_response_time) if r.p90_response_time else None,
            "p99_response_time": float(r.p99_response_time) if r.p99_response_time else None,
            "requests_per_second": float(r.requests_per_second) if r.requests_per_second else None,
            "created_time": r.created_time,
        }
        for r in reports
    ]
    return await create_response(data={"items": items_data, "total": total})


@router.get("/reports/{report_id}/", response_model=dict)
async def get_performance_test_report(report_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PerformanceTestReport).where(PerformanceTestReport.id == report_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Performance test report not found")
    return await create_response(
        data={
            "id": r.id,
            "performance_test_id": r.performance_test_id,
            "status": r.status.value if r.status else "IN_PROGRESS",
            "start_time": r.start_time,
            "end_time": r.end_time,
            "duration_seconds": r.duration_seconds,
            "total_requests": r.total_requests,
            "successful_requests": r.successful_requests,
            "failed_requests": r.failed_requests,
            "error_rate": float(r.error_rate) if r.error_rate else None,
            "avg_response_time": float(r.avg_response_time) if r.avg_response_time else None,
            "min_response_time": float(r.min_response_time) if r.min_response_time else None,
            "max_response_time": float(r.max_response_time) if r.max_response_time else None,
            "median_response_time": float(r.median_response_time) if r.median_response_time else None,
            "p90_response_time": float(r.p90_response_time) if r.p90_response_time else None,
            "p95_response_time": float(r.p95_response_time) if r.p95_response_time else None,
            "p99_response_time": float(r.p99_response_time) if r.p99_response_time else None,
            "stddev_response_time": float(r.stddev_response_time) if r.stddev_response_time else None,
            "requests_per_second": float(r.requests_per_second) if r.requests_per_second else None,
            "timeline_data": r.timeline_data,
            "scenario_stats": r.scenario_stats,
            "created_time": r.created_time,
        }
    )
