from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Optional, List
import requests
import os
import openpyxl

from app.database import get_db
from app.utils.response import create_response, ResponseModel
from app.config import Settings
from app.models import Testcase, Testsuite, Interface
from app.models.testreport import Testreport, ExecutionDetail
from app.schemas.base_schemas import TestStepStatus
from app.schemas.metrics import JiraBugDistributionItem, JiraBugItem, JiraFixVersion, JiraBugDistributionData, JiraFixVersionsData, JiraSeverityItem, JiraVersionTrendItem, JiraVersionTrendData
from app.services.ai_service import ai_service

settings = Settings()

router = APIRouter(prefix="/rest/v1/metrics", tags=["metrics"]) 

@router.get("/dashboard", response_model=ResponseModel)
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    """首页观测性指标聚合
    返回：用例、套件、接口、报告数量，以及最近24小时的执行情况与最近一次报告摘要。
    """
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
    project_key: str = Query("Gino", description="Jira 项目键（默认 Gino），例如 Gino、DM、PROJ"),
    start_date: Optional[str] = Query(None, description="开始日期（YYYY-MM-DD）"),
    end_date: Optional[str] = Query(None, description="结束日期（YYYY-MM-DD）"),
    months: Optional[int] = Query(None, ge=1, le=24, description="兼容旧参数：月份范围。当未提供日期范围时可用"),
    fix_versions: Optional[List[str]] = Query(None, description="修复版本筛选（多选）")
):
    """Jira Bug 在各模块（components）的分布情况，支持自定义日期范围。

    说明：
    - 聚合维度：Jira issue 的 Components；若无组件则归类为“未分配”。
    - 时间范围优先：start_date 与 end_date（格式 YYYY-MM-DD）；若未提供，则回退为 months（月数，兼容旧参数）。
    - 统计条件：issuetype = Bug 且 created 在所选日期范围内。
    """
    try:
        paths: list[list[str]] = []
        depth_map: dict[str, int] = {}
        leaf_set: set[str] = set()
        path = getattr(settings, "JIRA_COMPONENTS_XLSX_PATH", None)
        if path and os.path.isfile(path):
            wb = openpyxl.load_workbook(path)
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                if not row:
                    continue
                row_values: list[str] = []
                for col_idx, cell in enumerate(row):
                    val = str(cell).strip() if cell is not None else ""
                    if val != "":
                        row_values.append(val)
                        key = val.lower()
                        depth_map[key] = max(depth_map.get(key, -1), col_idx)
                if row_values:
                    paths.append(row_values)
                    leaf_set.add(row_values[-1].lower())
        # 解析日期范围
        start_str: Optional[str] = None
        end_str: Optional[str] = None

        if start_date and end_date:
            # 校验格式
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return await create_response(
                    data={
                        "project_key": project_key,
                        "start_date": start_date,
                        "end_date": end_date,
                        "total_bugs": 0,
                        "items": [],
                        "error": "日期格式错误，应为 YYYY-MM-DD"
                    },
                    code="1",
                    msg="日期格式错误，应为 YYYY-MM-DD"
                )

            if start_dt > end_dt:
                return await create_response(
                    data={
                        "project_key": project_key,
                        "start_date": start_date,
                        "end_date": end_date,
                        "total_bugs": 0,
                        "items": [],
                        "error": "开始日期不能晚于结束日期"
                    },
                    code="1",
                    msg="开始日期不能晚于结束日期"
                )

            start_str = start_dt.strftime("%Y-%m-%d")
            end_str = end_dt.strftime("%Y-%m-%d")
        elif months is not None:
            start_dt = datetime.utcnow() - timedelta(days=30 * months)
            end_dt = datetime.utcnow()
            start_str = start_dt.strftime("%Y-%m-%d")
            end_str = end_dt.strftime("%Y-%m-%d")
        else:
            start_str = None
            end_str = None

        base_url = settings.JIRA_URL.rstrip('/')
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        resolved_key = project_key
        check_resp = requests.get(
            f"{base_url}/rest/api/3/project/{project_key}",
            headers=headers,
            auth=(settings.JIRA_USER, settings.JIRA_API_TOKEN),
            timeout=settings.JIRA_TIMEOUT,
            verify=getattr(settings, "JIRA_VERIFY", True)
        )
        if check_resp.status_code == 404:
            search_resp = requests.get(
                f"{base_url}/rest/api/3/project/search",
                params={"query": project_key},
                headers=headers,
                auth=(settings.JIRA_USER, settings.JIRA_API_TOKEN),
                timeout=settings.JIRA_TIMEOUT,
                verify=getattr(settings, "JIRA_VERIFY", True)
            )
            if search_resp.status_code == 200:
                values = (search_resp.json() or {}).get("values", [])
                if values:
                    resolved_key = values[0].get("key", project_key)

        conditions = [
            f'project = {resolved_key}',
            'issuetype = Bug'
        ]
        if start_str and end_str:
            conditions.append(f'created >= "{start_str}"')
            conditions.append(f'created <= "{end_str}"')
        if fix_versions:
            safe_versions = [v.replace('"', '\\"') for v in fix_versions if v]
            if safe_versions:
                versions_expr = ', '.join([f'"{v}"' for v in safe_versions])
                conditions.append(f'fixVersion in ({versions_expr})')
        jql = ' AND '.join(conditions)

        # 分页拉取所有匹配的 issues
        start_at = 0
        max_results = 100
        total = 0
        distribution: dict[str, int] = {}
        severity_map: dict[str, int] = {}
        bug_items: list[dict] = []

        # Jira Cloud 新版 JQL Search API：POST /rest/api/3/search/jql（返回 nextPageToken，用于分页）
        # 参考变更日志：CHANGE-2046（旧 Search API 已移除，需迁移到 /search/jql）
        search_url = f"{base_url}/rest/api/3/search/jql"
        next_token = None

        while True:
            payload = {
                "jql": jql,
                "maxResults": max_results,
                "fields": ["components", "created", "priority"]
            }
            if next_token:
                payload["nextPageToken"] = next_token

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }

            resp = requests.post(
                search_url,
                json=payload,
                headers=headers,
                auth=(settings.JIRA_USER, settings.JIRA_API_TOKEN),
                timeout=settings.JIRA_TIMEOUT,
                verify=getattr(settings, "JIRA_VERIFY", True)
            )

            if resp.status_code != 200:
                body_preview = resp.text[:500] if resp.text else ""
                raise Exception(
                    f"Jira Search 失败: HTTP {resp.status_code}, url={search_url}, body={body_preview}"
                )

            body = resp.json() or {}
            issues = body.get("issues", [])

            if not issues:
                break

            for issue in issues:
                total += 1
                fields = issue.get("fields", {}) or {}
                comps = fields.get("components", []) or []
                comp_names = [ (c.get("name") or "未命名组件") for c in comps ]
                prio = fields.get("priority") or {}
                prio_name = (prio.get("name") or "未分级")
                bug_items.append({
                    "key": issue.get("key"),
                    "components": comp_names,
                    "created": fields.get("created"),
                    "severity": prio_name
                })
                severity_map[prio_name] = severity_map.get(prio_name, 0) + 1

                best_name = None
                best_depth = -1
                issue_names = { (comp.get("name") or "未命名组件").lower() for comp in comps }
                # 1) 优先：按每一行路径内匹配的最大索引（同一条路径越右越深）
                if paths:
                    for p in paths:
                        idxs = [i for i, v in enumerate(p) if v.lower() in issue_names]
                        if idxs:
                            d = max(idxs)
                            candidate = p[d]
                            if d > best_depth or (d == best_depth and candidate.lower() in leaf_set):
                                best_depth = d
                                best_name = candidate
                # 2) 回退：若未命中任何路径，按全局深度（真实列位置）选择；同深度优先叶子
                if not best_name and comps:
                    candidates = []
                    for comp in comps:
                        nm = (comp.get("name") or "未命名组件")
                        key = nm.lower()
                        d = depth_map.get(key, -1)
                        is_leaf = 1 if key in leaf_set else 0
                        candidates.append((nm, d, is_leaf))
                    if candidates:
                        nm, d, _ = max(candidates, key=lambda x: (x[1], x[2]))
                        if d >= 0:
                            best_name = nm
                            best_depth = d
                # 3) 最终回退：选择首组件
                if not best_name:
                    for comp in comps:
                        name = comp.get("name") or "未命名组件"
                        best_name = name
                        best_depth = 0
                        break
                if best_name:
                    distribution[best_name] = distribution.get(best_name, 0) + 1
                else:
                    distribution["未分配"] = distribution.get("未分配", 0) + 1

            # 新版 JQL Search 使用 nextPageToken 进行分页
            next_token = body.get("nextPageToken")
            if not next_token:
                break

        # 转换为前端友好的结构并排序
        items_models = [
            JiraBugDistributionItem(module=name, bug_count=count)
            for name, count in distribution.items()
        ]
        items_models.sort(key=lambda x: x.bug_count, reverse=True)
        severity_items = [JiraSeverityItem(name=k, count=v) for k, v in severity_map.items()]
        severity_items.sort(key=lambda x: x.count, reverse=True)
        bugs_models = [
            JiraBugItem(key=b["key"], components=b["components"], created=b.get("created"), severity=b.get("severity"))
            for b in bug_items
        ]
        data_model = JiraBugDistributionData(
            project_key=project_key,
            start_date=start_str,
            end_date=end_str,
            total_bugs=total,
            items=items_models,
            bugs=bugs_models,
            bug_severity=severity_items
        )
        return await create_response(data=data_model.model_dump())
    except Exception as e:
        # 返回结构化错误，便于前端降级显示
        return await create_response(
            data={
                "project_key": project_key,
                "start_date": start_date,
                "end_date": end_date,
                "total_bugs": 0,
                "items": [],
                "error": str(e)
            },
            code="1",
            msg=f"Jira 聚合失败: {str(e)}"
        )

