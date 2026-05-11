from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal, List
from enum import Enum
from .base_schemas import TestStepStatus, RequestType, VariableSource, ExtractVariableConfig
from .interface import InterfaceRead
from datetime import datetime

# 定义 JSON 值断言规则的模型
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
    description: Optional[str] = Field(None, description="断言描述") # 可选的描述字段

class ExtractVariableConfig(BaseModel):
    """变量提取配置"""
    name: str = Field(..., description="变量名")
    source: VariableSource = Field(default=VariableSource.RESPONSE, description="数据来源")
    path: str = Field(..., description="提取路径，支持jsonpath或键名")
    description: Optional[str] = Field(None, description="变量描述")

    class Config:
        from_attributes = True

class TestStepBase(BaseModel):
    name: str = Field(..., description="步骤名称")
    description: Optional[str] = Field(None, description="步骤描述")
    interface_id: str = Field(..., description="关联的接口ID")
    
    # 请求配置（可选，如果不提供则使用接口的默认配置）
    request_type: Optional[RequestType] = Field(None, description="请求体类型")
    headers: Optional[Dict[str, Any]] = Field(None, description="请求头配置")
    body: Optional[Dict[str, Any]] = Field(None, description="请求体配置")
    params: Optional[Dict[str, Any]] = Field(None, description="请求参数配置")
    file_config: Optional[Dict[str, Any]] = Field(None, description="文件上传配置")
    
    # 验证配置
    expected_response_code: Optional[int] = Field(None, description="预期响应码") # 保留状态码字段
    assertions: Optional[List[JsonValueAssertionRule]] = Field(None, description="JSON值断言规则列表") # 新增 assertions 列表
    
    # 变量提取
    extract_variables: Optional[List[ExtractVariableConfig]]  = Field(None, description="变量提取配置")
    
    # 执行状态
    status: Optional[TestStepStatus] = Field(TestStepStatus.PENDING, description="执行状态")
    
    # 新增的order字段
    order: int = Field(0, description="测试步骤的顺序")
    
    # 执行结果相关字段 (这些字段通常在执行后由后端填充)
    actual_response: Optional[Dict[str, Any]] = Field(None, description="实际响应结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    duration: Optional[float] = Field(None, description="执行时长(ms")
    retry_count: Optional[int] = Field(0, description="重试次数")

    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None

class TestStepCreate(TestStepBase):
    """创建测试步骤的模型"""
    testcase_id: Optional[str] = None  # 设为可选，因为创建时可能还不知道 testcase_id

class TestStepUpdate(TestStepBase):
    id: Optional[str] = None # 更新时可能需要ID来识别步骤


class TestStepInTestcase(TestStepBase):
    """在测试用例中使用的测试步骤信息"""
    id: str
    testcase_id: str

    class Config:
        from_attributes = True

class TestStepDetail(TestStepBase):
    """测试步骤详细信息"""
    id: str = Field(..., description="步骤ID")
    testcase_id: str = Field(..., description="所属测试用例ID")
    interface: InterfaceRead

    class Config:
        from_attributes = True

class TestStepRead(TestStepBase):
    """读取测试步骤的模型"""
    id: str
    testcase_id: str
    interface: InterfaceRead

    class Config:
        from_attributes = True