from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from .teststep import TestStepCreate, TestStepInTestcase, TestStepDetail
from app.schemas.base_schemas import TestcaseStatus
from datetime import datetime

class TestcaseBase(BaseModel):
    name: str
    description: Optional[str] = None
    priority: Optional[int] = 1
    tags: List[str] = None
    status: Optional[str] = "active"
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None


class TestcaseCreate(TestcaseBase):
    steps: Optional[List[TestStepCreate]] = []

class TestcaseUpdate(TestcaseBase):
    steps: Optional[List[TestStepCreate]] = None

class TestcaseInSuite(TestcaseBase):
    """在测试集中使用的测试用例信息"""
    id: str
    status: TestcaseStatus
    priority: int
    steps_count: int

    class Config:
        from_attributes = True

class TestcaseRead(TestcaseBase):
    id: str
    steps: List[TestStepInTestcase] = []
    
    class Config:
        from_attributes = True

class TestcaseWithResults(TestcaseRead):
    """包含执行结果的测试用例信息"""
    total_steps: int
    passed_steps: int
    failed_steps: int
    pass_rate: float

    class Config:
        from_attributes = True

class TestcaseDetail(TestcaseRead):
    steps: List[TestStepDetail] = []

    class Config:
        from_attributes = True