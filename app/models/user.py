from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import Column, String, Boolean, DateTime, func, Text, CHAR
from datetime import datetime
from fastapi_users.db import SQLAlchemyBaseUserTable
import uuid
import json
from passlib.context import CryptContext
from sqlalchemy.orm import relationship
from .base_model import Base

class Base(DeclarativeBase):
    pass

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


    @hybrid_property
    def permissions(self):
        """获取权限列表"""
        try:
            return json.loads(self.permissions) if self.permissions else []
        except:
            return []

    @permissions.setter
    def permissions(self, value):
        """设置权限列表"""
        if isinstance(value, list):
            self.permissions = json.dumps(value)
        elif isinstance(value, str):
            # 如果已经是JSON字符串，直接存储
            try:
                json.loads(value)  # 验证是否有效的JSON
                self.permissions = value
            except:
                self.permissions = '[]'
        else:
            self.permissions = '[]'

    def has_permission(self, permission: str) -> bool:
        """检查用户是否有指定权限"""
        if self.is_superuser:
            return True
        return permission in self.permissions

def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# 在用户注册时
def register_user(user_input_password: str):
    hashed_password = hash_password(user_input_password)
    # 将 hashed_password 存储到数据库