from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from .users import current_active_user
from app.database import get_db, User
from app.models import Project, Module, Interface, Testsuite, Testcase
from app.schemas.project import ProjectCreate, ProjectRead
from app.schemas.module import ModuleRead
from typing import List
from app.utils.response import create_response, ResponseModel

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
            selectinload(Project.modules)
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
    skip: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    name: str | None = Query(None, description="Filter by project name"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Project).options(
        selectinload(Project.modules)
    )

    if name:
        query = query.where(Project.name.like(f"%{name}%"))

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    projects = result.scalars().all()
    
    projects_data = [ProjectRead.model_validate(project).model_dump() for project in projects]
    return await create_response(data=projects_data)


@router.get("/{project_id}/", response_model=ResponseModel)
async def read_project(project_id: str, db: AsyncSession = Depends(get_db)):    
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.modules)
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
    result = await db.execute(select(Project).where(Project.id == project_id))
    db_project = result.scalar_one_or_none()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    update_data = project.dict(exclude_unset=True)  
    for key, value in update_data.items():
        setattr(db_project, key, value)
    await db.commit()
    await db.refresh(db_project)
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.modules)
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
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()
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