from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime

class TestStepStatus(str, Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"

class InterfaceMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

class RequestType(str, Enum):
    JSON = "JSON"
    FORM = "FORM"
    FILE = "FILE"

class TestcaseStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PASSED = "PASSED"
    FAILED = "FAILED"


class VariableSource(str, Enum):
    """变量来源类型"""
    RESPONSE = "RESPONSE"      # 响应体
    HEADERS = "HEADERS"        # 响应头 
    COOKIES = "COOKIES"      # Cookie
    BODY = "BODY"            # 请求体

class TestStatus(str, Enum):
    """测试状态枚举"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PASSED = "PASSED"
    SKIPPED = "SKIPPED"

class ExtractVariableConfig(BaseModel):
    """变量提取配置"""
    name: str = Field(..., description="变量名")
    source: VariableSource = Field(default=VariableSource.RESPONSE, description="数据来源")
    path: str = Field(..., description="提取路径，支持jsonpath或键名")
    description: Optional[str] = Field(None, description="变量描述")

    class Config:
        from_attributes = True 

class BaseInterface(BaseModel):
    """接口基础信息"""
    id: Optional[str] = None
    name: str
    url: str
    method: str
    description: Optional[str] = None
    version: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    request_type: Optional[RequestType] = Field(None, description="请求体类型")
    headers: Optional[Dict[str, Any]] = Field(None, description="请求头")
    params: Optional[Dict[str, Any]] = Field(None, description="请求参数")
    body: Optional[Dict[str, Any]] = Field(None, description="请求体")
    module_id: str = Field(..., description="所属模块ID")    