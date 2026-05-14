# 后端规范 (FastAPI / Python)

> 详细代码模板见 [patterns.md](./patterns.md)

## 1. 统一响应格式（必须遵循）

所有 API 必须用 `ResponseModel` 封装：

```python
from app.utils.response import create_response, ResponseModel

@router.post("/", response_model=ResponseModel)
async def create_resource(data: ResourceCreate, db: AsyncSession = Depends(get_db)):
    return await create_response(data={"id": resource.id})
```

响应结构：`{"code": "0", "data": {...}, "msg": "success"}`
错误响应：直接 `raise HTTPException`，不要自己封装。

---

## 2. Router 规范

**导入顺序**：FastAPI/Starlette -> SQLAlchemy -> `.users` -> `app.database` -> `app.models` -> `app.schemas` -> `app.utils` -> 标准库

**Router 定义**：
- 文件：每个模块一个 Router（如 `app/routers/testcases.py`）
- prefix: `/rest/v1/{resource}`，tags: `["{resource}"]`
- 每个端点 `response_model=ResponseModel`

**端点命名**：
```python
@router.post("/", response_model=ResponseModel)           # create
@router.get("/", response_model=ResponseModel)            # read list
@router.get("/{resource_id}/", response_model=ResponseModel)  # read one
@router.put("/{resource_id}/", response_model=ResponseModel)  # update
@router.delete("/{resource_id}/", response_model=ResponseModel) # delete
# 特殊端点放 CRUD 之后
@router.post("/ai-generate/", response_model=ResponseModel)
```

**数据库会话**：`db: AsyncSession = Depends(get_db)` 放参数最后。

---

## 3. Pydantic Schema 规范（四层分离）

每个资源一个 Schema 文件（如 `app/schemas/testcase.py`）：

```python
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class ResourceBase(BaseModel):
    name: str
    description: Optional[str] = None
    @field_validator("field", mode="before")
    @classmethod
    def handle_none(cls, v):
        return v if v is not None else []

class ResourceCreate(ResourceBase):
    steps: Optional[List[StepCreate]] = []

class ResourceUpdate(ResourceBase):
    # 所有字段 Optional
    name: Optional[str] = None
    steps: Optional[List[StepCreate]] = None

class ResourceRead(ResourceBase):
    id: str
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    steps: List[StepInResource] = []
    module: Optional[ModuleSimple] = None
    class Config:
        from_attributes = True
```

**规则**：
- `Optional` 字段必须给默认值
- `List` 默认值用 `Field(default_factory=list)` 或 `= []`
- 必须 `from_attributes = True`
- 用 `field_validator` 处理 `None` -> `[]` 边界值

---

## 4. SQLAlchemy Model 规范

每个资源一个 Model 文件（如 `app/models/testcase.py`）：

```python
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, Enum, DateTime
from sqlalchemy.orm import relationship
from app.models.base_model import Base
import uuid

class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = {"extend_existing": True}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False, index=True)
    # 外键必须 String(36) 匹配主键
    module_id = Column(String(36), ForeignKey("modules.id"), nullable=True)
    tags = Column(JSON, nullable=True)
    created_time = Column(DateTime, default=datetime.utcnow)
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    module = relationship("Module", back_populates="resources")
    steps = relationship("Step", back_populates="resource",
        cascade="all, delete-orphan", order_by="Step.order")
```

**规则**：
- 主键：`String(36)` + UUID
- 外键：`String(36)` 匹配主键
- JSON 字段加 `default=lambda: []`
- 关系删除：`cascade="all, delete-orphan"`
- 时间戳：`datetime.utcnow`

---

## 5. 日志规范

每个 Python 文件顶部：`logger = get_logger(__name__)`

| 级别 | 场景 |
|------|------|
| `logger.info` | 操作开始 / 成功 |
| `logger.warning` | 非致命异常（资源未找到等） |
| `logger.error` | 严重错误，记录 `e` 对象 |
| `logger.debug` | 调试信息 |

---

## 6. 异步编程规范

- 所有 Handler 必须是 `async def`
- 所有 DB 操作 `await db.execute/commit/refresh`
- 列表查询用 `select(...).offset(skip).limit(limit)`

---

## 7. 分页查询规范

```python
skip = max((page - 1) * limit, 0)
count_result = await db.execute(select(func.count()).select_from(Resource))
total = count_result.scalar()
result = await db.execute(
    select(Resource).options(selectinload(Resource.module))
    .offset(skip).limit(limit).order_by(Resource.created_time.desc())
)
items = result.scalars().all()
return await create_response(data={"items": items, "total": total})
```

---

## 8. 错误处理规范

找不到资源：`result.scalar_one_or_none()` 后 `if not resource: raise HTTPException(404)`
业务错误：`raise HTTPException(400)`
DB 异常：`except Exception as e: await db.rollback(); logger.error(...); raise HTTPException(500)`
