from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from .teststep import TestStepCreate, TestStepInTestcase, TestStepDetail
from app.schemas.base_schemas import TestcaseInSuite
from datetime import datetime

class TestcaseBase(BaseModel):
    name: str
    description: Optional[str] = None
    priority: Optional[int] = 1
    module_id: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    status: Optional[str] = "active"
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None

    @field_validator("tags", mode="before")
    @classmethod
    def handle_none_tags(cls, v):
        if v is None:
            return []
        return v


class TestcaseCreate(TestcaseBase):
    steps: Optional[List[TestStepCreate]] = []

class TestcaseUpdate(TestcaseBase):
    steps: Optional[List[TestStepCreate]] = None


class ModuleSimple(BaseModel):
    id: str
    name: str
    class Config:
        from_attributes = True

class TestcaseRead(TestcaseBase):
    id: str
    steps: List[TestStepInTestcase] = []
    module: Optional[ModuleSimple] = None
    
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