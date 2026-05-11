from sqlalchemy import Column, String, CHAR, Text, Enum, JSON, ForeignKey
import uuid
from sqlalchemy.orm import relationship
from .base_model import Base
from app.schemas.base_schemas import InterfaceMethod, RequestType

class Interface(Base):
    __tablename__ = "interfaces"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), index=True, info={"description": "接口名称"})
    url = Column(String(255), info={"description": "请求URL"})
    method = Column(
        Enum(InterfaceMethod),
        default=InterfaceMethod.GET,
        server_default=InterfaceMethod.GET.value,
        info={"description": "请求方法"}
    )
    description = Column(Text, nullable=True, info={"description": "接口描述"})
    version = Column(String(50), nullable=True, default="v1", server_default="v1", info={"description": "接口版本"})
    
    # 请求配置相关字段
    request_type = Column(
        Enum(RequestType),
        default=RequestType.JSON,
        server_default=RequestType.JSON.value,
        info={"description": "请求体类型"}
    )
    headers = Column(JSON, nullable=True, info={"description": "请求头"})
    params = Column(JSON, nullable=True, info={"description": "请求参数"})
    body = Column(JSON, nullable=True, info={"description": "请求体示例"})
    body_schema = Column(JSON, nullable=True, info={"description": "请求体结构定义"})
    
    # 添加外键字段
    module_id = Column(CHAR(36), ForeignKey("modules.id"), info={"description": "所属模块ID"})
    
    module = relationship("Module", back_populates="interfaces", info={"description": "所属模块"})
    steps = relationship("TestStep", back_populates="interface")

