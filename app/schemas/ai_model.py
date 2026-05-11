from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AIModelBase(BaseModel):
    name: str = Field(..., description="模型显示名称")
    provider: str = Field(..., description="供应商 (deepseek, doubao, glm, openai)")
    model_name: str = Field(..., description="模型调用名称 (e.g. deepseek-chat)")
    api_key: str = Field(..., description="API Key")
    base_url: str = Field(..., description="Base URL")
    description: Optional[str] = Field(None, description="描述")
    icon: Optional[str] = Field(None, description="图标URL或类名")

class AIModelCreate(AIModelBase):
    pass

class AIModelUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    icon: Optional[str] = None

class AIModelTestConnection(BaseModel):
    provider: str
    model_name: str
    api_key: str
    base_url: str

class AIModelRead(AIModelBase):
    id: str
    is_active: bool
    created_time: datetime
    updated_time: datetime

    class Config:
        from_attributes = True
