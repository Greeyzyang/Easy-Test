from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import insert, delete, update, func
from sqlalchemy.orm import selectinload
from .users import current_active_user
from app.database import get_db, User
from app.models import Interface, Testcase, TestStep, ExecutionDetail
from app.schemas.testcase import TestcaseCreate, TestcaseRead, TestcaseUpdate
from app.schemas.base_schemas import PaginationParams
from app.schemas.teststep import TestStepCreate, TestStepRead, TestStepUpdate
from app.schemas.ai import GenerateTaskRequest, InterfaceIdInput, SaveGeneratedTestcasesRequest
from typing import List
from app.utils.response import create_response, ResponseModel
from fastapi.responses import StreamingResponse
from app.services.agent_service import AgentService
from app.tasks.ai_tasks import generate_testcases_task, generate_interface_testcases_task
from celery.result import AsyncResult
import io
import json
import asyncio
import openpyxl
from openpyxl.styles import Alignment, Border, Side, Font
from openpyxl.utils import get_column_letter
from app.config import REDIS_URL
from datetime import datetime
try:
    import redis
except Exception:
    redis = None

from app.utils.logger import get_logger
from app.utils.llm_parsing import extract_json_from_llm_output

logger = get_logger(__name__)

router = APIRouter(prefix="/rest/v1/testcases", tags=["testcases"])

@router.post("/", response_model=ResponseModel)
async def create_testcase(testcase: TestcaseCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"Creating testcase: {testcase.name}")
    # 创建测试用例
    db_testcase = Testcase(**testcase.dict(exclude={"steps"}))
    db.add(db_testcase)
    await db.commit()
    await db.refresh(db_testcase)
    
    # 创建测试步骤
    if testcase.steps:
        logger.info(f"Adding {len(testcase.steps)} steps to testcase {db_testcase.id}")
        for step_data in testcase.steps:
            # 验证接口是否存在
            result = await db.execute(select(Interface).where(Interface.id == step_data.interface_id))
            if not result.scalar_one_or_none():
                logger.warning(f"Interface {step_data.interface_id} not found for testcase step")
                raise HTTPException(status_code=404, detail=f"Interface {step_data.interface_id} not found")
            
            # 创建测试步骤，确保设置正确的 testcase_id
            db_step = TestStep(
                **step_data.dict(exclude={"testcase_id"}),
                testcase_id=db_testcase.id
            )
            db.add(db_step)
        await db.commit()
        await db.refresh(db_testcase)
    
    # 重新查询以获取完整数据
    result = await db.execute(
        select(Testcase)
        .options(
            selectinload(Testcase.steps).selectinload(TestStep.interface),
            selectinload(Testcase.module)
        )
        .where(Testcase.id == db_testcase.id)
    )
    db_testcase = result.scalar_one()
    logger.info(f"Testcase created successfully: {db_testcase.id}")
    return await create_response(data=TestcaseRead.from_orm(db_testcase))