@router.get("/jira/fix-versions", response_model=ResponseModel)
async def get_jira_fix_versions(
    project_key: str = Query("Gino", description="Jira 项目键（默认 Gino），例如 Gino、DM、PROJ")
):
    try:
        base_url = settings.JIRA_URL.rstrip('/')
        headers = {"Accept": "application/json"}
        key = project_key
        check = requests.get(
            f"{base_url}/rest/api/3/project/{key}",
            headers=headers,
            auth=(settings.JIRA_USER, settings.JIRA_API_TOKEN),
            timeout=settings.JIRA_TIMEOUT,
            verify=getattr(settings, "JIRA_VERIFY", True)
        )
        if check.status_code == 404:
            search = requests.get(
                f"{base_url}/rest/api/3/project/search",
                params={"query": project_key},
                headers=headers,
                auth=(settings.JIRA_USER, settings.JIRA_API_TOKEN),
                timeout=settings.JIRA_TIMEOUT,
                verify=getattr(settings, "JIRA_VERIFY", True)
            )
            if search.status_code == 200:
                values = (search.json() or {}).get("values", [])
                if values:
                    key = values[0].get("key", project_key)

        url = f"{base_url}/rest/api/3/project/{key}/versions"
        resp = requests.get(
            url,
            headers=headers,
            auth=(settings.JIRA_USER, settings.JIRA_API_TOKEN),
            timeout=settings.JIRA_TIMEOUT,
            verify=getattr(settings, "JIRA_VERIFY", True)
        )
        if resp.status_code != 200:
            body_preview = resp.text[:500] if resp.text else ""
            raise Exception(f"获取修复版本失败: HTTP {resp.status_code}, url={url}, body={body_preview}")
        items = resp.json() or []
        versions_models = []
        for v in items:
            name = v.get("name")
            if name:
                versions_models.append(
                    JiraFixVersion(
                        name=name,
                        id=v.get("id"),
                        released=v.get("released"),
                        archived=v.get("archived")
                    )
                )
        data_model = JiraFixVersionsData(project_key=key, versions=versions_models)
        return await create_response(data=data_model.model_dump())
    except Exception as e:
        return await create_response(data={"project_key": project_key, "versions": [], "error": str(e)}, code="1", msg=str(e))


