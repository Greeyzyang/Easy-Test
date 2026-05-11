from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Optional, List
import os

from app.database import get_db
from app.utils.response import create_response, ResponseModel
from app.config import Settings
from app.models import Testcase, Testsuite, Interface
from app.models.testreport import Testreport, ExecutionDetail
from app.schemas.base_schemas import TestStepStatus
from app.schemas.metrics import JiraBugDistributionItem, JiraBugItem, JiraFixVersion, JiraBugDistributionData, JiraFixVersionsData, JiraSeverityItem, JiraVersionTrendItem, JiraVersionTrendData
from app.services.ai_service import ai_service
from app.utils.logger import get_logger

logger = get_logger(__name__)

settings = Settings()

router = APIRouter(prefix="/rest/v1/metrics", tags=["metrics"])

@router.get("/dashboard", response_model=ResponseModel)
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    """首页观测性指标聚合
    返回：用例、套件、接口、报告数量，以及最近24小时的执行情况与最近一次报告摘要。
    """
    logger.info("获取首页看板指标")
    # 基础数量统计
    tc_count = (await db.execute(select(func.count(Testcase.id)))).scalar() or 0
    ts_count = (await db.execute(select(func.count(Testsuite.id)))).scalar() or 0
    if_count = (await db.execute(select(func.count(Interface.id)))).scalar() or 0
    rp_count = (await db.execute(select(func.count(Testreport.id)))).scalar() or 0

    # 最近 24 小时统计
    now = datetime.utcnow()
    since = now - timedelta(days=1)
    recent_reports_count = (await db.execute(
        select(func.count(Testreport.id)).where(Testreport.start_time != None, Testreport.start_time >= since)
    )).scalar() or 0

    recent_failed_steps = (await db.execute(
        select(func.count(ExecutionDetail.id)).where(
            ExecutionDetail.status == TestStepStatus.FAILED,
            ExecutionDetail.start_time != None,
            ExecutionDetail.start_time >= since
        )
    )).scalar() or 0

    # 最近一次报告摘要
    last_report: Optional[Testreport] = (await db.execute(
        select(Testreport).where(Testreport.start_time != None).order_by(Testreport.start_time.desc()).limit(1)
    )).scalar_one_or_none()

    last_report_summary = None
    if last_report:
        last_report_summary = {
            "id": last_report.id,
            "status": str(last_report.status.value) if hasattr(last_report.status, "value") else str(last_report.status),
            "total_cases": last_report.total_cases or 0,
            "passed_cases": last_report.passed_cases or 0,
            "failed_cases": last_report.failed_cases or 0,
            "skipped_cases": last_report.skipped_cases or 0,
            "pass_rate": last_report.pass_rate or 0,
            "start_time": last_report.start_time.isoformat() if last_report.start_time else None,
            "end_time": last_report.end_time.isoformat() if last_report.end_time else None,
            "duration_ms": float(last_report.duration or 0)
        }

    data = {
        "testcase_count": tc_count,
        "testsuite_count": ts_count,
        "interface_count": if_count,
        "report_count": rp_count,
        "recent_24h": {
            "reports": recent_reports_count,
            "failed_steps": recent_failed_steps
        },
        "last_report": last_report_summary
    }
    return await create_response(data=data)
    
    
@router.get("/jira/bug-distribution", response_model=ResponseModel)
async def get_jira_bug_distribution(
    project_key: str = Query("DM", description="Jira 项目键（默认 DM），例如 DM、GINO、PROJ"),
    start_date: Optional[str] = Query(None, description="开始日期（YYYY-MM-DD）"),
    end_date: Optional[str] = Query(None, description="结束日期（YYYY-MM-DD）"),
    months: Optional[int] = Query(None, ge=1, le=24, description="兼容旧参数：月份范围。当未提供日期范围时可用"),
    fix_versions: Optional[List[str]] = Query(None, description="修复版本筛选（多选）")
):
    """Jira Bug 在各模块（components）的分布情况，支持自定义日期范围。"""
    try:
        # 兼容处理：如果提供了 months 但未提供 start_date，则计算 start_date
        if months and not start_date:
            start_date = (datetime.now() - timedelta(days=months*30)).strftime("%Y-%m-%d")

        # 使用统一的服务层逻辑，该逻辑已优化分页和大数据量处理
        data = ai_service.get_project_bug_distribution(
            project_key=project_key,
            start_date=start_date,
            end_date=end_date,
            fix_versions=fix_versions
        )
        return await create_response(data=JiraBugDistributionData(
            project_key=data.get("project", project_key),
            total_bugs=data.get("total_bugs", 0),
            items=data.get("items", []),
            bugs=data.get("bugs", []),
            bug_severity=data.get("bug_severity", [])
        ).model_dump())
    except Exception as e:
        logger.error(f"获取 Jira Bug 分布失败: {str(e)}")
        return await create_response(
            data={
                "project_key": project_key,
                "total_bugs": 0,
                "items": [],
                "error": str(e)
            },
            code="1",
            msg=f"Jira 聚合失败: {str(e)}"
        )

