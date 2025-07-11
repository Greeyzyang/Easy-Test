from sqlalchemy import Column, String, CHAR, Table, ForeignKey
import uuid
from sqlalchemy.orm import relationship
from .base_model import Base

# 定义关联表
testcase_to_testsuite = Table(
    "testcase_to_testsuite",
    Base.metadata,
    Column("testcase_id", CHAR(36), ForeignKey("testcases.id"), primary_key=True),
    Column("testsuite_id", CHAR(36), ForeignKey("testsuites.id"), primary_key=True)
)

class Testsuite(Base):
    __tablename__ = "testsuites"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), index=True, info={"description": "测试集名称"})
    description = Column(String(255), nullable=True, info={"description": "测试集描述"})
    cron_expression = Column(String(255), nullable=True, info={"description": "Cron 表达式"})
    env_name = Column(String(255), nullable=True, info={"description": "环境变量名"})
    testcases = relationship("Testcase", secondary=testcase_to_testsuite, 
                           back_populates="testsuites", 
                           info={"description": "关联的用例"})
    testreports = relationship("Testreport", back_populates="testsuite", 
                             info={"description": "关联的测试报告"})
