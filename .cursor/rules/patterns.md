# 常用代码模式

> 这些是精简后的核心模板，完整规范见 [backend.md](./backend.md) 和 [frontend.md](./frontend.md)

## 后端

### Router 模板

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Resource
from app.schemas.resource import ResourceCreate, ResourceRead
from app.utils.response import create_response, ResponseModel
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/rest/v1/resources", tags=["resources"])

@router.post("/", response_model=ResponseModel)
async def create_resource(data: ResourceCreate, db: AsyncSession = Depends(get_db)):
    logger.info(f"Creating resource: {data.name}")
    db_obj = Resource(**data.dict())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return await create_response(data=ResourceRead.model_validate(db_obj).model_dump())

@router.get("/", response_model=ResponseModel)
async def read_resources(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Resource).options(selectinload(Resource.module)).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return await create_response(data={"items": items, "total": len(items)})
```

### Pydantic Schema 模板

```python
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime

class ResourceBase(BaseModel):
    name: str
    description: Optional[str] = None

    @field_validator("tags", mode="before")
    @classmethod
    def handle_none(cls, v):
        return v if v is not None else []

class ResourceCreate(ResourceBase):
    steps: Optional[List[StepCreate]] = []

class ResourceUpdate(ResourceBase):
    name: Optional[str] = None
    steps: Optional[List[StepCreate]] = None

class ResourceRead(ResourceBase):
    id: str
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    class Config:
        from_attributes = True
```

### Model 模板

```python
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from app.models.base_model import Base
import uuid

class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = {"extend_existing": True}
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False, index=True)
    module_id = Column(String(36), ForeignKey("modules.id"), nullable=True)
    tags = Column(JSON, nullable=True)
    created_time = Column(DateTime, default=datetime.utcnow)
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    module = relationship("Module", back_populates="resources")
```

## 前端

### API 层模板

```javascript
import request from '@/utils/request'

export function getResources(listQueryParams) {
  return request({
    url: '/rest/v1/resources/',
    method: 'get',
    params: {
      skip: Math.max((listQueryParams.page - 1) * listQueryParams.limit, 0),
      limit: listQueryParams.limit,
      name: listQueryParams.name
    }
  })
}

export function getResource(id) {
  return request({ url: `/rest/v1/resources/${id}/`, method: 'get' })
}

export function createResource(data) {
  return request({ url: '/rest/v1/resources/', method: 'post', data })
}

export function updateResource(id, data) {
  return request({ url: `/rest/v1/resources/${id}/`, method: 'put', data })
}

export function deleteResource(id) {
  return request({ url: `/rest/v1/resources/${id}/`, method: 'delete' })
}
```

### 列表页模板（核心片段）

```javascript
data() {
  return {
    list: null,
    total: 0,
    listLoading: true,
    listQuery: { page: 1, limit: 20, name: undefined }
  }
},
methods: {
  async getList() {
    this.listLoading = true
    try {
      const response = await getResources(this.listQuery)
      if (response && response.code === '0' && response.data) {
        this.list = response.data.items || []
        this.total = response.data.total || 0
      }
    } finally {
      this.listLoading = false
    }
  },
  handleFilter() {
    this.listQuery.page = 1
    this.getList()
  },
  async handleDelete(row) {
    await this.$confirm('确认删除吗？', '提示', { type: 'warning' })
    await deleteResource(row.id)
    this.$message.success('删除成功')
    this.getList()
  }
}
```

### 编辑页模板（核心片段）

```javascript
async init() {
  this.loading = true
  try {
    const [res1, res2] = await Promise.all([
      getResource(this.$route.params.id),
      getModuleList({ page: 1, limit: 1000 })
    ])
    if (res1 && res1.code === '0') this.form = { ...this.form, ...res1.data }
    if (res2 && res2.code === '0') this.moduleOptions = res2.data.items || []
  } finally {
    this.loading = false
  }
},
async save() {
  const valid = await this.$refs.form.validate().catch(() => false)
  if (!valid) return
  const api = this.form.id ? updateResource : createResource
  const args = this.form.id ? [this.form.id, this.form] : [this.form]
  await api(...args)
  this.$message.success('保存成功')
  this.$router.push('/resources')
}
```
