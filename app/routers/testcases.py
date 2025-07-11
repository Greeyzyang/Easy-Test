from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import insert, delete, update
from sqlalchemy.orm import selectinload
from .users import current_active_user
from app.database import get_db, User
from app.models import Interface, Testcase, TestStep, ExecutionDetail
from app.schemas.testcase import TestcaseCreate, TestcaseRead, TestcaseUpdate
from app.schemas.teststep import TestStepCreate, TestStepRead, TestStepUpdate
from typing import List
from app.utils.response import create_response, ResponseModel

router = APIRouter(prefix="/rest/v1/testcases", tags=["testcases"])

@router.post("/", response_model=ResponseModel)
async def create_testcase(testcase: TestcaseCreate, db: AsyncSession = Depends(get_db)):
    # 创建测试用例
    db_testcase = Testcase(**testcase.dict(exclude={"steps"}))
    db.add(db_testcase)
    await db.commit()
    await db.refresh(db_testcase)
    
    # 创建测试步骤
    if testcase.steps:
        for step_data in testcase.steps:
            # 验证接口是否存在
            result = await db.execute(select(Interface).where(Interface.id == step_data.interface_id))
            if not result.scalar_one_or_none():
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
        .options(selectinload(Testcase.steps).selectinload(TestStep.interface))
        .where(Testcase.id == db_testcase.id)
    )
    db_testcase = result.scalar_one()
    return await create_response(data=TestcaseRead.from_orm(db_testcase))

@router.get("/", response_model=ResponseModel)
async def read_testcases(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    name: str | None = Query(None, description="Filter by testcase name"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Testcase).options(
        selectinload(Testcase.steps).selectinload(TestStep.interface)
    )

    if name:
        query = query.where(Testcase.name.like(f"%{name}%"))

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    testcases = result.scalars().all()
    return await create_response(data=[TestcaseRead.from_orm(testcase) for testcase in testcases])

@router.get("/{testcase_id}/", response_model=ResponseModel)
async def read_testcase(testcase_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Testcase)
        .options(selectinload(Testcase.steps).selectinload(TestStep.interface))
        .where(Testcase.id == testcase_id)
    )
    testcase = result.scalar_one_or_none()
    if not testcase:
        raise HTTPException(status_code=404, detail="Testcase not found")
    return await create_response(data=TestcaseRead.from_orm(testcase))

@router.put("/{testcase_id}/", response_model=ResponseModel)
async def update_testcase(testcase_id: str, testcase: TestcaseUpdate, db: AsyncSession = Depends(get_db)):
    # 检查测试用例是否存在
    result = await db.execute(select(Testcase).where(Testcase.id == testcase_id))
    db_testcase = result.scalar_one_or_none()
    if not db_testcase:
        raise HTTPException(status_code=404, detail="Testcase not found")
    
    # 更新测试用例基本信息
    update_data = testcase.dict(exclude={"steps"}, exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_testcase, key, value)
    
    # 更新测试步骤
    if testcase.steps is not None:
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
        .options(selectinload(Testcase.steps).selectinload(TestStep.interface))
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