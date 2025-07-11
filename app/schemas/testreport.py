from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.base_schemas import TestStatus, BaseInterface

class TestcaseRead(BaseModel):
    """测试用例基础信息"""
    id: str
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True

class StepResult(BaseModel):
    """测试步骤执行结果"""
    id: str
    step_id: str
    step_name: str
    status: TestStatus
    start_time: datetime
    end_time: datetime
    duration: float
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    order: int = 0

    class Config:
        from_attributes = True

class TestcaseResult(BaseModel):
    """测试用例执行结果"""
    id: str
    name: str
    description: Optional[str] = None
    status: TestStatus
    duration: float
    steps: List[StepResult]

    class Config:
        from_attributes = True

class TestsuiteRead(BaseModel):
    """测试套件信息"""
    id: str
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True

class TestreportBase(BaseModel):
    """测试报告基础信息"""
    name: str
    description: Optional[str] = None
    testsuite_id: str
    testsuite_name: str
    status: TestStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: float
    total_cases: int
    passed_cases: int
    failed_cases: int
    skipped_cases: int  # 新增
    pass_rate: float

class TestreportCreate(TestreportBase):
    """创建测试报告请求"""
    pass

class TestreportRead(TestreportBase):
    """测试报告列表项"""
    id: str

    class Config:
        from_attributes = True

class TestreportDetail(TestreportRead):
    """测试报告详情"""
    case_results: List[TestcaseResult]

    class Config:
        from_attributes = True

class ExecutionDetailBase(BaseModel):
    """执行详情基础信息"""
    testreport_id: str
    testcase_id: str
    step_id: str
    step_name: str
    status: TestStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: float
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class ExecutionDetailCreate(ExecutionDetailBase):
    """创建执行详情请求"""
    pass

class ExecutionDetailRead(ExecutionDetailBase):
    """执行详情响应"""
    id: str

    class Config:
        from_attributes = True

class TestcaseDetailRead(BaseModel):
    testcase: TestcaseRead
    interface: BaseInterface
    detail: ExecutionDetailRead

    class Config:
        from_attributes = True

class TestreportListRead(BaseModel):
    id: str
    name: str
    testsuite_id: str
    testsuite_name: str  # 新增
    status: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration: float
    total_cases: int
    passed_cases: int
    failed_cases: int
    skipped_cases: int
    pass_rate: int

    class Config:
        from_attributes = True        
