from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, or_
from .users import current_active_user
from app.database import get_db, User
from app.models import Interface, Module, Project
from app.schemas.interface import InterfaceCreate, InterfaceRead, SwaggerImportRequest
from app.schemas.base_schemas import PaginationParams
from typing import List
import httpx
import json
from app.utils.response import create_response, ResponseModel
from app.utils.logger import get_logger
from app.config import REDIS_URL

from app.tasks.interface_tasks import import_swagger_task
from celery.result import AsyncResult
from fastapi import WebSocket
import redis.asyncio as redis
import os

logger = get_logger(__name__)

router = APIRouter(prefix="/rest/v1/interfaces", tags=["interfaces"])


@router.post("/", response_model=ResponseModel)
async def create_interface(interface: InterfaceCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"Creating interface: {interface.name} in module {interface.module_id}")
    result = await db.execute(select(Module).where(Module.id == interface.module_id))
    moudle = result.scalar_one_or_none()
    if moudle is None:
        logger.warning(f"Module not found: {interface.module_id}")
        raise HTTPException(status_code=404, detail="Module not found")
    db_interface = Interface(**interface.dict())
    db.add(db_interface)
    await db.commit()
    await db.refresh(db_interface)
    # 获取完整数据（包括关联的steps）
    result = await db.execute(
        select(Interface)
        .options(selectinload(Interface.steps))
        .where(Interface.id == db_interface.id)
    )
    interface = result.scalar_one_or_none()
    interface_data = InterfaceRead.model_validate(interface).model_dump()
    logger.info(f"Interface created successfully: {db_interface.id}")
    return await create_response(data=interface_data)

@router.post("/import-swagger/", response_model=ResponseModel)
async def import_swagger(import_data: SwaggerImportRequest, db: AsyncSession = Depends(get_db)):
    """
    启动异步 Swagger 导入任务
    """
    logger.info(f"Triggering asynchronous Swagger import for project: {import_data.project_id}")
    
    # 验证项目是否存在
    result = await db.execute(select(Project).where(Project.id == import_data.project_id))
    project = result.scalar_one_or_none()
    if project is None:
        logger.warning(f"Project not found: {import_data.project_id}")
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # 启动 Celery 任务
        task = import_swagger_task.delay(import_data.project_id, import_data.url)
        logger.info(f"Swagger import task started with ID: {task.id}")
        return await create_response(
            data={"task_id": task.id},
            msg="Swagger 导入任务已启动，请稍后查看结果"
        )
    except Exception as e:
        logger.error(f"Failed to start Swagger import task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start background task: {str(e)}")

@router.get("/import-status/{task_id}/", response_model=ResponseModel)
async def get_import_status(task_id: str):
    """
    查询 Swagger 导入任务的状态
    """
    try:
        task_result = AsyncResult(task_id, app=import_swagger_task.app)
        
        response_data = {
            "task_id": task_id,
            "status": task_result.status, # PENDING, PROGRESS, SUCCESS, FAILURE
            "result": None,
            "progress": None
        }
        
        if task_result.status == 'PROGRESS':
            response_data["progress"] = task_result.info
        elif task_result.successful():
            response_data["result"] = task_result.get()
        elif task_result.failed():
            response_data["result"] = {"status": "error", "message": str(task_result.result)}
            
        return await create_response(data=response_data)
    except Exception as e:
        logger.error(f"Error checking task status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/import/{task_id}")
async def websocket_import_progress(websocket: WebSocket, task_id: str):
    """
    WebSocket 实时推送 Swagger 导入进度。
    """
    try:
        await websocket.accept()
    except Exception:
        return

    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    
    # 订阅该任务的消息队列
    channel = f"task:progress:{task_id}"
    await pubsub.subscribe(channel)
    
    try:
        # 先检查任务是否已经完成
        task_result = AsyncResult(task_id, app=import_swagger_task.app)
        if task_result.ready():
            if task_result.successful():
                result = task_result.get()
                await websocket.send_json({
                    "status": "SUCCESS",
                    "progress": 100,
                    "text": result.get("message", "导入成功"),
                    "result": result
                })
            else:
                await websocket.send_json({
                    "status": "FAILURE",
                    "text": str(task_result.result)
                })
            await websocket.close()
            return

        # 持续监听进度更新
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data = json.loads(message['data'])
                await websocket.send_json(data)
                
                # 如果任务状态是完成或失败，退出循环
                if data.get('status') in ['SUCCESS', 'FAILURE']:
                    break
            
            # 也可以主动检查一次任务状态，防止错过最后一条消息
            task_result = AsyncResult(task_id, app=import_swagger_task.app)
            if task_result.ready():
                if task_result.successful():
                    result = task_result.get()
                    await websocket.send_json({
                        "status": "SUCCESS",
                        "progress": 100,
                        "text": result.get("message", "导入成功"),
                        "result": result
                    })
                else:
                    await websocket.send_json({
                        "status": "FAILURE",
                        "text": str(task_result.result)
                    })
                break
                
    except Exception as e:
        logger.error(f"WebSocket 导入进度推送异常: {str(e)}")
    finally:
        await pubsub.unsubscribe(channel)
        await websocket.close()