@router.get("/jira/fix-versions", response_model=ResponseModel)
async def get_jira_fix_versions(
    project_key: str = Query("DM", description="Jira 项目键（默认 DM），例如 DM、GINO、PROJ")
):
    try:
        # Use centralized service
        items = ai_service.get_project_fix_versions(project_key)
        
        if isinstance(items, dict) and "error" in items:
            raise Exception(items["error"])
            
        versions_models = []
        for v in items:
            versions_models.append(
                JiraFixVersion(
                    name=v.get("name"),
                    id=v.get("id"),
                    released=v.get("released"),
                    archived=v.get("archived"),
                    release_date=v.get("releaseDate")
                )
            )
        data_model = JiraFixVersionsData(project_key=project_key, versions=versions_models)
        return await create_response(data=data_model.model_dump())
    except Exception as e:
        return await create_response(data={"project_key": project_key, "versions": [], "error": str(e)}, code="1", msg=str(e))


@router.get("/jira/version-trend", response_model=ResponseModel)
async def get_jira_version_trend(
    project_key: str = Query("DM", description="Jira 项目键（默认 DM）"),
    start_date: Optional[str] = Query(None, description="开始日期（YYYY-MM-DD）"),
    end_date: Optional[str] = Query(None, description="结束日期（YYYY-MM-DD）"),
    version_type: str = Query("all", description="版本类型筛选（official/patch/all，默认 all）"),
    fix_versions: Optional[List[str]] = Query(None, description="修复版本筛选（多选）")
):
    """按项目获取 Jira 版本趋势数据（支持日期筛选与版本类型筛选）。"""
    try:
        data = ai_service.get_project_version_trend(
            project_key, 
            start_date=start_date, 
            end_date=end_date, 
            version_type=version_type,
            fix_versions=fix_versions
        )
        
        if "error" in data:
            raise Exception(data["error"])

        return await create_response(data=JiraVersionTrendData(
            project_key=project_key,
            items=data.get("items", [])
        ).model_dump())
    except Exception as e:
        logger.error(f"获取 Jira 版本趋势失败: {e}")
        return await create_response(data={
            "project_key": project_key,
            "error": str(e)
        }, code="1", msg=f"Jira 聚合失败: {e}")

@router.get("/jira/member-efficiency", response_model=ResponseModel)
async def get_jira_member_efficiency(
    project_key: str = Query("DM", description="Jira 项目键"),
    fix_versions: Optional[List[str]] = Query(None, description="修复版本筛选"),
    start_date: Optional[str] = Query(None, description="开始日期（YYYY-MM-DD）"),
    end_date: Optional[str] = Query(None, description="结束日期（YYYY-MM-DD）"),
    version_type: str = Query("all", description="版本类型筛选（official/patch/all，默认 all）"),
    limit: Optional[int] = Query(None, description="限制最近N个版本")
):
    """获取成员 Bug 修复效率统计。"""
    try:
        # 确保 fix_versions 是列表
        versions = fix_versions if fix_versions else []
        
        data = ai_service.get_version_member_cycle_time(
            project_key=project_key,
            versions=versions,
            start_date=start_date,
            end_date=end_date,
            version_type=version_type,
            limit=limit
        )
        return await create_response(data=data)
    except Exception as e:
        logger.error(f"获取 Jira 成员效率失败: {str(e)}")
        return await create_response(
            data={
                "project_key": project_key,
                "member_cycle_times": [],
                "error": str(e)
            },
            code="1",
            msg=f"获取效率数据失败: {str(e)}"
        )
