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
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return []
        return v


class UserCreate(schemas.BaseUserCreate):
    username: str
    permissions: List[str] = Field(default_factory=list)


class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = None
    permissions: Optional[List[str]] = None


class TokenData(BaseModel):
    sub: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class UserPermissionUpdate(BaseModel):
    permissions: List[str]