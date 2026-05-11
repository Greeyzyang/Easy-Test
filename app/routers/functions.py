from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.function import Function
from app.schemas.function import (
    FunctionCreate,
    FunctionUpdate,
    FunctionInDB,
    FunctionRun,
    FunctionRunResult
)
from app.schemas.base_schemas import PaginationParams
from app.utils.response import create_response, ResponseModel
from app.services.function_service import FunctionService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/rest/v1/functions", tags=["functions"])

@router.post("/", response_model=ResponseModel)
async def create_function(
    function: FunctionCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新函数
    
    Args:
        function: 函数创建参数
        db: 数据库会话
        
    Returns:
        创建的函数信息
    """
    logger.info(f"创建函数: {function.name}")
    try:
        function_service = FunctionService(db)
        db_function = await function_service.create_function(
            name=function.name,
            code=function.code,
            description=function.description
        )
        function_dict = FunctionInDB.model_validate(db_function).model_dump()
        logger.info(f"函数创建成功: {db_function.id}")
        return await create_response(data=function_dict)
    except ValueError as e:
        logger.warning(f"创建函数失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=ResponseModel)
async def list_functions(
    params: PaginationParams = Depends(),
    name: Optional[str] = Query(None, description="函数名称过滤"),
    db: AsyncSession = Depends(get_db)
):
    """获取函数列表
    
    Args:
        params: 分页查询参数
        name: 函数名称过滤
        db: 数据库会话
        
    Returns:
        函数列表
    """
    logger.info(f"获取函数列表: skip={params.skip}, limit={params.limit}, name={name}")
    function_service = FunctionService(db)
    functions, total = await function_service.list_functions(params.skip, params.limit, name)
    functions_data = [FunctionInDB.model_validate(f).model_dump(mode='json') for f in functions]
    return await create_response(data={"items": functions_data, "total": total})

@router.get("/{function_id}/", response_model=ResponseModel)
async def get_function(
    function_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取函数详情
    
    Args:
        function_id: 函数ID
        db: 数据库会话
        
    Returns:
        函数详情
    """
    logger.info(f"获取函数详情: {function_id}")
    function_service = FunctionService(db)
    function = await function_service.get_function_by_id(function_id)
    if not function:
        logger.warning(f"函数不存在: {function_id}")
        raise HTTPException(status_code=404, detail="Function not found")
    
    function_dict = FunctionInDB.model_validate(function).model_dump()
    return await create_response(data=function_dict)

@router.put("/{function_id}/", response_model=ResponseModel)
async def update_function(
    function_id: str,
    function: FunctionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新函数
    
    Args:
        function_id: 函数ID
        function: 函数更新参数
        db: 数据库会话
        
    Returns:
        更新后的函数信息
    """
    logger.info(f"更新函数: {function_id}")
    try:
        function_service = FunctionService(db)
        db_function = await function_service.update_function(
            function_id=function_id,
            name=function.name,
            code=function.code,
            description=function.description
        )
        if not db_function:
            logger.warning(f"待更新函数不存在: {function_id}")
            raise HTTPException(status_code=404, detail="Function not found")
        
        function_dict = FunctionInDB.model_validate(db_function).model_dump()
        logger.info(f"函数更新成功: {function_id}")
        return await create_response(data=function_dict)
    except ValueError as e:
        logger.warning(f"更新函数失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{function_id}/", response_model=ResponseModel)
async def delete_function(
    function_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除函数
    
    Args:
        function_id: 函数ID
        db: 数据库会话
        
    Returns:
        删除结果
    """
    logger.info(f"删除函数: {function_id}")
    function_service = FunctionService(db)
    success = await function_service.delete_function(function_id)
    if not success:
        logger.warning(f"待删除函数不存在: {function_id}")
        raise HTTPException(status_code=404, detail="Function not found")
    
    logger.info(f"函数删除成功: {function_id}")
    return await create_response(data=None, msg="Function deleted successfully")

@router.post("/run/", response_model=ResponseModel)
async def run_function(
    request: FunctionRun,
    db: AsyncSession = Depends(get_db)
):
    """运行函数
    
    Args:
        request: 运行请求参数
        db: 数据库会话
        
    Returns:
        运行结果
    """
    logger.info(f"运行函数: {request.name or 'Ad-hoc Code'}, 参数: {request.parameters}")
    function_service = FunctionService(db)
    
    if request.code:
        success, result, stdout, stderr = await function_service.execute_code(
            code=request.code,
            entry_name=request.entry_name,
            args=request.parameters or []
        )
    elif request.name:
        success, result, stdout, stderr = await function_service.execute_function(
            name=request.name,
            args=request.parameters or []
        )
    else:
        raise HTTPException(status_code=400, detail="Either 'name' or 'code' must be provided")
    
    run_result = FunctionRunResult(
        success=success,
        result=result,
        stdout=stdout,
        stderr=stderr
    ).model_dump()
    
    if not success:
        logger.warning(f"函数运行失败: {request.name}, error={stderr}")
    else:
        logger.info(f"函数运行成功: {request.name}")
        
    return await create_response(data=run_result) 