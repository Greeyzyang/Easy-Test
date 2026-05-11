from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from .base_schemas import RequestType


class InterfaceBase(BaseModel):
    """接口基础字段，所有 Schema 共享"""
    name: str
    url: str
    method: str = "GET"
    description: Optional[str] = None
    version: Optional[str] = None
    request_type: Optional[RequestType] = Field(None, description="请求体类型")
    headers: Optional[Dict[str, Any]] = Field(default_factory=dict, description="请求头")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="请求参数")
    body: Optional[Any] = None
    body_schema: Optional[Dict[str, Any]] = None
    module_id: str = Field(..., description="所属模块ID")

    @field_validator("headers", "params", mode="before")
    @classmethod
    def handle_none_or_default(cls, v):
        if v is None:
            return {}
        return v

    @field_validator("request_type", mode="before")
    @classmethod
    def handle_none_request_type(cls, v):
        if v is None:
            return RequestType.JSON
        return v


class InterfaceCreate(InterfaceBase):
    """创建时接受的字段"""
    pass


class InterfaceUpdate(BaseModel):
    """更新时接受的字段（全部可选）"""
    name: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    request_type: Optional[RequestType] = None
    headers: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None
    body: Optional[Any] = None
    body_schema: Optional[Dict[str, Any]] = None
    module_id: Optional[str] = None


class InterfaceRead(InterfaceBase):
    """API 响应时使用的完整 Schema"""
    id: str
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    module_name: Optional[str] = None

    class Config:
        from_attributes = True


class SwaggerImportRequest(BaseModel):
    url: str
    project_id: str
