from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from .testcase import TestcaseDetail
from .teststep import TestStepDetail


class ModuleBase(BaseModel):
    name: str
    project_id: str
    description: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None

class ModuleCreate(ModuleBase):
    pass

class ModuleRead(ModuleBase):
    id: str

    class Config:
        from_attributes = True

class ModuleDetail(ModuleRead):
    testcases: List[TestcaseDetail] = []

    class Config:
        from_attributes = True