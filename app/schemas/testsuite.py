from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from .base_schemas import TestcaseStatus



class TestcaseInSuite(BaseModel):
    """在测试套件中使用的简化测试用例信息"""
    id: str
    name: str
    description: Optional[str] = None
    status: TestcaseStatus
    steps_count: int

    class Config:
        from_attributes = True

class TestsuiteBase(BaseModel):
    name: str
    description: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    cron_expression: Optional[str] = None
    env_name: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    project_id: Optional[str] = None


class TestsuiteCreate(TestsuiteBase):
    testcases: List[str]

class TestsuiteRead(TestsuiteBase):
    id: str
    testcases: Optional[List[TestcaseInSuite]] = []

    class Config:
        from_attributes = True

class TestsuiteUpdate(TestsuiteBase):
    testcases: Optional[List[str]] = None


class ScheduleTestSuiteRequest(BaseModel):
    testsuite_id: str
    cron_expression: str   