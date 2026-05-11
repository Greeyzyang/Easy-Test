from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from .users import current_active_user
from app.database import get_db, User
from app.models import Project, Module, Interface, Testsuite, Testcase
from app.schemas.project import ProjectCreate, ProjectRead
from app.schemas.base_schemas import PaginationParams
from app.schemas.module import ModuleRead
from typing import List
from app.utils.response import create_response, ResponseModel
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/rest/v1/projects", tags=["projects"])


@router.post("/", response_model=ResponseModel)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db)):
    db_project = Project(**project.dict())
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.modules),
            selectinload(Project.testsuites)
        )
        .where(Project.id == db_project.id)
    )
    project_with_modules = result.scalar_one_or_none()
    if project_with_modules is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created project with modules")
    project_data = ProjectRead.model_validate(project_with_modules).model_dump()
    project_data['modules'] = [ModuleRead.model_validate(module).model_dump() for module in project_with_modules.modules]
    return await create_response(data=project_data)


@router.get("/", response_model=ResponseModel)
async def read_projects(
    params: PaginationParams = Depends(),
    name: str | None = Query(None, description="Filter by project name"),
    db: AsyncSession = Depends(get_db)
):
    # 基础查询
    query = select(Project).options(
        selectinload(Project.modules),
        selectinload(Project.testsuites)
    )
    
    # 计数查询
    count_query = select(func.count()).select_from(Project)

    if name:
        filter_stmt = Project.name.like(f"%{name}%")
        query = query.where(filter_stmt)
        count_query = count_query.where(filter_stmt)

    # 执行计数查询
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 执行分页查询
    query = query.offset(params.skip).limit(params.limit)
    result = await db.execute(query)
    projects = result.scalars().all()
    
    projects_data = [ProjectRead.model_validate(project).model_dump() for project in projects]
    return await create_response(data={"items": projects_data, "total": total})


@router.get("/{project_id}/", response_model=ResponseModel)
async def read_project(project_id: str, db: AsyncSession = Depends(get_db)):    
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.modules),
            selectinload(Project.testsuites)
        )
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_data = ProjectRead.model_validate(project).model_dump()
    return await create_response(data=project_data)


@router.put("/{project_id}/", response_model=ResponseModel)
async def update_project(
    project_id: str,
    project: ProjectCreate,
    db: AsyncSession = Depends(get_db)):
    logger.info(f"Updating project: {project_id}")
    result = await db.execute(select(Project).where(Project.id == project_id))
    db_project = result.scalar_one_or_none()
    if not db_project:
        logger.warning(f"Project not found for update: {project_id}")
        raise HTTPException(status_code=404, detail="Project not found")
    update_data = project.dict(exclude_unset=True)  
    for key, value in update_data.items():
        setattr(db_project, key, value)
    await db.commit()
    await db.refresh(db_project)
    logger.info(f"Project {project_id} updated successfully")
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.modules),
            selectinload(Project.testsuites)
        )
        .where(Project.id == project_id)
    )
    updated_project = result.scalar_one_or_none()
    if updated_project is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated project")
    project_data = ProjectRead.model_validate(updated_project).model_dump()
    project_data['modules'] = [ModuleRead.model_validate(module).model_dump() for module in updated_project.modules]
    return await create_response(data=project_data)


@router.delete("/{project_id}/")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"Deleting project: {project_id}")
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        logger.warning(f"Project not found for deletion: {project_id}")
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()
    logger.info(f"Project {project_id} deleted successfully")
    return await create_response(data=None, msg="Project deleted successfully")


@router.delete("/")
async def delete_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project))
    projects = result.scalars().all()
    if not projects:
        raise HTTPException(status_code=404, detail="No projects found")
    for project in projects:
        await db.delete(project)
    await db.commit()
    return await create_response(data=None, msg="All Project deleted successfully")