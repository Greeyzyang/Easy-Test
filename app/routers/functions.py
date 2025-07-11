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
from app.utils.response import create_response, ResponseModel
from app.services.function_service import FunctionService

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
    try:
        function_service = FunctionService(db)
        db_function = await function_service.create_function(
            name=function.name,
            code=function.code,
            description=function.description
        )
        function_dict = FunctionInDB.model_validate(db_function).model_dump()
        return await create_response(data=function_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=ResponseModel)
async def list_functions(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(10, ge=1, le=100, description="返回的记录数"),
    name: Optional[str] = Query(None, description="函数名称过滤"),
    db: AsyncSession = Depends(get_db)
):
    """获取函数列表
    
    Args:
        skip: 跳过的记录数
        limit: 返回的记录数
        name: 函数名称过滤
        db: 数据库会话
        
    Returns:
        函数列表
    """
    function_service = FunctionService(db)
    functions = await function_service.list_functions(skip, limit, name)
    functions_data = [FunctionInDB.model_validate(f).model_dump(mode='json') for f in functions]
    return await create_response(data=functions_data)

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
    function_service = FunctionService(db)
    function = await function_service.get_function_by_id(function_id)
    if not function:
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
    try:
        function_service = FunctionService(db)
        db_function = await function_service.update_function(
            function_id=function_id,
            name=function.name,
            code=function.code,
            description=function.description
        )
        function_dict = FunctionInDB.model_validate(db_function).model_dump()
        return await create_response(data=function_dict)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

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
    function_service = FunctionService(db)
    success = await function_service.delete_function(function_id)
    if not success:
        raise HTTPException(status_code=404, detail="Function not found")
    
    return await create_response(data=None, msg="Function deleted successfully")

@router.post("/run/", response_model=ResponseModel)
async def run_function(
    function_run: FunctionRun,
    db: AsyncSession = Depends(get_db)
):
    """执行函数
    
    Args:
        function_run: 函数执行参数
        db: 数据库会话
        
    Returns:
        函数执行结果
    """
    function_service = FunctionService(db)
    success, result, stdout, stderr = await function_service.execute_function(
        name=function_run.name,
        args=function_run.parameters or []
    )
    
    run_result = FunctionRunResult(
        success=success,
        result=result,
        stdout=stdout,
        stderr=stderr
    )
    
    return await create_response(data=run_result.model_dump()) 