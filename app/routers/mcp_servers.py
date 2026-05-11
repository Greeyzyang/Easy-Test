from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.mcp_server import MCPServer
from app.schemas.mcp_server import MCPServerCreate, MCPServerUpdate, MCPServerInDB
from app.schemas.base_schemas import PaginationParams
from app.utils.response import create_response, ResponseModel
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/rest/v1/mcp-servers", tags=["mcp-servers"])


@router.post("/", response_model=ResponseModel)
async def create_mcp_server(
    mcp_server: MCPServerCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建 MCP Server 配置"""
    logger.info(f"创建 MCP Server: {mcp_server.name}")
    existing = await db.execute(select(MCPServer).where(MCPServer.name == mcp_server.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"MCP Server '{mcp_server.name}' 已存在")

    db_server = MCPServer(**mcp_server.model_dump())
    db.add(db_server)
    await db.commit()
    await db.refresh(db_server)
    return await create_response(data=MCPServerInDB.model_validate(db_server).model_dump())


@router.get("/", response_model=ResponseModel)
async def list_mcp_servers(
    params: PaginationParams = Depends(),
    name: Optional[str] = Query(None, description="服务器名称过滤"),
    db: AsyncSession = Depends(get_db)
):
    """获取 MCP Server 列表"""
    query = select(MCPServer)
    count_query = select(func.count()).select_from(MCPServer)

    if name:
        filter_stmt = MCPServer.name.like(f"%{name}%")
        query = query.where(filter_stmt)
        count_query = count_query.where(filter_stmt)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset(params.skip).limit(params.limit)
    result = await db.execute(query)
    servers = result.scalars().all()

    servers_data = [MCPServerInDB.model_validate(s).model_dump(mode='json') for s in servers]
    return await create_response(data={"items": servers_data, "total": total})


@router.get("/{server_id}/", response_model=ResponseModel)
async def get_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取 MCP Server 详情"""
    logger.info(f"获取 MCP Server 详情: {server_id}")
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    return await create_response(data=MCPServerInDB.model_validate(server).model_dump())


@router.put("/{server_id}/", response_model=ResponseModel)
async def update_mcp_server(
    server_id: str,
    mcp_server: MCPServerUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新 MCP Server"""
    logger.info(f"更新 MCP Server: {server_id}")
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    db_server = result.scalar_one_or_none()
    if not db_server:
        raise HTTPException(status_code=404, detail="MCP Server not found")

    existing = await db.execute(
        select(MCPServer).where(MCPServer.name == mcp_server.name, MCPServer.id != server_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"MCP Server '{mcp_server.name}' 已存在")

    for key, value in mcp_server.model_dump().items():
        setattr(db_server, key, value)

    await db.commit()
    await db.refresh(db_server)
    return await create_response(data=MCPServerInDB.model_validate(db_server).model_dump())


@router.delete("/{server_id}/", response_model=ResponseModel)
async def delete_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除 MCP Server"""
    logger.info(f"删除 MCP Server: {server_id}")
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    db_server = result.scalar_one_or_none()
    if not db_server:
        raise HTTPException(status_code=404, detail="MCP Server not found")

    await db.delete(db_server)
    await db.commit()
    return await create_response(data=None, msg="MCP Server deleted successfully")


@router.patch("/{server_id}/toggle/", response_model=ResponseModel)
async def toggle_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """切换 MCP Server 启用/禁用状态"""
    logger.info(f"切换 MCP Server 状态: {server_id}")
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    db_server = result.scalar_one_or_none()
    if not db_server:
        raise HTTPException(status_code=404, detail="MCP Server not found")

    db_server.enabled = not db_server.enabled
    await db.commit()
    await db.refresh(db_server)
    return await create_response(
        data={"id": db_server.id, "enabled": db_server.enabled},
        msg=f"MCP Server {'启用' if db_server.enabled else '禁用'}成功"
    )
