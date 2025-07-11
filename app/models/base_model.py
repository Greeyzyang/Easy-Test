from datetime import datetime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Integer, DateTime, Column

class Base(DeclarativeBase):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_time = Column(DateTime, default=datetime.now,  info={"description": "创建时间"})
    updated_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, info={"description": "更新时间"})