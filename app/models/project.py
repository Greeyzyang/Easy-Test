from sqlalchemy import Column, String, CHAR, DateTime, Text, JSON
import uuid
from sqlalchemy.orm import relationship
from .base_model import Base

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), index=True, info={"description": "项目名称"})
    description = Column(Text, nullable=True, info={"description": "项目描述"})
    creator = Column(String(255), info={"description": "创建人"})
    headers = Column(JSON, nullable=True, default={}, info={"description": "项目公共请求头 (JSON)"})
    variables = Column(JSON, nullable=True, default={}, info={"description": "项目公共变量 (JSON)"})
    modules = relationship("Module", back_populates="project", info={"description": "包含模块"})
    testsuites = relationship("Testsuite", back_populates="project", info={"description": "包含测试套件"})
    performance_tests = relationship("PerformanceTest", back_populates="project", info={"description": "包含压测"})