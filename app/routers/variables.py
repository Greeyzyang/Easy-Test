from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List, Optional

from app.database import get_db
from app.models.variable import Variable
from app.schemas.variable import VariableCreate, VariableRead, VariableUpdate
from app.schemas.base_schemas import PaginationParams
from app.utils.logger import get_logger
from app.utils.response import ResponseModel, create_response

logger = get_logger(__name__)

router = APIRouter(prefix="/rest/v1/variables", tags=["variables"])

@router.get("/", response_model=ResponseModel)
async def list_variables(
    params: PaginationParams = Depends(),
    key: Optional[str] = Query(None, description="按变量名模糊搜索"),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"获取变量列表: skip={params.skip}, limit={params.limit}, key={key}")
    query = select(Variable)
    count_query = select(func.count()).select_from(Variable)

    if key:
        filter_stmt = Variable.key.like(f"%{key}%")
        query = query.where(filter_stmt)
        count_query = count_query.where(filter_stmt)

    # 执行计数查询
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 执行分页查询
    query = query.offset(params.skip).limit(params.limit)
    result = await db.execute(query)
    variables = result.scalars().all()
    
    variables_data = [VariableRead.from_orm(var) for var in variables]
    return await create_response(data={"items": variables_data, "total": total})

@router.post("/", response_model=ResponseModel)
async def create_variable(data: VariableCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"创建变量: {data.key}")
    result = await db.execute(select(Variable).where(Variable.key == data.key))
    if result.scalar_one_or_none():
        logger.warning(f"变量名已存在: {data.key}")
        raise HTTPException(status_code=400, detail="变量名已存在")
    var = Variable(key=data.key, value=data.value, description=data.description)
    db.add(var)
    await db.commit()
    await db.refresh(var)
    logger.info(f"变量创建成功: {var.id}")
    return await create_response(data=VariableRead.from_orm(var))

@router.get("/{var_id}/", response_model=ResponseModel)
async def read_variable(var_id: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"获取变量详情: {var_id}")
    result = await db.execute(select(Variable).where(Variable.id == var_id))
    var = result.scalar_one_or_none()
    if not var:
        logger.warning(f"变量不存在: {var_id}")
        raise HTTPException(status_code=404, detail="变量不存在")
    return await create_response(data=VariableRead.from_orm(var))

@router.put("/{var_id}/", response_model=ResponseModel)
async def update_variable(var_id: str, data: VariableUpdate, db: AsyncSession = Depends(get_db)):
    logger.info(f"更新变量: {var_id}")
    result = await db.execute(select(Variable).where(Variable.id == var_id))
    var = result.scalar_one_or_none()
    if not var:
        logger.warning(f"变量不存在: {var_id}")
        raise HTTPException(status_code=404, detail="变量不存在")
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(var, key, value)
    await db.commit()
    await db.refresh(var)
    logger.info(f"变量更新成功: {var_id}")
    return await create_response(data=VariableRead.from_orm(var))

@router.delete("/{var_id}/", response_model=ResponseModel)
async def delete_variable(var_id: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"删除变量: {var_id}")
    result = await db.execute(select(Variable).where(Variable.id == var_id))
    var = result.scalar_one_or_none()
    if not var:
        logger.warning(f"待删除变量不存在: {var_id}")
        raise HTTPException(status_code=404, detail="变量不存在")
    await db.delete(var)
    await db.commit()
    logger.info(f"变量删除成功: {var_id}")
    return await create_response(data=None, msg="变量删除成功")