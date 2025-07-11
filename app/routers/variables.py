from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from app.models.variable import Variable
from app.schemas.variable import VariableCreate, VariableUpdate, VariableRead
from app.database import get_db
from app.utils.response import create_response, ResponseModel

router = APIRouter(prefix="/rest/v1/variables", tags=["variables"])

@router.get("/", response_model=ResponseModel)
async def list_variables(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0),
    key: Optional[str] = Query(None, description="按变量名模糊搜索"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Variable)
    if key:
        query = query.where(Variable.key.like(f"%{key}%"))
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    variables = result.scalars().all()
    return await create_response(data=[VariableRead.from_orm(var) for var in variables])

@router.post("/", response_model=ResponseModel)
async def create_variable(data: VariableCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Variable).where(Variable.key == data.key))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="变量名已存在")
    var = Variable(key=data.key, value=data.value, description=data.description)
    db.add(var)
    await db.commit()
    await db.refresh(var)
    return await create_response(data=VariableRead.from_orm(var))

@router.get("/{var_id}/", response_model=ResponseModel)
async def read_variable(var_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Variable).where(Variable.id == var_id))
    var = result.scalar_one_or_none()
    if not var:
        raise HTTPException(status_code=404, detail="变量不存在")
    return await create_response(data=VariableRead.from_orm(var))

@router.put("/{var_id}/", response_model=ResponseModel)
async def update_variable(var_id: str, data: VariableUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Variable).where(Variable.id == var_id))
    var = result.scalar_one_or_none()
    if not var:
        raise HTTPException(status_code=404, detail="变量不存在")
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(var, key, value)
    await db.commit()
    await db.refresh(var)
    return await create_response(data=VariableRead.from_orm(var))

@router.delete("/{var_id}/", response_model=ResponseModel)
async def delete_variable(var_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Variable).where(Variable.id == var_id))
    var = result.scalar_one_or_none()
    if not var:
        raise HTTPException(status_code=404, detail="变量不存在")
    await db.delete(var)
    await db.commit()
    return await create_response(data=None, msg=f"Variable {var_id} deleted successfully") 