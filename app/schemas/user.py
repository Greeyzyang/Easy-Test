from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from fastapi_users import schemas
import json


class UserRead(schemas.BaseUser[str]):
    username: str
    permissions: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True

    @field_validator('permissions', mode='before')
    @classmethod
    def parse_permissions(cls, v):
        """将字符串形式的权限转换为列表"""
        # 兼容 None、字符串(JSON)与列表三种输入，统一返回列表
        if v is None:
            return []
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        if isinstance(v, list):
            return v
        # 其他类型一律回退为空列表，避免 Pydantic v2 校验错误
        return []


class UserCreate(schemas.BaseUserCreate):
    username: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = None
    permissions: Optional[List[str]] = None


class TokenData(BaseModel):
    sub: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class UserPermissionUpdate(BaseModel):
    permissions: List[str]
