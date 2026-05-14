from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import Column, String, Boolean, DateTime, func, Text, CHAR
from datetime import datetime
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
import uuid
import json
from app.utils.password import pwd_context
from sqlalchemy.orm import relationship
from .base_model import Base

class User(SQLAlchemyBaseUserTable, Base):
    __tablename__ = "users"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(320), unique=True, nullable=False)
    username = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(1024), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    permissions = Column(Text, nullable=True)
    created_time = Column(DateTime)
    updated_time = Column(DateTime)

    def has_permission(self, permission: str) -> bool:
        if self.is_superuser:
            return True
        try:
            perms = json.loads(self.permissions) if self.permissions else []
        except Exception:
            perms = []
        return permission in perms

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)
# 在用户注册时
def register_user(user_input_password: str):
    hashed_password = hash_password(user_input_password)
    # 将 hashed_password 存储到数据库
