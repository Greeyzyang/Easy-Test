from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import insert, delete, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
import os
from app.database import get_db
from app.models import Testsuite, Testcase, TestStep, Interface, TestSuiteTestCase
from app.schemas.testsuite import TestsuiteCreate, TestsuiteRead, TestsuiteUpdate, ScheduleTestSuiteRequest
from app.schemas.base_schemas import PaginationParams
from app.utils.response import create_response, ResponseModel
from app.services.testreport_service import TestreportService
from app.celery_app import celery_app
from celery.schedules import crontab

from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/rest/v1/testsuites",
    tags=["testsuites"]
)

# 保存每个 testsuite_id 的 WebSocket 连接
active_connections = {}

@router.post("/", response_model=ResponseModel)
async def create_testsuite(testsuite: TestsuiteCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"Creating testsuite: {testsuite.name}")
    
    testcases = []
    # 如果有测试用例，先验证它们是否存在
    if testsuite.testcases:
        logger.info(f"Validating {len(testsuite.testcases)} testcases for testsuite")
        result = await db.execute(
            select(Testcase)
            .where(Testcase.id.in_(testsuite.testcases))
        )
        found_testcases = result.scalars().all()
        
        # 验证所有测试用例是否存在
        if len(found_testcases) != len(testsuite.testcases):
            found_ids = {tc.id for tc in found_testcases}
            missing_ids = set(testsuite.testcases) - found_ids
            logger.warning(f"Testcases not found: {missing_ids}")
            raise HTTPException(
                status_code=404,
                detail=f"Testcases not found: {', '.join(missing_ids)}"
            )
        testcases = found_testcases

    # 按照请求中的顺序创建关联对象
    testcase_associations = []
    if testsuite.testcases:
        testcase_map = {tc.id: tc for tc in testcases}
        for index, tc_id in enumerate(testsuite.testcases):
            if tc_id in testcase_map:
                testcase_associations.append(
                    TestSuiteTestCase(testcase=testcase_map[tc_id], sort_order=index)
                )

    # 创建测试套件并直接添加测试用例关联
    db_testsuite = Testsuite(
        **testsuite.dict(exclude={"testcases"}),
        testcase_associations=testcase_associations
    )
    db.add(db_testsuite)
    await db.commit()
    await db.refresh(db_testsuite)
    logger.info(f"Testsuite created: {db_testsuite.id}")

    # 查询完整数据，包括测试用例基本信息和步骤数量
    result = await db.execute(
        select(Testsuite)
        .options(
            selectinload(Testsuite.testcase_associations)
            .selectinload(TestSuiteTestCase.testcase)
            .selectinload(Testcase.steps)
        )
        .where(Testsuite.id == db_testsuite.id)
    )
    db_testsuite = result.scalar_one()
    return await create_response(data=TestsuiteRead.from_orm(db_testsuite))

@router.get("/", response_model=ResponseModel)
async def read_testsuites(
    params: PaginationParams = Depends(),
    name: str | None = Query(None, description="Filter by testsuite name"),
    db: AsyncSession = Depends(get_db)
):
    # 基础查询
    query = select(Testsuite).options(
        selectinload(Testsuite.testcase_associations)
        .selectinload(TestSuiteTestCase.testcase)
        .selectinload(Testcase.steps)
    )
    
    # 计数查询
    count_query = select(func.count()).select_from(Testsuite)

    # 如果提供了 name 参数，添加过滤条件
    if name:
        filter_stmt = Testsuite.name.like(f"%{name}%")
        query = query.where(filter_stmt)
        count_query = count_query.where(filter_stmt)

    # 执行计数查询
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 添加排序
    query = query.order_by(Testsuite.id.desc())

    # 添加分页
    query = query.offset(params.skip).limit(params.limit)

    result = await db.execute(query)
    testsuites = result.scalars().all()
    
    testsuites_data = [TestsuiteRead.from_orm(ts) for ts in testsuites]
    return await create_response(data={"items": testsuites_data, "total": total})

