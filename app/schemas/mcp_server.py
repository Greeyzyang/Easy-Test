from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class MCPServerBase(BaseModel):
    name: str
    description: Optional[str] = None
    transport: str = "stdio"
    command: Optional[str] = None
    args: List[str] = []
    env: Dict[str, str] = {}
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = {}
    enabled: bool = True


class MCPServerCreate(MCPServerBase):
    pass


class MCPServerUpdate(MCPServerBase):
    pass


class MCPServerInDB(MCPServerBase):
    id: str
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None

    class Config:
        from_attributes = True