@router.get("/", response_model=ResponseModel)
async def read_testcases(
    params: PaginationParams = Depends(),
    name: str | None = Query(None, description="Filter by testcase name"),
    module_id: str | None = Query(None, description="Filter by module id"),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Reading testcases: skip={params.skip}, limit={params.limit}, name={name}, module_id={module_id}")
    
    # 基础查询
    query = select(Testcase).options(
        selectinload(Testcase.steps).selectinload(TestStep.interface),
        selectinload(Testcase.module)
    )
    
    # 计数查询
    count_query = select(func.count()).select_from(Testcase)

    if name:
        filter_stmt = Testcase.name.like(f"%{name}%")
        query = query.where(filter_stmt)
        count_query = count_query.where(filter_stmt)

    if module_id:
        query = query.where(Testcase.module_id == module_id)
        count_query = count_query.where(Testcase.module_id == module_id)

    # 执行计数查询
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 执行分页查询
    query = query.offset(params.skip).limit(params.limit)
    result = await db.execute(query)
    testcases = result.scalars().all()
    
    testcases_data = [TestcaseRead.model_validate(testcase) for testcase in testcases]
    return await create_response(data={"items": testcases_data, "total": total})

@router.get("/{testcase_id}/", response_model=ResponseModel)
async def read_testcase(testcase_id: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"Reading testcase details: {testcase_id}")
    result = await db.execute(
        select(Testcase)
        .options(
            selectinload(Testcase.steps).selectinload(TestStep.interface),
            selectinload(Testcase.module)
        )
        .where(Testcase.id == testcase_id)
    )
    testcase = result.scalar_one_or_none()
    if not testcase:
        logger.warning(f"Testcase not found: {testcase_id}")
        raise HTTPException(status_code=404, detail="Testcase not found")
    return await create_response(data=TestcaseRead.from_orm(testcase))

@router.put("/{testcase_id}/", response_model=ResponseModel)
async def update_testcase(testcase_id: str, testcase: TestcaseUpdate, db: AsyncSession = Depends(get_db)):
    logger.info(f"Updating testcase: {testcase_id}")
    # 检查测试用例是否存在
    result = await db.execute(select(Testcase).where(Testcase.id == testcase_id))
    db_testcase = result.scalar_one_or_none()
    if not db_testcase:
        logger.warning(f"Testcase not found: {testcase_id}")
        raise HTTPException(status_code=404, detail="Testcase not found")
    
    # 更新测试用例基本信息
    update_data = testcase.dict(exclude={"steps"}, exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_testcase, key, value)
    
    # 更新测试步骤
    if testcase.steps is not None:
        logger.info(f"Updating steps for testcase: {testcase_id}")
        # 获取现有步骤的ID列表
        result = await db.execute(
            select(TestStep.id).where(TestStep.testcase_id == testcase_id)
        )
        existing_step_ids = [row[0] for row in result.fetchall()]
        
        if existing_step_ids:
            # 先删除相关的执行记录
            await db.execute(
                delete(ExecutionDetail).where(ExecutionDetail.step_id.in_(existing_step_ids))
            )
            # 再删除步骤
            await db.execute(
                delete(TestStep).where(TestStep.testcase_id == testcase_id)
            )
        
        # 创建新步骤
        for index, step_data in enumerate(testcase.steps):
            # 验证接口是否存在
            result = await db.execute(select(Interface).where(Interface.id == step_data.interface_id))
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail=f"Interface {step_data.interface_id} not found")
            
            # 创建新的测试步骤，排除testcase_id字段
            step_dict = step_data.dict(exclude={'testcase_id'})
            db_step = TestStep(
                testcase_id=testcase_id,
                **step_dict
            )
            db.add(db_step)
    
    await db.commit()
    
    # 重新查询以获取更新后的完整数据
    result = await db.execute(
        select(Testcase)
        .options(
            selectinload(Testcase.steps).selectinload(TestStep.interface),
            selectinload(Testcase.module)
        )
        .where(Testcase.id == testcase_id)
    )
    updated_testcase = result.scalar_one()
    return await create_response(data=TestcaseRead.from_orm(updated_testcase))

@router.delete("/{testcase_id}/", response_model=ResponseModel)
async def delete_testcase(testcase_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Testcase).where(Testcase.id == testcase_id))
    testcase = result.scalar_one_or_none()
    if not testcase:
        raise HTTPException(status_code=404, detail="Testcase not found")
    # 删除测试步骤（由于外键约束，会自动删除）
    await db.delete(testcase)
    await db.commit()
    return await create_response(data=None, msg=f"Testcase {testcase_id} deleted successfully")

@router.delete("/", response_model=ResponseModel)
async def delete_testcases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Testcase))
    testcases = result.scalars().all()
    if not testcases:
        raise HTTPException(status_code=404, detail="Testcase not found")
    for testcase in testcases:
        await db.delete(testcase)
    await db.commit()
    return await create_response(data=None, msg="All testcases deleted successfully")

