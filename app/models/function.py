from sqlalchemy import Column, Integer, String, Text, JSON
import uuid
from .base_model import Base

class Function(Base):
    __tablename__ = "functions"

    id = Column(Integer, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, index=True, nullable=False, info={"description": "函数名称"})
    description = Column(Text, nullable=True, info={"description": "函数描述"})
    code = Column(Text, nullable=False, info={"description": "函数代码"})
