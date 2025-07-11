from sqlalchemy import Column, String, Text, DateTime
from app.models.base_model import Base
import uuid

class Variable(Base):
    __tablename__ = "variables"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(100), unique=True, nullable=False, index=True, comment="变量名")
    value = Column(Text, nullable=False, comment="变量值（支持字符串或JSON）")
    description = Column(String(255), nullable=True, comment="变量描述")