@router.get("/jira/version-trend", response_model=ResponseModel)
async def get_jira_version_trend(
    project_key: str = Query("Gino", description="Jira 项目键（默认 Gino）"),
    fix_versions: Optional[List[str]] = Query(None, description="修复版本筛选（多选）；为空则使用项目全部版本")
):
    """按修复版本统计 Bug 与需求数量，用于版本折线图。

    - Bug：issuetype = Bug
    - 需求：常见需求类型（Story/Task/Requirement/Feature/Improvement/Change 等），以及非 Bug 类型作为兜底
    - 若传入多个版本，则聚合每个版本的计数
    """
    try:
        base_url = settings.JIRA_URL.rstrip('/')
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        # 解析项目键
        key = project_key
        check = requests.get(
            f"{base_url}/rest/api/3/project/{key}",
            headers=headers,
            auth=(settings.JIRA_USER, settings.JIRA_API_TOKEN),
            timeout=settings.JIRA_TIMEOUT,
            verify=getattr(settings, "JIRA_VERIFY", True)
        )
        if check.status_code == 404:
            search = requests.get(
                f"{base_url}/rest/api/3/project/search",
                params={"query": project_key},
                headers=headers,
                auth=(settings.JIRA_USER, settings.JIRA_API_TOKEN),
                timeout=settings.JIRA_TIMEOUT,
                verify=getattr(settings, "JIRA_VERIFY", True)
            )
            if search.status_code == 200:
                values = (search.json() or {}).get("values", [])
                if values:
                    key = values[0].get("key", project_key)

        # 获取版本列表（若未指定）
        versions_list: List[str] = []
        if fix_versions and len(fix_versions) > 0:
            versions_list = [v for v in fix_versions if v]
        else:
            vurl = f"{base_url}/rest/api/3/project/{key}/versions"
            vresp = requests.get(
                vurl,
                headers={"Accept": "application/json"},
                auth=(settings.JIRA_USER, settings.JIRA_API_TOKEN),
                timeout=settings.JIRA_TIMEOUT,
                verify=getattr(settings, "JIRA_VERIFY", True)
            )
            if vresp.status_code == 200:
                vitems = vresp.json() or []
                versions_list = [vi.get("name") for vi in vitems if vi.get("name")]

        if not versions_list:
            return await create_response(data=JiraVersionTrendData(project_key=key, items=[]).model_dump())

        safe_versions = [v.replace('"', '\\"') for v in versions_list]
        versions_expr = ', '.join([f'"{v}"' for v in safe_versions])
        search_url = f"{base_url}/rest/api/3/search/jql"
        agg = {v: {"bug": 0, "demand": 0} for v in versions_list}

        for v in versions_list:
            sv = v.replace('"', '\\"')
            bug_jql = f'project = {key} AND issuetype = Bug AND fixVersion = "{sv}"'
            demand_jql = f'project = {key} AND issuetype = Task AND fixVersion = "{sv}"'

            for name, jql in (("bug", bug_jql), ("demand", demand_jql)):
                total_count = 0
                next_token = None
                while True:
                    payload = {"jql": jql, "maxResults": 200, "fields": ["id"]}
                    if next_token:
                        payload["nextPageToken"] = next_token
                    resp = requests.post(
                        search_url,
                        json=payload,
                        headers=headers,
                        auth=(settings.JIRA_USER, settings.JIRA_API_TOKEN),
                        timeout=settings.JIRA_TIMEOUT,
                        verify=getattr(settings, "JIRA_VERIFY", True)
                    )
                    if resp.status_code != 200:
                        body_preview = resp.text[:500] if resp.text else ""
                        raise Exception(f"Jira Search 失败: HTTP {resp.status_code}, url={search_url}, body={body_preview}")
                    body = resp.json() or {}
                    issues = body.get("issues", []) or []
                    if not issues:
                        break
                    total_count += len(issues)
                    next_token = body.get("nextPageToken")
                    if not next_token:
                        break
                agg[v][name] = total_count

        items = [
            JiraVersionTrendItem(version=v, bug_count=counts["bug"], demand_count=counts["demand"]) 
            for v, counts in agg.items()
        ]
        def ver_key(s: str):
            x = str(s or "").strip().lstrip("vV")
            parts = x.split('.')
            res = []
            for p in parts:
                digits = ''.join(ch for ch in p if ch.isdigit())
                res.append(int(digits or '0'))
            return tuple(res)
        items.sort(key=lambda it: ver_key(it.version))

        data_model = JiraVersionTrendData(project_key=key, items=items)
        return await create_response(data=data_model.model_dump())
    except Exception as e:
        return await create_response(
            data={
                "project_key": project_key,
                "items": [],
                "error": str(e)
            },
            code="1",
            msg=f"Jira 版本趋势失败: {str(e)}"
        )
