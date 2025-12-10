from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from pydantic import BaseModel
from celery.result import AsyncResult
from fastapi.responses import StreamingResponse
import io
import openpyxl
from openpyxl.styles import Alignment, Border, Side, Font
from openpyxl.utils import get_column_letter
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.tasks.ai_tasks import generate_testcases_task, generate_kb_answer_task
from app.utils.response import create_response
from app.routers.users import current_active_user
from app.database import User

# 新增：Redis 订阅用于 WebSocket 推送
import json
from app.config import REDIS_URL
from app.schemas.base_schemas import KBQueryRequest
try:
    import redis
except Exception:
    redis = None


router = APIRouter(
    prefix="/rest/v1/ai",
    tags=["assistant"]
)


class GenerateTaskRequest(BaseModel):
    jira_key: str
    history_keys: list[str] = []


@router.post("/generate-task/", status_code=202)
async def start_generation_task(
    request: GenerateTaskRequest,
    db: AsyncSession = Depends(get_db) # 增加用户依赖
):
    """
    启动一个异步生成测试用例的任务
    优化：支持多模态分析，提升生成质量
    """
    if not request.jira_key:
        raise HTTPException(status_code=400, detail="Jira key is required.")
    
    # 验证Jira key格式
    import re
    jira_pattern = r'^[A-Z]+-\d+$'
    if not re.match(jira_pattern, request.jira_key):
        raise HTTPException(status_code=400, detail="Invalid Jira key format. Expected format: PROJECT-123")
    
    # 验证历史需求格式
    if request.history_keys:
        for key in request.history_keys:
            if not re.match(jira_pattern, key):
                raise HTTPException(status_code=400, detail=f"Invalid history Jira key format: {key}")
    
    try:
        task = generate_testcases_task.delay(request.jira_key, request.history_keys)
        return await create_response({
            "task_id": task.id,
            "message": "任务已启动，正在处理中... (优化版本：支持多模态分析)",
            "jira_key": request.jira_key,
            "history_keys_count": len(request.history_keys) if request.history_keys else 0,
            "optimization_note": "Enhanced multimodal analysis for better test case generation"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")


@router.get("/task-status/{task_id}/")
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_db) # 增加用户依赖
):
    """
    查询异步任务的状态和结果
    优化：提供更明确的状态信息和质量统计
    """
    if not task_id:
        raise HTTPException(status_code=400, detail="Task ID is required.")
    
    try:
        task_result = AsyncResult(task_id, app=generate_testcases_task.app)
        
        response_data = {
            "task_id": task_id,
            "status": task_result.status,
            "result": None,
            "timestamp": task_result.date_done.isoformat() if task_result.date_done else None,
            "optimization_note": "Optimized version with image processing disabled"
        }

        if task_result.successful():
            result = task_result.get()
            response_data["result"] = result
            if result.get('status') == 'SUCCESS':
                testcases = result.get('result', {}).get('testcases', [])
                response_data["summary"] = {
                    "total_testcases": len(testcases),
                    "generation_success": True,
                    "optimization_status": "Image processing disabled for better performance"
                }
            else:
                response_data["summary"] = {
                    "total_testcases": 0,
                    "generation_success": False,
                    "error": result.get('result', 'Unknown error'),
                    "optimization_status": "Optimized version"
                }
        elif task_result.failed():
            result_info = task_result.info if isinstance(task_result.info, dict) else {'exc_message': str(task_result.info)}
            response_data["result"] = {
                'error': result_info.get('exc_type', 'UnknownError'),
                'message': result_info.get('exc_message', 'An unknown error occurred.')
            }
            response_data["summary"] = {
                "total_testcases": 0,
                "generation_success": False,
                "error": result_info.get('exc_message', 'Task failed'),
                "optimization_status": "Optimized version"
            }
        else:  # PENDING or PROGRESS
            result_info = task_result.info if isinstance(task_result.info, dict) else {}
            if task_result.status == 'PROGRESS':
                response_data["result"] = {
                    'status': 'PROGRESS',
                    'message': result_info.get('status', '处理中...'),
                    'progress': result_info.get('progress', 0)
                }
            elif task_result.status == 'PENDING':
                response_data["result"] = {
                    'status': 'PENDING',
                    'message': '任务已排队，等待执行',
                    'progress': 0
                }
            else:
                # 兼容其他 Celery 自定义状态
                response_data["result"] = {
                    'status': task_result.status
                }

            response_data["summary"] = {
                "total_testcases": 0,
                "generation_success": False,
                "status": "in_progress",
                "optimization_status": "Optimized version with improved performance"
            }

        return await create_response(response_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务状态失败: {str(e)}")


@router.get("/export-xlsx/{task_id}/")
async def export_xlsx(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    导出测试用例为Excel文件
    """
    if not task_id:
        raise HTTPException(status_code=400, detail="Task ID is required.")
    
    try:
        task_result = AsyncResult(task_id, app=generate_testcases_task.app)
        if not task_result.successful():
            raise HTTPException(status_code=400, detail="任务未完成或失败")
        
        result = task_result.get()
        if result.get('status') != 'SUCCESS':
            raise HTTPException(status_code=400, detail="任务执行失败，无法导出")
        
        testcases = result.get('result', {}).get('testcases', [])
        if not testcases:
            raise HTTPException(status_code=400, detail="没有可导出的测试用例")
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "测试用例"
        
        # 添加表头（保持与前端约定一致，新结构 expected_result 合并展示在步骤区块内）
        headers = ["用例编号", "模块", "标题", "优先级", "类型", "前置条件", "测试步骤 / 预期结果"]
        ws.append(headers)
        
        # 设置表头样式
        for col_num, _ in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = Font(bold=True)
        
        # 当前行号
        row_num = 2
        
        # 合并单元格样式
        merged_style = Alignment(vertical='top', wrap_text=True)
        border_style = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for case in testcases:
            case_id = case.get("id", "")
            module = case.get("module", "")
            title = case.get("title", "")
            priority = case.get("priority", "")
            test_type = case.get("type", "")
            precondition = case.get("precondition", "")
            steps = case.get("steps", [])
            expected_result = case.get("expected_result", "")
            
            # 标准化步骤格式处理
            formatted_steps = []
            if isinstance(steps, list) and steps:
                if isinstance(steps[0], dict):
                    # 旧格式：字典数组，转换为标准格式
                    for i, step in enumerate(steps):
                        step_content = step.get("step", "")
                        expected = step.get("expected", "")
                        if step_content:
                            formatted_steps.append(f"步骤 {i+1}: {step_content}")
                            if expected:
                                formatted_steps.append(f"预期结果: {expected}")
                else:
                    # 新格式：字符串数组
                    for i, step_str in enumerate(steps):
                        if step_str and step_str.strip():
                            formatted_steps.append(f"步骤 {i+1}: {step_str.strip()}")
            
            # 如果没有格式化的步骤，至少添加一个空行
            if not formatted_steps:
                formatted_steps = ["无具体步骤"]
            
            # 添加整体预期结果
            if expected_result and expected_result.strip():
                formatted_steps.append(f"\n整体预期结果:\n{expected_result.strip()}")
            
            # 计算当前用例的行数
            steps_count = len(formatted_steps)
            
            # 添加用例基本信息
            ws.append([case_id, module, title, priority, test_type, precondition, ""])
            
            # 合并用例基本信息单元格
            for col in range(1, 7):  # 前6列需要合并
                ws.merge_cells(start_row=row_num, start_column=col, end_row=row_num + steps_count - 1, end_column=col)
                cell = ws.cell(row=row_num, column=col)
                cell.alignment = merged_style
                cell.border = border_style
            
            # 添加格式化的测试步骤
            for i, step_text in enumerate(formatted_steps):
                ws.cell(row=row_num + i, column=7).value = step_text
                ws.cell(row=row_num + i, column=7).alignment = merged_style
                ws.cell(row=row_num + i, column=7).border = border_style
            
            # 更新行号
            row_num += steps_count
        
        # 调整列宽
        column_widths = {1: 15, 2: 15, 3: 30, 4: 10, 5: 15, 6: 25, 7: 50}
        for col, width in column_widths.items():
            ws.column_dimensions[get_column_letter(col)].width = width
            
        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=testcases_{task_id}.xlsx"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出Excel文件失败: {str(e)}")


# 新增：WebSocket 路由用于实时推送 Celery 任务进度（通过 Redis Pub/Sub 转发）
@router.websocket("/ws/progress/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    # 允许任意来源连接，便于前端调试
    try:
        await websocket.accept()
    except Exception as e:
        print(f"WebSocket accept error: {e}")
        return

    # 如果没有 redis 依赖，提示并保持连接一段时间后关闭
    if redis is None:
        await websocket.send_text(json.dumps({
            "status": "ERROR",
            "text": "服务器未安装 redis 客户端，无法推送进度。请安装 redis-py。",
            "progress": 0
        }))
        await websocket.close()
        return

    r = redis.Redis.from_url(REDIS_URL)
    channel = f"ai:progress:{task_id}"
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel)

    try:
        import asyncio
        while True:
            # 从 Redis 获取消息（非阻塞），无消息时小睡一下
            message = pubsub.get_message(timeout=1.0)
            if message and message.get("type") == "message":
                data = message.get("data")
                try:
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    await websocket.send_text(data)
                except Exception as e:
                    print(f"WebSocket send error: {e}")
                    await websocket.send_text(str(data))
            if (
                websocket.application_state != WebSocketState.CONNECTED
                or websocket.client_state != WebSocketState.CONNECTED
            ):
                break
            try:
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                break
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        # 热重载或服务停止时的正常取消
        pass
    except asyncio.CancelledError:
        # 热重载或服务停止时的正常取消
        pass
    except Exception as e:
        print(f"WebSocket loop error: {e}")
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/kb/query/", status_code=202)
async def kb_query(request: KBQueryRequest, db: AsyncSession = Depends(get_db)):
    try:
        task = generate_kb_answer_task.delay(request.question, request.top_k)
        return await create_response({
            "task_id": task.id,
            "message": "知识库查询任务已启动，正在处理中..."
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")
