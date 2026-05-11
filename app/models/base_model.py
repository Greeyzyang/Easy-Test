import uuid
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import String, DateTime, Column

class Base(DeclarativeBase):
    __abstract__ = True

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_time = Column(DateTime, default=datetime.utcnow, info={"description": "创建时间"})
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, info={"description": "更新时间"})