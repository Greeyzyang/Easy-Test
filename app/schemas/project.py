from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from .module import ModuleRead

class ProjectBase(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    creator: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None

class ProjectCreate(ProjectBase):
    pass

class TestsuiteBase(BaseModel):
    id: str
    name: str

    class Config:
           from_attributes = True

class ProjectRead(ProjectBase):
    id: str
    modules: List[ModuleRead] = []
    testsuites: List[TestsuiteBase] = []

    class Config:
           from_attributes = True
