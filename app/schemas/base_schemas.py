from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal, List
from datetime import datetime
from enum import Enum

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

class TestcaseStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PASSED = "PASSED"
    FAILED = "FAILED"


class VariableSource(str, Enum):
    """变量与断言来源类型"""
    RESPONSE = "RESPONSE"      # 响应体 (默认)
    HEADERS = "HEADERS"        # 响应头 
    COOKIES = "COOKIES"        # Cookie
    BODY = "BODY"              # 请求体
    STATUS = "STATUS"          # 响应状态码
    RESPONSE_TIME = "RESPONSE_TIME" # 响应时间

class TestStatus(str, Enum):
    """测试状态枚举"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PASSED = "PASSED"
    SKIPPED = "SKIPPED"
    STOPPED = "STOPPED"

class ExtractVariableConfig(BaseModel):
    """变量提取配置"""
    name: str = Field(..., description="变量名")
    source: VariableSource = Field(default=VariableSource.RESPONSE, description="数据来源")
    path: str = Field(..., description="提取路径，支持jsonpath或键名")
    description: Optional[str] = Field(None, description="变量描述")

    class Config:
        from_attributes = True


class TestcaseInSuite(BaseModel):
    """在测试套件中使用的简化测试用例信息"""
    id: str
    name: str
    description: Optional[str] = None
    status: TestcaseStatus
    priority: Optional[int] = None
    steps_count: int = 0

    class Config:
        from_attributes = True


class JsonValueAssertionRule(BaseModel):
    """表示一个单一的断言规则"""
    source: VariableSource = Field(default=VariableSource.RESPONSE, description="断言来源")
    path: Optional[str] = Field(default=None, description="JSONPath 表达式 (RESPONSE/BODY) 或 Header Key (HEADERS)")
    value: Any = Field(None, description="预期值")
    operator: Literal[
        "equal", "not_equal", "contains", "not_contains",
        "greater_than", "less_than", "greater_or_equal", "less_or_equal",
        "exists", "not_exists",
        "length_equal", "length_not_equal", "length_greater_than", "length_less_than",
        "length_greater_or_equal", "length_less_or_equal",
        "is_array", "is_dict", "is_string", "is_number", "is_boolean", "is_null", "not_null"
    ] = Field(..., description="比较操作符")
    description: Optional[str] = Field(None, description="断言描述")

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
    body: Optional[Any] = Field(None, description="请求体示例")
    body_schema: Optional[Dict[str, Any]] = Field(None, description="请求体结构定义")
    module_id: str = Field(..., description="所属模块ID")    

class KBQueryRequest(BaseModel):
    question: str
    top_k: int = 4

class PaginationParams(BaseModel):
    """分页查询参数模型"""
    skip: int = Field(0, ge=0, description="跳过的记录数")
    limit: int = Field(10, gt=0, description="返回的最大记录数")