@router.post("/{testcase_id}/steps/", response_model=ResponseModel)
async def add_testcase_step(testcase_id: str, step: TestStepCreate, db: AsyncSession = Depends(get_db)):
    # 验证测试用例是否存在
    result = await db.execute(
        select(Testcase)
        .where(Testcase.id == testcase_id)
    )
    testcase = result.scalar_one_or_none()
    if not testcase:
        raise HTTPException(status_code=404, detail="Testcase not found")
    
    # 验证接口是否存在
    result = await db.execute(
        select(Interface)
        .where(Interface.id == step.interface_id)
    )
    interface = result.scalar_one_or_none()
    if not interface:
        raise HTTPException(status_code=404, detail="Interface not found")
    
    # 创建测试步骤，确保 testcase_id 被正确设置
    step_data = step.dict(exclude={'testcase_id'})  # 排除 testcase_id
    db_step = TestStep(**step_data, testcase_id=testcase_id)
    db.add(db_step)
    await db.commit()
    await db.refresh(db_step)
    
    return await create_response(data=TestStepRead.from_orm(db_step))


# --- AI 相关接口 (从 assistant 路由迁移，优化结构) ---

@router.get("/export/jira", tags=["ai", "testcases"])
async def export_testcases_from_jira(
    jira_key: str,
    db: AsyncSession = Depends(get_db)
):
    """
    根据 Jira Key 实时生成并导出测试用例为 Excel。
    """
    try:
        # 1. 鲁棒性处理：清洗 Jira Key
        import re
        match = re.search(r'([A-Z]+-\d+)', jira_key)
        if match:
            jira_key = match.group(1)
            
        service = AgentService(db)
        
        # 2. 获取 Jira 详情
        issue_details = service.ai_service.get_jira_issue_details(jira_key)
        if not issue_details:
            raise HTTPException(status_code=404, detail=f"未找到 Jira 需求 `{jira_key}` 或无权访问。")

        # 3. 调用生成逻辑
        llm_result = service.ai_service.generate_testcases_from_jira(issue_details, jira_key=jira_key)
        
        # 4. 统一解析 JSON（复用公共解析工具）
        if isinstance(llm_result, str):
            structured = extract_json_from_llm_output(llm_result)
            if isinstance(structured, list):
                structured = {"testcases": structured}
            if not isinstance(structured, dict):
                logger.error("解析 AI 输出失败：无法从响应中提取结构化 JSON")
                raise HTTPException(status_code=500, detail="解析 AI 生成结果失败，请重试。")
            llm_result = structured

        testcases = llm_result.get("testcases", [])
        if not testcases:
            raise HTTPException(status_code=400, detail=f"需求 `{jira_key}` 未能生成有效的测试用例，请检查需求描述是否完整。")

        # 5. 生成 Excel 流
        buffer = service.export_testcases_excel(jira_key, testcases)
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"testcases_{jira_key}_{date_str}.xlsx"
        
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出测试用例异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导出过程中出现未知错误: {str(e)}")


