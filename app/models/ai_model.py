from sqlalchemy import Column, String, Boolean, Text, DateTime
from .base_model import Base
import uuid
from datetime import datetime

class AIModel(Base):
    __tablename__ = "ai_models"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, info={"description": "模型显示名称"})
    provider = Column(String(50), nullable=False, info={"description": "供应商 (deepseek, doubao, glm, openai)"})
    model_name = Column(String(100), nullable=False, info={"description": "模型调用名称 (e.g. deepseek-chat)"})
    api_key = Column(String(255), nullable=False, info={"description": "API Key"})
    base_url = Column(String(255), nullable=False, info={"description": "Base URL"})
    is_active = Column(Boolean, default=False, info={"description": "是否当前启用"})
    description = Column(Text, nullable=True, info={"description": "描述"})
    icon = Column(String(255), nullable=True, info={"description": "图标URL或类名"})
