from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import insert, delete
from app.database import get_db
from app.models import Project, Module, Testcase, TestStep
from app.models import testcase_to_module
from app.schemas.module import ModuleCreate, ModuleRead, ModuleDetail
from app.schemas.testcase import TestcaseRead, TestcaseDetail
from app.schemas.teststep import TestStepDetail
from typing import List
from app.utils.response import create_response, ResponseModel

router = APIRouter(prefix="/rest/v1/modules", tags=["modules"])

@router.post("/", response_model=ResponseModel)
async def create_module(module: ModuleCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == module.project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    db_module = Module(**module.dict())
    db.add(db_module)
    await db.commit()
    await db.refresh(db_module)
    result = await db.execute(
        select(Module)
        .options(selectinload(Module.testcases))
        .where(Module.id == db_module.id)
    )
    module_data = result.scalar_one_or_none()
    if module_data is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created module")
    module_dict = ModuleRead.model_validate(module_data).model_dump()
    module_dict['testcases'] = [TestcaseRead.model_validate(tc).model_dump() for tc in module_data.testcases]
    return await create_response(data=module_dict)

@router.get("/", response_model=ResponseModel)
async def read_modules(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    name: str | None = Query(None, description="Filter by module name"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Module).options(
        selectinload(Module.project),
        selectinload(Module.testcases)
        .selectinload(Testcase.steps)
        .selectinload(TestStep.interface)
    )

    if name:
        query = query.where(Module.name.like(f"%{name}%"))

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    modules = result.scalars().all()
    modules_data = []
    for module in modules:
        module_dict = ModuleRead.model_validate(module).model_dump()
        modules_data.append(module_dict)
    return await create_response(data=modules_data)

@router.get("/{module_id}/", response_model=ResponseModel)
async def read_module(module_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Module)
        .options(
            selectinload(Module.testcases)
            .selectinload(Testcase.steps)
            .selectinload(TestStep.interface)
        )
        .where(Module.id == module_id)
    )
    module = result.scalar_one_or_none()
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found")
    module_dict = ModuleDetail.model_validate(module).model_dump()
    return await create_response(data=module_dict)

@router.put("/{module_id}/", response_model=ResponseModel)
async def update_module(module_id: str, module: ModuleCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Module).where(Module.id == module_id))
    db_module = result.scalar_one_or_none()
    if not db_module:
        raise HTTPException(status_code=404, detail="Module not found")
    result = await db.execute(select(Project).where(Project.id == module.project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Associated project not found")
    update_data = module.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_module, key, value)
    await db.commit()
    await db.refresh(db_module)
    result = await db.execute(
        select(Module)
        .options(selectinload(Module.testcases))
        .where(Module.id == module_id)
    )
    updated_module = result.scalar_one_or_none()
    if updated_module is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated module")
    module_dict = ModuleRead.model_validate(updated_module).model_dump()
    module_dict['testcases'] = [TestcaseRead.model_validate(tc).model_dump() for tc in updated_module.testcases]
    return await create_response(data=module_dict)

@router.delete("/{module_id}/")
async def delete_module(module_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Module)
        .options(selectinload(Module.testcases))
        .where(Module.id == module_id)
    )
    module = result.scalar_one_or_none()
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found")
    await db.delete(module)
    await db.commit()
    return await create_response(data=None, msg="Module deleted successfully")

@router.delete("/")
async def delete_modules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Module))
    modules = result.scalars().all()
    if not modules:
        raise HTTPException(status_code=404, detail="modules not found")
    for module in modules:
        await db.delete(module)
        await db.commit()
    return await create_response(data=None, msg="Module deleted successfully")

@router.post("/{module_id}/testcases/{testcase_id}/", response_model=ResponseModel)
async def add_testcase_to_module(
    module_id: str,
    testcase_id: str,
    db: AsyncSession = Depends(get_db)
):
    # 检查 module 是否存在
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    # 检查 testcase 是否存在
    result = await db.execute(select(Testcase).where(Testcase.id == testcase_id))
    testcase = result.scalar_one_or_none()
    if not testcase:
        raise HTTPException(status_code=404, detail="Testcase not found")
    
    # 检查是否已经存在关联
    result = await db.execute(
        select(testcase_to_module)
        .where(
            testcase_to_module.c.module_id == module_id,
            testcase_to_module.c.testcase_id == testcase_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Testcase already exists in module")
    
    # 添加关联
    await db.execute(
        insert(testcase_to_module).values(
            module_id=module_id,
            testcase_id=testcase_id
        )
    )
    await db.commit()
    
    # 加载完整的 module 数据，包括 testcases 和它们的 steps
    result = await db.execute(
        select(Module)
        .options(
            selectinload(Module.testcases)
            .selectinload(Testcase.steps)
            .selectinload(TestStep.interface)
        )
        .where(Module.id == module_id)
    )
    updated_module = result.scalar_one_or_none()
    
    # 使用 Pydantic 模型进行序列化
    module_dict = ModuleDetail.model_validate(updated_module).model_dump()
    return await create_response(data=module_dict)

@router.delete("/{module_id}/testcases/{testcase_id}/", response_model=ResponseModel)
async def remove_testcase_from_module(
    module_id: str,
    testcase_id: str,
    db: AsyncSession = Depends(get_db)
):
    # 检查 module 是否存在
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    # 检查 testcase 是否存在
    result = await db.execute(select(Testcase).where(Testcase.id == testcase_id))
    testcase = result.scalar_one_or_none()
    if not testcase:
        raise HTTPException(status_code=404, detail="Testcase not found")
    
    # 检查关联是否存在
    result = await db.execute(
        select(testcase_to_module)
        .where(
            testcase_to_module.c.module_id == module_id,
            testcase_to_module.c.testcase_id == testcase_id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Testcase not found in module")
    
    # 删除关联
    await db.execute(
        delete(testcase_to_module)
        .where(
            testcase_to_module.c.module_id == module_id,
            testcase_to_module.c.testcase_id == testcase_id
        )
    )
    await db.commit()
    
    # 返回更新后的 module 信息
    result = await db.execute(
        select(Module)
        .options(selectinload(Module.testcases))
        .where(Module.id == module_id)
    )
    updated_module = result.scalar_one_or_none()
    module_dict = ModuleDetail.model_validate(updated_module).model_dump()
    return await create_response(data=module_dict)

@router.put("/{module_id}/testcases/", response_model=ResponseModel)
async def update_module_testcases(
    module_id: str,
    testcase_ids: List[str],
    db: AsyncSession = Depends(get_db)
):
    # 检查 module 是否存在
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    
    # 检查所有 testcase 是否存在
    for testcase_id in testcase_ids:
        result = await db.execute(select(Testcase).where(Testcase.id == testcase_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Testcase {testcase_id} not found")
    
    # 删除所有现有关联
    await db.execute(
        delete(testcase_to_module)
        .where(testcase_to_module.c.module_id == module_id)
    )
    
    # 添加新的关联
    if testcase_ids:
        await db.execute(
            insert(testcase_to_module),
            [{"module_id": module_id, "testcase_id": testcase_id} for testcase_id in testcase_ids]
        )
    await db.commit()
    
    # 返回更新后的 module 信息
    result = await db.execute(
        select(Module)
        .options(selectinload(Module.testcases))
        .where(Module.id == module_id)
    )
    updated_module = result.scalar_one_or_none()
    module_dict = ModuleRead.model_validate(updated_module).model_dump()
    module_dict['testcases'] = [TestcaseRead.model_validate(tc).model_dump() for tc in updated_module.testcases]
    return await create_response(data=module_dict)
