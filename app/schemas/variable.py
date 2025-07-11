from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class VariableBase(BaseModel):
    key: str = Field(..., description="变量名")
    value: str = Field(..., description="变量值（支持字符串或JSON）")
    description: Optional[str] = Field(None, description="变量描述")
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None

class VariableCreate(VariableBase):
    pass

class VariableUpdate(VariableBase):
    pass

class VariableRead(VariableBase):
    id: str

    class Config:
        from_attributes = True