@router.post("/ai-generate/", status_code=202, tags=["ai", "testcases"])
async def start_ai_generation_task(
    request: GenerateTaskRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    启动异步 AI 生成测试用例任务。
    """
    if not request.jira_key:
        raise HTTPException(status_code=400, detail="Jira key is required.")
    
    import re
    jira_pattern = r'^[A-Z]+-\d+$'
    if not re.match(jira_pattern, request.jira_key):
        raise HTTPException(status_code=400, detail="Invalid Jira key format.")
    
    try:
        task = generate_testcases_task.delay(request.jira_key, request.linked_req_keys)
        return await create_response({
            "task_id": task.id,
            "message": "AI 生成任务已启动",
            "jira_key": request.jira_key
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")


@router.post("/interface/ai-generate/", status_code=202, tags=["ai", "testcases"])
async def start_interface_ai_generation_task(
    request: InterfaceIdInput,
    db: AsyncSession = Depends(get_db)
):
    """
    启动异步单接口 AI 生成测试用例任务。
    仅生成结果供用户 review，不直接入库。
    """
    if not request.interface_id:
        raise HTTPException(status_code=400, detail="Interface ID is required.")
    
    try:
        task = generate_interface_testcases_task.delay(request.interface_id)
        return await create_response(data={
            "task_id": task.id,
            "message": "接口 AI 生成任务已启动",
            "interface_id": request.interface_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动接口任务失败: {str(e)}")

@router.post("/save-generated/", status_code=201, tags=["ai", "testcases"])
async def save_generated_testcases(
    request: SaveGeneratedTestcasesRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    保存用户 review 后的 AI 生成测试用例。
    """
    from app.models.testcase import Testcase
    from app.models.teststep import TestStep
    from app.models.interface import Interface
    from sqlalchemy import select

    # 1. 验证接口是否存在
    result = await db.execute(select(Interface).where(Interface.id == request.interface_id))
    interface = result.scalars().first()
    if not interface:
        raise HTTPException(status_code=404, detail=f"Interface {request.interface_id} not found")

    saved_testcases = []
    try:
        for tc_data in request.testcases:
            # 2. 创建测试用例
            db_testcase = Testcase(
                name=tc_data.title,
                description=f"AI Generated from interface: {interface.name}. Type: {tc_data.type}",
                priority=int(tc_data.priority.replace('P', '')) if tc_data.priority.startswith('P') else 1,
                setup=tc_data.precondition,
                module_id=interface.module_id  # 自动关联到接口所属模块
            )
            db.add(db_testcase)
            await db.flush() # 获取 ID

            # 3. 创建测试步骤 (单接口生成通常对应一个步骤)
            # 这里的逻辑是：以接口定义的配置为基础，合并AI生成的配置
            # 这样可以确保如果AI生成的用例中没有包含某些必要的请求头或参数，会自动使用接口定义的默认值
            
            # 合并请求头
            final_headers = (interface.headers or {}).copy()
            if tc_data.headers:
                final_headers.update(tc_data.headers)
            
            # 合并查询参数
            final_params = (interface.params or {}).copy()
            if tc_data.params:
                final_params.update(tc_data.params)
                
            # 处理请求体（AI生成的body通常是完整的，但如果为空则使用接口示例）
            final_body = tc_data.body if tc_data.body is not None else interface.body

            db_step = TestStep(
                testcase_id=db_testcase.id,
                interface_id=request.interface_id,
                name=tc_data.title,
                order=0,
                request_type=interface.request_type, # 继承接口的请求类型
                headers=final_headers,
                params=final_params,
                body=final_body,
                expected_response_code=tc_data.expected_response_code,
                assertions=tc_data.assertions or [],
                extract_variables=tc_data.extract_variables or []
            )
            db.add(db_step)
            saved_testcases.append({
                "id": db_testcase.id,
                "name": db_testcase.name
            })

        await db.commit()
        return await create_response(data={
            "message": f"成功保存 {len(saved_testcases)} 条测试用例",
            "testcases": saved_testcases
        })
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"保存生成用例失败: {str(e)}")


