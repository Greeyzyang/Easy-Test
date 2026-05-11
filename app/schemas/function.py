from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime

class FunctionBase(BaseModel):
    name: str
    description: Optional[str] = None
    code: str
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None

class FunctionCreate(FunctionBase):
    pass

class FunctionUpdate(FunctionBase):
    pass

class FunctionInDB(FunctionBase):
    id: str

    class Config:
        from_attributes = True

class FunctionList(BaseModel):
    total: int
    items: List[FunctionInDB]

class FunctionRun(BaseModel):
    """函数执行请求模型"""
    name: Optional[str] = None
    code: Optional[str] = None
    entry_name: Optional[str] = None
    parameters: Optional[List[Any]] = None

class FunctionRunResult(BaseModel):
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None 