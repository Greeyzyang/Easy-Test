from sqlalchemy import Column, String, CHAR, ForeignKey, JSON, Integer
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.ext.associationproxy import association_proxy
from .base_model import Base

# 定义关联模型
class TestSuiteTestCase(Base):
    __tablename__ = "testcase_to_testsuite"
    
    # 不使用 Base 的默认 ID，使用复合主键
    id = None
    
    testcase_id = Column(CHAR(36), ForeignKey("testcases.id"), primary_key=True)
    testsuite_id = Column(CHAR(36), ForeignKey("testsuites.id"), primary_key=True)
    sort_order = Column(Integer, default=0, info={"description": "排序"})
    
    testcase = relationship("Testcase")
    testsuite = relationship("Testsuite", back_populates="testcase_associations")

class Testsuite(Base):
    __tablename__ = "testsuites"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), index=True, info={"description": "测试集名称"})
    description = Column(String(255), nullable=True, info={"description": "测试集描述"})
    cron_expression = Column(String(255), nullable=True, index=True, info={"description": "Cron 表达式"})
    env_name = Column(String(255), nullable=True, info={"description": "环境变量名"})
    headers = Column(JSON, nullable=True, info={"description": "公共请求头"})
    project_id = Column(CHAR(36), ForeignKey("projects.id"), nullable=True, index=True, info={"description": "项目ID"})
    
    project = relationship("Project", back_populates="testsuites")
    
    # 使用关联模型管理多对多关系
    testcase_associations = relationship("TestSuiteTestCase", 
                                       back_populates="testsuite", 
                                       cascade="all, delete-orphan",
                                       order_by="TestSuiteTestCase.sort_order")
    
    # 使用 association_proxy 简化访问，保持原有接口兼容性（大部分情况下）
    testcases = association_proxy("testcase_associations", "testcase",
                                creator=lambda tc: TestSuiteTestCase(testcase=tc))
                                
    testreports = relationship("Testreport", back_populates="testsuite", 
                             info={"description": "关联的测试报告"})
