from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from .users import current_active_user
from app.database import get_db, User
from app.models import Interface, Module
from app.schemas.interface import InterfaceCreate, InterfaceRead
from typing import List
from app.utils.response import create_response, ResponseModel

router = APIRouter(prefix="/rest/v1/interfaces", tags=["interfaces"])


@router.post("/", response_model=ResponseModel)
async def create_interface(interface: InterfaceCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Module).where(Module.id == interface.module_id))
    moudle = result.scalar_one_or_none()
    if moudle is None:
        raise HTTPException(status_code=404, detail="Interface not found")
    db_interface = Interface(**interface.dict())
    db.add(db_interface)
    await db.commit()
    await db.refresh(db_interface)
    # 获取完整数据（包括关联的steps）
    result = await db.execute(
        select(Interface)
        .options(selectinload(Interface.steps))
        .where(Interface.id == db_interface.id)
    )
    interface = result.scalar_one_or_none()
    interface_data = InterfaceRead.model_validate(interface).model_dump()
    return await create_response(data=interface_data)

@router.get("/", response_model=ResponseModel)
async def read_interfaces(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, gt=0),
    name: str | None = Query(None, description="Filter by interface name"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Interface).options(
        selectinload(Interface.steps),
        selectinload(Interface.module).selectinload(Module.project)
    )

    if name:
        query = query.where(Interface.name.like(f"%{name}%"))

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    interfaces = result.scalars().all()
    interfaces_data = [InterfaceRead.from_orm(interface).dict() for interface in interfaces]
    return await create_response(data=interfaces_data)

@router.get("/{interface_id}/", response_model=ResponseModel)
async def read_interface(interface_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Interface)
        .options(selectinload(Interface.steps)
        )   
        .where(Interface.id == interface_id)
        )
    interface = result.scalar_one_or_none()
    if interface is None:
        raise HTTPException(status_code=404, detail="Interface not found")
    interface_data = InterfaceRead.from_orm(interface).dict()
    return await create_response(data=interface_data)

@router.put("/{interface_id}/", response_model=ResponseModel)
async def update_interface(interface_id, interface: InterfaceCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Interface)
        .options(selectinload(Interface.steps))
        .where(Interface.id == interface_id)
    )
    db_interface = result.scalar_one_or_none()
    if db_interface is None:
        raise HTTPException(status_code=404, detail="Interface not found")
    if interface.module_id is not None:
        result = await db.execute(select(Module).where(Module.id == interface.module_id))
        module = result.scalar_one_or_none()
        if module is None:
            raise HTTPException(status_code=404, detail="Module not found")
    updata_data = interface.dict(exclude_unset=True)
    for key, value in updata_data.items():
        setattr(db_interface, key, value)
    await db.commit()
    await db.refresh(db_interface)
    updated_data = InterfaceRead.from_orm(db_interface).dict()
    return await create_response(data=updated_data)

@router.delete("/{interface_id}/")
async def delete_interface(interface_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
            select(Interface)
            .options(selectinload(Interface.steps)
            ).where(Interface.id == interface_id))
    interface = result.scalar_one_or_none()
    if interface is None:
        raise HTTPException(status_code=404, detail="Interface not found")
    await db.delete(interface)
    await db.commit()
    return await create_response(data=None, msg=f"Interface {interface_id} deleted successfully")

@router.delete("/")
async def delete_interfaces(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Interface))
    interfaces = result.scalars().all()
    if not interfaces:
        raise HTTPException(status_code=404, detail="Interface not found")
    for interface in interfaces:
        await db.delete(interface)
        await db.commit()
    return await create_response(data=None, msg="All Interface deleted successfully")