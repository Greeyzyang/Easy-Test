from sqlalchemy import Column, String, Text, Boolean, JSON
from app.models.base_model import Base
import uuid


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, index=True, nullable=False, info={"description": "服务器名称"})
    description = Column(Text, nullable=True, info={"description": "服务器描述"})
    transport = Column(String(20), nullable=False, default="stdio", info={"description": "传输类型: stdio | http | sse"})
    command = Column(String(255), nullable=True, info={"description": "启动命令 (stdio 模式)"})
    args = Column(JSON, nullable=True, default=[], info={"description": "启动参数列表"})
    env = Column(JSON, nullable=True, default={}, info={"description": "环境变量"})
    url = Column(String(500), nullable=True, info={"description": "服务端点 URL (http/sse 模式)"})
    headers = Column(JSON, nullable=True, default={}, info={"description": "HTTP 请求头 (http/sse 模式)"})
    enabled = Column(Boolean, default=True, info={"description": "是否启用"})
