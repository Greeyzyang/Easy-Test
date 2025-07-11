from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import insert, delete, update
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import TestStep, Interface, Testcase
from app.schemas.teststep import TestStepCreate, TestStepRead, TestStepUpdate
from app.utils.response import create_response, ResponseModel

router = APIRouter(prefix="/rest/v1/teststeps", tags=["teststeps"])

@router.post("/", response_model=ResponseModel)
async def create_teststep(teststep: TestStepCreate, db: AsyncSession = Depends(get_db)):
    # 验证接口是否存在
    result = await db.execute(select(Interface).where(Interface.id == teststep.interface_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Interface {teststep.interface_id} not found")
    
    # 验证测试用例是否存在
    result = await db.execute(select(Testcase).where(Testcase.id == teststep.testcase_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Testcase {teststep.testcase_id} not found")
    
    db_teststep = TestStep(**teststep.dict())
    db.add(db_teststep)
    await db.commit()
    await db.refresh(db_teststep)
    
    # 重新查询以获取关联数据
    result = await db.execute(
        select(TestStep)
        .options(selectinload(TestStep.interface))
        .where(TestStep.id == db_teststep.id)
    )
    db_teststep = result.scalar_one_or_none()
    return await create_response(data=TestStepRead.from_orm(db_teststep))

@router.get("/", response_model=ResponseModel)
async def read_teststeps(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0),
    name: str | None = Query(None, description="Filter by test step name"),
    db: AsyncSession = Depends(get_db)
):
    """获取测试步骤列表"""
    # 构建基础查询语句
    query = select(TestStep).options(selectinload(TestStep.interface))

    # 如果提供了 name 参数，添加过滤条件
    if name:
        # 使用 SQLAlchemy 的 like 进行模糊匹配
        query = query.where(TestStep.name.like(f"%{name}%"))

    # 添加分页
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    steps = result.scalars().all()
    return await create_response(data=[TestStepRead.from_orm(step) for step in steps])

@router.get("/{teststep_id}/", response_model=ResponseModel)
async def read_teststep(teststep_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个测试步骤的详细信息"""
    result = await db.execute(
        select(TestStep)
        .options(selectinload(TestStep.interface))
        .where(TestStep.id == teststep_id)
    )
    teststep = result.scalar_one_or_none()
    if not teststep:
        raise HTTPException(status_code=404, detail="TestStep not found")
    return await create_response(data=TestStepRead.from_orm(teststep))

@router.put("/{teststep_id}/", response_model=ResponseModel)
async def update_teststep(teststep_id: str, teststep: TestStepUpdate, db: AsyncSession = Depends(get_db)):
    # 检查步骤是否存在
    result = await db.execute(select(TestStep).where(TestStep.id == teststep_id))
    db_teststep = result.scalar_one_or_none()
    if not db_teststep:
        raise HTTPException(status_code=404, detail="TestStep not found")
    
    # 如果更新了接口ID，验证新接口是否存在
    if teststep.interface_id:
        result = await db.execute(select(Interface).where(Interface.id == teststep.interface_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Interface {teststep.interface_id} not found")
    
    # 更新数据
    update_data = teststep.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_teststep, key, value)
    
    await db.commit()
    await db.refresh(db_teststep)
    
    # 重新查询以获取关联数据
    result = await db.execute(
        select(TestStep)
        .options(selectinload(TestStep.interface))
        .where(TestStep.id == teststep_id)
    )
    updated_teststep = result.scalar_one()
    return await create_response(data=TestStepRead.from_orm(updated_teststep))

@router.delete("/{teststep_id}/", response_model=ResponseModel)
async def delete_teststep(teststep_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TestStep).where(TestStep.id == teststep_id))
    teststep = result.scalar_one_or_none()
    if not teststep:
        raise HTTPException(status_code=404, detail="TestStep not found")
    
    await db.delete(teststep)
    await db.commit()
    return await create_response(data=None, msg=f"TestStep {teststep_id} deleted successfully")