@router.get("/ai-task/{task_id}/", tags=["ai", "testcases"])
async def get_ai_task_status(task_id: str):
    """
    查询 AI 生成任务的状态。
    """
    try:
        task_result = AsyncResult(task_id, app=generate_testcases_task.app)
        cached_result = None
        try:
            cache_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            cached_result = cache_client.get(f"ai:task:result:{task_id}")
        except Exception as cache_error:
            logger.warning(f"读取任务缓存失败: {cache_error}")

        response_data = {
            "task_id": task_id,
            "status": task_result.status,
            "result": None
        }

        if cached_result:
            try:
                cached_payload = json.loads(cached_result)
                if isinstance(cached_payload, dict):
                    response_data["result"] = cached_payload
                    cached_status = cached_payload.get("status")
                    if isinstance(cached_status, str) and cached_status:
                        response_data["status"] = cached_status
                    return await create_response(response_data)
            except json.JSONDecodeError:
                logger.warning(f"任务缓存 JSON 解析失败: task_id={task_id}")

        if task_result.successful():
            response_data["result"] = task_result.get()
        return await create_response(response_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai-export/{task_id}/", tags=["ai", "testcases"])
async def export_ai_generated_xlsx(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    导出 AI 生成任务的结果为 Excel。
    """
    service = AgentService(db)
    try:
        error_msg = None
        testcases = []
        analysis = []
        knowledge_sources = []
        
        # 1. Try to get result from Redis Cache (Unified Source)
        r = None
        cached_result = None
        if redis:
            try:
                r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
                cached_result = r.get(f"ai:task:result:{task_id}")
            except Exception as e:
                logger.warning(f"Failed to read task result from redis: {e}")

        if cached_result:
            try:
                result = json.loads(cached_result)
                if not isinstance(result, dict):
                     error_msg = f"任务结果格式错误: {type(result)}"
                elif result.get('status') != 'SUCCESS':
                     error_msg = f"任务执行失败: {result.get('error', '未知错误')}"
                else:
                    result_payload = result.get('result', {})
                    testcases = result_payload.get('testcases', [])
                    analysis = result_payload.get('analysis', [])
                    rag_summary = result_payload.get('rag_summary', {}) if isinstance(result_payload, dict) else {}
                    sources = rag_summary.get('sources', []) if isinstance(rag_summary, dict) else []
                    knowledge_sources = [
                        f"{item.get('source', 'Unknown')} (Page {item.get('page')})" if item.get('page') is not None else str(item.get('source', 'Unknown'))
                        for item in sources if isinstance(item, dict)
                    ]
                    if not testcases:
                         error_msg = "没有可导出的测试用例"
                    elif not isinstance(testcases, list):
                         error_msg = "测试用例数据格式错误 (非列表)"
            except json.JSONDecodeError:
                error_msg = "缓存结果解析失败"
        else:
            # 2. Fallback to Celery AsyncResult (For backward compatibility with running tasks)
            task_result = AsyncResult(task_id, app=generate_testcases_task.app)
            if not task_result.ready():
                 error_msg = f"任务未完成或缓存已过期 (Status: {task_result.status})"
            elif not task_result.successful():
                 error_msg = f"任务未完成或失败 (Status: {task_result.status})"
            else:
                result = task_result.get()
                if not isinstance(result, dict):
                     error_msg = f"任务结果格式错误: {type(result)}"
                elif result.get('status') != 'SUCCESS':
                     error_msg = f"任务执行失败: {result.get('error', '未知错误')}"
                else:
                    result_payload = result.get('result', {})
                    testcases = result_payload.get('testcases', [])
                    analysis = result_payload.get('analysis', [])
                    rag_summary = result_payload.get('rag_summary', {}) if isinstance(result_payload, dict) else {}
                    sources = rag_summary.get('sources', []) if isinstance(rag_summary, dict) else []
                    knowledge_sources = [
                        f"{item.get('source', 'Unknown')} (Page {item.get('page')})" if item.get('page') is not None else str(item.get('source', 'Unknown'))
                        for item in sources if isinstance(item, dict)
                    ]
                    if not testcases:
                         error_msg = "没有可导出的测试用例"
                    elif not isinstance(testcases, list):
                         error_msg = "测试用例数据格式错误 (非列表)"

        if error_msg:
             # 生成包含错误信息的 Excel
             import openpyxl
             from io import BytesIO
             wb = openpyxl.Workbook()
             ws = wb.active
             ws.title = "Error"
             ws.cell(row=1, column=1, value="导出失败")
             ws.cell(row=2, column=1, value=error_msg)
             
             # 尝试写入原始数据以便调试
             if 'result' in locals() and isinstance(result, dict):
                 ws.cell(row=4, column=1, value="原始数据:")
                 ws.cell(row=5, column=1, value=str(result.get('result', '')))
                 
             buffer = BytesIO()
             wb.save(buffer)
             buffer.seek(0)
             return StreamingResponse(
                buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=error_{task_id}.xlsx"}
            )
        
        jira_key = ""
        try:
            import re
            if isinstance(testcases, list) and testcases:
                for tc in testcases:
                    if not isinstance(tc, dict):
                        continue
                    case_id = tc.get('id')
                    if isinstance(case_id, str):
                        m_id = re.search(r'([A-Z]+-\d+)', case_id)
                        if m_id:
                            jira_key = m_id.group(1)
                            break
        except Exception:
            jira_key = ""
        date_str = datetime.now().strftime("%Y%m%d")
        filename_base = f"testcases_{jira_key}_{date_str}" if jira_key else f"testcases_{task_id}_{date_str}"
        buffer = service.export_testcases_excel(
            jira_key or f"task_{task_id}",
            testcases,
            analysis if isinstance(analysis, list) else None,
            knowledge_sources if isinstance(knowledge_sources, list) else None,
        )
        
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename_base}.xlsx",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
         logger.error(f"Export Excel failed: {e}", exc_info=True)
         # 发生未捕获异常时也尝试返回 Excel
         try:
             import openpyxl
             from io import BytesIO
             wb = openpyxl.Workbook()
             ws = wb.active
             ws.title = "System Error"
             ws.cell(row=1, column=1, value="系统错误")
             ws.cell(row=2, column=1, value=str(e))
             buffer = BytesIO()
             wb.save(buffer)
             buffer.seek(0)
             return StreamingResponse(
                buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=error_sys_{task_id}.xlsx"}
            )
         except:
             raise HTTPException(status_code=500, detail=f"导出失败且无法生成错误文件: {str(e)}")


@router.websocket("/ws/progress/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    """
    WebSocket 实时推送 AI 生成进度。
    """
    try:
        await websocket.accept()
    except Exception:
        return

    if redis is None:
        await websocket.send_text(json.dumps({"status": "ERROR", "text": "Redis 未安装"}))
        await websocket.close()
        return

    r = redis.Redis.from_url(REDIS_URL)
    channel = f"task:progress:{task_id}"
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel)

    try:
        while True:
            message = pubsub.get_message(timeout=1.0)
            if message and message.get("type") == "message":
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await websocket.send_text(data)
            
            if websocket.application_state != WebSocketState.CONNECTED:
                break
            await asyncio.sleep(0.2)
    except (WebSocketDisconnect, asyncio.CancelledError):
        # 连接断开或任务被取消（如服务器关闭）时正常退出
        pass
    except Exception as e:
        logger.error(f"WebSocket progress error: {str(e)}")
    finally:
        pubsub.unsubscribe(channel)

@router.get("/{testcase_id}/steps/", response_model=ResponseModel)
async def get_testcase_steps(
    testcase_id: str,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """获取测试用例的所有步骤"""
    # 验证测试用例是否存在
    result = await db.execute(select(Testcase).where(Testcase.id == testcase_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Testcase {testcase_id} not found")
    
    # 获取测试步骤列表
    result = await db.execute(
        select(TestStep)
        .options(selectinload(TestStep.interface))
        .where(TestStep.testcase_id == testcase_id)
        .offset(skip)
        .limit(limit)
    )
    steps = result.scalars().all()
    return await create_response(data=[TestStepRead.from_orm(step) for step in steps])

@router.delete("/{testcase_id}/steps/{step_id}/", response_model=ResponseModel)
async def delete_testcase_step(
    testcase_id: str,
    step_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除测试用例的某个步骤"""
    # 验证测试用例是否存在
    result = await db.execute(select(Testcase).where(Testcase.id == testcase_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Testcase {testcase_id} not found")
    
    # 验证步骤是否存在且属于该测试用例
    result = await db.execute(
        select(TestStep)
        .where(TestStep.id == step_id, TestStep.testcase_id == testcase_id)
    )
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail=f"TestStep {step_id} not found in Testcase {testcase_id}")
    
    await db.delete(step)
    await db.commit()
    return await create_response(data=None, msg=f"TestStep {step_id} deleted successfully")

@router.put("/{testcase_id}/steps/{step_id}/", response_model=ResponseModel)
async def update_testcase_step(
    testcase_id: str,
    step_id: str,
    step: TestStepUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新测试用例中的步骤信息"""
    # 验证测试用例是否存在
    result = await db.execute(
        select(Testcase).where(Testcase.id == testcase_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Testcase {testcase_id} not found")
    
    # 验证步骤是否存在且属于该测试用例
    result = await db.execute(
        select(TestStep)
        .options(selectinload(TestStep.interface))
        .where(TestStep.id == step_id, TestStep.testcase_id == testcase_id)
    )
    db_step = result.scalar_one_or_none()
    if not db_step:
        raise HTTPException(status_code=404, detail=f"TestStep {step_id} not found in Testcase {testcase_id}")
    
    # 如果更新了接口ID，验证新接口是否存在
    if step.interface_id:
        result = await db.execute(
            select(Interface).where(Interface.id == step.interface_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Interface {step.interface_id} not found")
    
    # 更新步骤信息
    update_data = step.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_step, key, value)
    
    await db.commit()
    await db.refresh(db_step)
    
    return await create_response(data=TestStepRead.from_orm(db_step))