@router.get("/{testsuite_id}/", response_model=ResponseModel)
async def read_testsuite(testsuite_id: str, db: AsyncSession = Depends(get_db)):
    # 详情接口需要加载完整的测试用例信息，包括步骤和接口
    result = await db.execute(
        select(Testsuite)
        .options(
            selectinload(Testsuite.testcase_associations)
            .selectinload(TestSuiteTestCase.testcase)
            .selectinload(Testcase.steps)
            .selectinload(TestStep.interface)
        )
        .where(Testsuite.id == testsuite_id)
    )
    testsuite = result.scalar_one_or_none()
    if not testsuite:
        raise HTTPException(status_code=404, detail="Testsuite not found")
    return await create_response(data=TestsuiteRead.from_orm(testsuite))

@router.put("/{testsuite_id}/", response_model=ResponseModel)
async def update_testsuite(testsuite_id: str, testsuite: TestsuiteUpdate, db: AsyncSession = Depends(get_db)):
    logger.info(f"Updating testsuite: {testsuite_id}")
    # 先加载测试套件及其测试用例，使用 selectinload 确保在异步环境中预加载关系
    result = await db.execute(
        select(Testsuite)
        .options(selectinload(Testsuite.testcase_associations))
        .where(Testsuite.id == testsuite_id)
    )
    db_testsuite = result.scalar_one_or_none()
    if not db_testsuite:
        logger.warning(f"Testsuite not found for update: {testsuite_id}")
        raise HTTPException(status_code=404, detail="Testsuite not found")
    
    # 更新基本字段
    update_data = testsuite.dict(exclude={"testcases"}, exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_testsuite, key, value)
    
    # 处理测试用例关系更新
    if testsuite.testcases is not None:
        logger.info(f"Updating {len(testsuite.testcases)} testcases for testsuite: {testsuite_id}")
        # 一次性查询所有新的测试用例
        result = await db.execute(
            select(Testcase)
            .where(Testcase.id.in_(testsuite.testcases))
        )
        new_testcases = result.scalars().all()
        
        # 验证所有测试用例是否存在
        if len(new_testcases) != len(testsuite.testcases):
            found_ids = {tc.id for tc in new_testcases}
            missing_ids = set(testsuite.testcases) - found_ids
            logger.warning(f"Testcases not found for testsuite update: {missing_ids}")
            raise HTTPException(
                status_code=404,
                detail=f"Testcases not found: {', '.join(missing_ids)}"
            )
        
        # 清空现有的测试用例关联
        db_testsuite.testcase_associations.clear()
        
        # 重建关联并保持顺序
        testcase_map = {tc.id: tc for tc in new_testcases}
        new_associations = []
        for index, tc_id in enumerate(testsuite.testcases):
            if tc_id in testcase_map:
                new_associations.append(
                    TestSuiteTestCase(testcase=testcase_map[tc_id], sort_order=index)
                )
        
        db_testsuite.testcase_associations = new_associations
    
    # 提交更改
    await db.commit()
    logger.info(f"Testsuite {testsuite_id} updated successfully")
    
    # 重新查询更新后的数据，确保所有关系正确加载
    result = await db.execute(
        select(Testsuite)
        .options(
            selectinload(Testsuite.testcase_associations)
            .selectinload(TestSuiteTestCase.testcase)
            .selectinload(Testcase.steps)
        )
        .where(Testsuite.id == testsuite_id)
    )
    updated_testsuite = result.scalar_one()
    return await create_response(data=TestsuiteRead.from_orm(updated_testsuite))

@router.delete("/{testsuite_id}/")
async def delete_testsuite(testsuite_id: str, db: AsyncSession = Depends(get_db)):
    # 先加载测试套件及其测试报告
    result = await db.execute(
        select(Testsuite)
        .options(selectinload(Testsuite.testreports))
        .where(Testsuite.id == testsuite_id)
    )
    testsuite = result.scalar_one_or_none()
    if not testsuite:
        raise HTTPException(status_code=404, detail="Testsuite not found")
    
    # 先删除相关的测试报告
    for report in testsuite.testreports:
        await db.delete(report)
    
    # 删除测试套件
    await db.delete(testsuite)
    await db.commit()
    # 移除 Celery 定时任务
    task_name = f"schedule_testsuite_{testsuite_id}"
    if task_name in celery_app.conf.beat_schedule:
        del celery_app.conf.beat_schedule[task_name]
        # 可以在此处添加日志或通知，表示任务已移除
        logger.info(f"Scheduled task {task_name} removed from Celery Beat.")

    return await create_response(data=None, msg=f"Testsuite {testsuite_id} and its scheduled task deleted successfully")

