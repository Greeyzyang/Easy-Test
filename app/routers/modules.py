from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import insert, delete, func
from app.database import get_db
from app.models import Project, Module, Testcase, TestStep
# from app.models import testcase_to_module
from app.schemas.module import ModuleCreate, ModuleRead, ModuleDetail
from app.schemas.base_schemas import PaginationParams
from app.schemas.testcase import TestcaseRead, TestcaseDetail
from app.schemas.teststep import TestStepDetail
from typing import List
from app.utils.response import create_response, ResponseModel

from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/rest/v1/modules", tags=["modules"])

@router.post("/", response_model=ResponseModel)
async def create_module(module: ModuleCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"Creating module: {module.name} in project {module.project_id}")
    result = await db.execute(select(Project).where(Project.id == module.project_id))
    project = result.scalar_one_or_none()
    if project is None:
        logger.warning(f"Project not found for module creation: {module.project_id}")
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
        logger.error(f"Failed to retrieve created module: {db_module.id}")
        raise HTTPException(status_code=500, detail="Failed to retrieve created module")
    module_dict = ModuleRead.model_validate(module_data).model_dump()
    module_dict['testcases'] = [TestcaseRead.model_validate(tc).model_dump() for tc in module_data.testcases]
    logger.info(f"Module created successfully: {db_module.id}")
    return await create_response(data=module_dict)

@router.get("/", response_model=ResponseModel)
async def read_modules(
    params: PaginationParams = Depends(),
    name: str | None = Query(None, description="Filter by module name"),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Reading modules: skip={params.skip}, limit={params.limit}, name={name}")
    
    # 基础查询
    query = select(Module).options(
        selectinload(Module.project),
        selectinload(Module.testcases)
        .selectinload(Testcase.steps)
        .selectinload(TestStep.interface)
    )
    
    # 计数查询
    count_query = select(func.count()).select_from(Module)

    if name:
        filter_stmt = Module.name.like(f"%{name}%")
        query = query.where(filter_stmt)
        count_query = count_query.where(filter_stmt)

    # 执行计数查询
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 执行分页查询
    query = query.offset(params.skip).limit(params.limit)
    result = await db.execute(query)
    modules = result.scalars().all()
    
    modules_data = []
    for module in modules:
        module_dict = ModuleRead.model_validate(module).model_dump()
        modules_data.append(module_dict)
    return await create_response(data={"items": modules_data, "total": total})

@router.get("/{module_id}/", response_model=ResponseModel)
async def read_module(module_id: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"Reading module details: {module_id}")
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
        logger.warning(f"Module not found: {module_id}")
        raise HTTPException(status_code=404, detail="Module not found")
    module_dict = ModuleDetail.model_validate(module).model_dump()
    return await create_response(data=module_dict)

@router.put("/{module_id}/", response_model=ResponseModel)
async def update_module(module_id: str, module: ModuleCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"Updating module: {module_id}")
    result = await db.execute(select(Module).where(Module.id == module_id))
    db_module = result.scalar_one_or_none()
    if not db_module:
        logger.warning(f"Module not found for update: {module_id}")
        raise HTTPException(status_code=404, detail="Module not found")
    result = await db.execute(select(Project).where(Project.id == module.project_id))
    project = result.scalar_one_or_none()
    if project is None:
        logger.warning(f"Project not found for module update: {module.project_id}")
        raise HTTPException(status_code=404, detail="Associated project not found")
    update_data = module.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_module, key, value)
    await db.commit()
    await db.refresh(db_module)
    logger.info(f"Module {module_id} updated successfully")
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
    logger.info(f"Adding testcase {testcase_id} to module {module_id}")
    # 检查 module 是否存在
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        logger.warning(f"Module not found for testcase association: {module_id}")
        raise HTTPException(status_code=404, detail="Module not found")
    
    # 检查 testcase 是否存在
    result = await db.execute(select(Testcase).where(Testcase.id == testcase_id))
    testcase = result.scalar_one_or_none()
    if not testcase:
        logger.warning(f"Testcase not found for module association: {testcase_id}")
        raise HTTPException(status_code=404, detail="Testcase not found")
    
    # 检查是否已经存在关联
    if testcase.module_id == module_id:
        logger.warning(f"Testcase {testcase_id} already exists in module {module_id}")
        raise HTTPException(status_code=400, detail="Testcase already exists in module")
    
    # 更新关联
    testcase.module_id = module_id
    await db.commit()
    logger.info(f"Successfully added testcase {testcase_id} to module {module_id}")
    
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
    if testcase.module_id != module_id:
        raise HTTPException(status_code=400, detail="Testcase not found in module")
    
    # 删除关联
    testcase.module_id = None
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
    
    # 清空当前模块的所有关联 (将 module_id 设为 None)
    await db.execute(
        update(Testcase)
        .where(Testcase.module_id == module_id)
        .values(module_id=None)
    )
    
    # 添加新的关联
    if testcase_ids:
        await db.execute(
            update(Testcase)
            .where(Testcase.id.in_(testcase_ids))
            .values(module_id=module_id)
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