@router.get("/", response_model=ResponseModel)
async def read_interfaces(
    params: PaginationParams = Depends(),
    name: str | None = Query(None, description="Filter by interface name"),
    module_id: str | None = Query(None, alias="moduleId", description="Filter by module ID"),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Reading interfaces: skip={params.skip}, limit={params.limit}, name={name}, module_id={module_id}")
    
    # 基础查询
    query = select(Interface).options(
        selectinload(Interface.steps),
        selectinload(Interface.module).selectinload(Module.project)
    )
    
    # 计数查询
    count_query = select(func.count()).select_from(Interface)

    # 条件过滤
    if name:
        filter_stmt = or_(
            Interface.name.like(f"%{name}%"),
            Interface.url.like(f"%{name}%")
        )
        query = query.where(filter_stmt)
        count_query = count_query.where(filter_stmt)
        
    if module_id:
        query = query.where(Interface.module_id == module_id)
        count_query = count_query.where(Interface.module_id == module_id)

    # 执行计数查询
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 执行分页查询
    query = query.offset(params.skip).limit(params.limit)
    result = await db.execute(query)
    interfaces = result.scalars().all()
    
    interfaces_data = []
    for interface in interfaces:
        try:
            # 兼容性处理：如果数据库中存储的 body/params/headers/body_schema 是字符串或非字典类型，强制纠正
            for field in ['body', 'params', 'headers', 'body_schema']:
                val = getattr(interface, field)
                
                # 如果是字符串，尝试解析
                if isinstance(val, str):
                    try:
                        parsed_val = json.loads(val)
                        # body 字段允许 dict 或 list，其他字段通常为 dict
                        allowed_types = (dict, list) if field == 'body' else dict
                        if isinstance(parsed_val, allowed_types):
                            setattr(interface, field, parsed_val)
                        else:
                            setattr(interface, field, [] if field == 'body' else {})
                    except Exception:
                        setattr(interface, field, [] if field == 'body' else {})
            
                # 再次校验最终类型
                current_val = getattr(interface, field)
                allowed_types = (dict, list, type(None)) if field == 'body' else (dict, type(None))
                if not isinstance(current_val, allowed_types):
                    setattr(interface, field, [] if field == 'body' else {})

            data = InterfaceRead.model_validate(interface).model_dump()
            # 填充模块名称用于前端显示
            if interface.module:
                data['module_name'] = interface.module.name
            interfaces_data.append(data)
        except Exception as e:
            logger.error(f"Error validating interface {interface.id}: {str(e)}")
            continue
    return await create_response(data={"items": interfaces_data, "total": total})

@router.get("/{interface_id}/", response_model=ResponseModel)
async def read_interface(interface_id: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"Reading interface details: {interface_id}")
    result = await db.execute(
        select(Interface)
        .options(
            selectinload(Interface.steps),
            selectinload(Interface.module)
        )
        .where(Interface.id == interface_id)
    )
    interface = result.scalar_one_or_none()
    if interface is None:
        logger.warning(f"Interface not found: {interface_id}")
        raise HTTPException(status_code=404, detail="Interface not found")
    
    interface_data = InterfaceRead.model_validate(interface).model_dump()
    if interface.module:
        interface_data['module_name'] = interface.module.name
    return await create_response(data=interface_data)

@router.put("/{interface_id}/", response_model=ResponseModel)
async def update_interface(interface_id, interface: InterfaceCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"Updating interface: {interface_id}")
    result = await db.execute(
        select(Interface)
        .options(selectinload(Interface.steps))
        .where(Interface.id == interface_id)
    )
    db_interface = result.scalar_one_or_none()
    if db_interface is None:
        logger.warning(f"Interface not found for update: {interface_id}")
        raise HTTPException(status_code=404, detail="Interface not found")
    if interface.module_id is not None:
        result = await db.execute(select(Module).where(Module.id == interface.module_id))
        module = result.scalar_one_or_none()
        if module is None:
            logger.warning(f"Module not found for interface update: {interface.module_id}")
            raise HTTPException(status_code=404, detail="Module not found")
    updata_data = interface.dict(exclude_unset=True)
    for key, value in updata_data.items():
        setattr(db_interface, key, value)
    await db.commit()
    await db.refresh(db_interface)
    logger.info(f"Interface updated successfully: {interface_id}")
    updated_data = InterfaceRead.from_orm(db_interface).dict()
    return await create_response(data=updated_data)

@router.delete("/{interface_id}/")
async def delete_interface(interface_id: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"Deleting interface: {interface_id}")
    result = await db.execute(
        select(Interface).where(Interface.id == interface_id)
    )
    db_interface = result.scalar_one_or_none()
    if db_interface is None:
        logger.warning(f"Interface not found for deletion: {interface_id}")
        raise HTTPException(status_code=404, detail="Interface not found")
    await db.delete(db_interface)
    await db.commit()
    logger.info(f"Interface deleted successfully: {interface_id}")
    return await create_response(data=None, msg="Interface deleted")

@router.delete("/")
async def delete_interfaces(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Interface))
    interfaces = result.scalars().all()
    if not interfaces:
        raise HTTPException(status_code=404, detail="Interface not found")
    for interface in interfaces:
        await db.delete(interface)
        await db.commit()
    return await create_response(data=None, msg="All Interface deleted successfully")