@router.websocket("/ws/progress/{testsuite_id}")
async def websocket_progress(websocket: WebSocket, testsuite_id: str):
    """
    WebSocket 路由：允许任意 Origin 连接（不做校验）
    """
    logger.info(f"Received WebSocket connection request for testsuite: {testsuite_id}")
    logger.debug(f"Headers: {websocket.headers}")
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted")
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")
    if testsuite_id not in active_connections:
        active_connections[testsuite_id] = []
    active_connections[testsuite_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()  # 保持连接
    except WebSocketDisconnect:
        active_connections[testsuite_id].remove(websocket)
        if not active_connections[testsuite_id]:
            del active_connections[testsuite_id]

@router.post("/{testsuite_id}/execute/", response_model=ResponseModel)
async def execute_testsuite(
    testsuite_id: str,
    env_name: str = Body(..., embed=True, description="环境变量名"),
    db: AsyncSession = Depends(get_db)):
    """
    执行测试套件并生成报告
    """
    service = TestreportService(db)
    websocket_list = active_connections.get(testsuite_id, []) if 'active_connections' in globals() else None
    testreport = await service.generate_report(testsuite_id, env_name, websocket_list)
    return await create_response(data={"id": testreport.id, "message": "测试执行完成"})

@router.post("/schedule/", response_model=ResponseModel)
async def schedule_testsuite(
    request: ScheduleTestSuiteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    调度测试套件定时执行
    """
    testsuite_id = request.testsuite_id
    cron_expression = request.cron_expression

    # 验证测试套件是否存在
    result = await db.execute(select(Testsuite).where(Testsuite.id == testsuite_id))
    testsuite = result.scalar_one_or_none()
    if not testsuite:
        raise HTTPException(status_code=404, detail="Testsuite not found")

    # 核心修改：将 cron_expression 保存到数据库
    testsuite.cron_expression = cron_expression
    db.add(testsuite) # 将更新后的对象添加到会话
    await db.commit() # 提交更改到数据库
    await db.refresh(testsuite) # 刷新对象以获取最新状态

    # 解析 Cron 表达式
    try:
        # Cron 表达式通常是 '分 时 天 月 周' 或者 '秒 分 时 天 月 周'
        # Celery 的 crontab 支持 '分 时 日 月 周' 格式，秒可选
        parts = cron_expression.split()
        if len(parts) == 5: # 分 时 日 月 周
            minute, hour, day_of_month, month_of_year, day_of_week = parts
            schedule = crontab(minute=minute, hour=hour, day_of_month=day_of_month, month_of_year=month_of_year, day_of_week=day_of_week)
        elif len(parts) == 6: # 秒 分 时 日 月 周
            second, minute, hour, day_of_month, month_of_year, day_of_week = parts
            schedule = crontab(minute=minute, hour=hour, day_of_month=day_of_month, month_of_year=month_of_year, day_of_week=day_of_week, second=second)
        else:
            raise ValueError("Invalid cron expression format. Expected 5 or 6 parts.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}")

    # 生成唯一的任务名称
    task_name = f"schedule_testsuite_{testsuite_id}"

    # 添加或更新 Celery Beat 调度
    celery_app.conf.beat_schedule[task_name] = {
        'task': 'execute_testsuite_task', # 对应 app.tasks.testsuite_tasks 中的任务名称
        'schedule': schedule,
        'args': (testsuite_id,), # 传递给任务的参数
        'options': {'queue': 'default'} # 可选：指定任务队列
    }
    celery_app.conf.timezone = 'Asia/Shanghai' # 确保 Celery Beat 使用正确的时区

    logger.info(f"Scheduled task '{task_name}' for testsuite {testsuite_id} with cron: {cron_expression}")
    # 可以在这里保存调度信息到数据库，以便持久化和管理

    return await create_response(data={"task_name": task_name, "message": "测试套件已成功调度"})
