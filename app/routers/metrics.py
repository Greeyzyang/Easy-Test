from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from app.database import get_db
from app.models import Testcase, Testsuite, Interface, Testreport, ExecutionDetail
from app.utils.response import create_response, ResponseModel
from app.schemas.base_schemas import TestStepStatus

router = APIRouter(prefix="/rest/v1/metrics", tags=["metrics"])

@router.get("/dashboard", response_model=ResponseModel)
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    since = now - timedelta(days=1)

    # Counts
    tc_count = await db.execute(select(func.count(Testcase.id)))
    ts_count = await db.execute(select(func.count(Testsuite.id)))
    iface_count = await db.execute(select(func.count(Interface.id)))
    report_count = await db.execute(select(func.count(Testreport.id)))

    # Recent 24h
    recent_reports_stmt = select(func.count(Testreport.id)).where(
        Testreport.start_time != None,  # noqa: E711
        Testreport.start_time >= since
    )
    recent_reports = await db.execute(recent_reports_stmt)

    recent_failed_steps_stmt = select(func.count(ExecutionDetail.id)).where(
        ExecutionDetail.start_time != None,  # noqa: E711
        ExecutionDetail.start_time >= since,
        ExecutionDetail.status == TestStepStatus.FAILED
    )
    recent_failed_steps = await db.execute(recent_failed_steps_stmt)

    # Last report
    last_stmt = select(Testreport).where(Testreport.end_time != None).order_by(Testreport.end_time.desc()).limit(1)  # noqa: E711
    last_result = await db.execute(last_stmt)
    last_report = last_result.scalar_one_or_none()

    last_report_data = None
    if last_report:
        last_report_data = {
            "id": last_report.id,
            "status": getattr(last_report.status, "value", str(last_report.status)) if last_report.status else None,
            "total_cases": last_report.total_cases or 0,
            "passed_cases": last_report.passed_cases or 0,
            "failed_cases": last_report.failed_cases or 0,
            "skipped_cases": last_report.skipped_cases or 0,
            "pass_rate": last_report.pass_rate or 0,
            "duration_ms": float(last_report.duration or 0)
        }

    data = {
        "testcase_count": int(tc_count.scalar() or 0),
        "testsuite_count": int(ts_count.scalar() or 0),
        "interface_count": int(iface_count.scalar() or 0),
        "report_count": int(report_count.scalar() or 0),
        "recent_24h": {
            "reports": int(recent_reports.scalar() or 0),
            "failed_steps": int(recent_failed_steps.scalar() or 0)
        },
        "last_report": last_report_data
    }
    return await create_response(data=data)

@router.get("/jira/bug-distribution", response_model=ResponseModel)
async def jira_bug_distribution(
    project_key: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    fix_versions: Optional[list[str]] = Query(None),
):
    # 占位实现，返回空数据结构，前端会优雅降级
    data = {
        "total_bugs": 0,
        "items": [],
        "bug_severity": []
    }
    return await create_response(data=data)

@router.get("/jira/fix-versions", response_model=ResponseModel)
async def jira_fix_versions(project_key: Optional[str] = Query(None)):
    # 占位实现，返回空版本列表
    data = {"versions": []}
    return await create_response(data=data)

@router.get("/jira/version-trend", response_model=ResponseModel)
async def jira_version_trend(
    project_key: Optional[str] = Query(None),
    fix_versions: Optional[list[str]] = Query(None),
):
    # 占位实现，返回空趋势列表
    data = {"items": []}
    return await create_response(data=data)

