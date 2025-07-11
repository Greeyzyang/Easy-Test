from sqlalchemy import Column, String, CHAR, Text, ForeignKey
import uuid
from sqlalchemy.orm import relationship
from .base_model import Base
from .testcase import testcase_to_module


class Module(Base):
    __tablename__ = "modules"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), index=True, info={"description": "模块名称"})
    project_id = Column(CHAR(36), ForeignKey("projects.id"))
    description = Column(Text, nullable=True, info={"description": "模块描述"})
    
    project = relationship("Project", back_populates="modules")
    interfaces = relationship("Interface", back_populates="module")
    testcases = relationship("Testcase", secondary=testcase_to_module, back_populates="modules")