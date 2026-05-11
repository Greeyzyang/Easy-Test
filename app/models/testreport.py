from sqlalchemy import Column, String, CHAR, JSON, Enum, Text, ForeignKey, Integer, DateTime, Float, Numeric
import uuid
from sqlalchemy.orm import relationship
from .base_model import Base
from app.schemas.base_schemas import TestStatus, TestStepStatus

class Testreport(Base):
    __tablename__ = "testreports"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), index=True, info={"description": "报告名称"})
    description = Column(String(255), nullable=True, info={"description": "报告描述"})
    testsuite_id = Column(CHAR(36), ForeignKey("testsuites.id", ondelete="CASCADE"), nullable=False, info={"description": "关联的测试套件ID"})
    status = Column(Enum(TestStatus), default=TestStatus.PENDING, info={"description": "报告状态"})
    start_time = Column(DateTime, nullable=True, info={"description": "开始时间"})
    end_time = Column(DateTime, nullable=True, info={"description": "结束时间"})
    duration = Column(Numeric(precision=10, scale=1), nullable=True, info={"description": "执行时长(s，保留一位小数)"})
    total_cases = Column(Integer, default=0, info={"description": "总用例数"})
    passed_cases = Column(Integer, default=0, info={"description": "通过用例数"})
    failed_cases = Column(Integer, default=0, info={"description": "失败用例数"})
    skipped_cases = Column(Integer, default=0, info={"description": "跳过用例数"})
    pass_rate = Column(Integer, default=0, info={"description": "通过率"})
    
    # 关联关系
    testsuite = relationship("Testsuite", back_populates="testreports")
    execution_details = relationship("ExecutionDetail", back_populates="testreport", cascade="all, delete-orphan")

class ExecutionDetail(Base):
    __tablename__ = 'execution_details'

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    testreport_id = Column(CHAR(36), ForeignKey("testreports.id"), nullable=False, info={"description": "关联的测试报告ID"})
    testcase_id = Column(CHAR(36), ForeignKey("testcases.id"), nullable=False, info={"description": "关联的测试用例ID"})
    step_id = Column(CHAR(36), ForeignKey("teststeps.id"), nullable=False, info={"description": "关联的测试步骤ID"})
    step_name = Column(String(255), nullable=False, info={"description": "步骤名称"})
    status = Column(Enum(TestStepStatus), default=TestStepStatus.PENDING, info={"description": "执行状态"})
    start_time = Column(DateTime, nullable=True, info={"description": "开始时间"})
    end_time = Column(DateTime, nullable=True, info={"description": "结束时间"})
    duration = Column(Numeric(precision=10, scale=1), nullable=True, info={"description": "执行时长(s，保留一位小数)"})
    request_data = Column(JSON, nullable=True, info={"description": "请求数据"})
    response_data = Column(JSON, nullable=True, info={"description": "响应数据"})
    error_message = Column(String(255), nullable=True, info={"description": "错误信息"})
    
    # 新增的order字段，用于记录步骤的执行顺序
    order = Column(Integer, nullable=False, default=0, info={"description": "测试步骤的执行顺序"})
    
    # 关联关系
    testreport = relationship("Testreport", back_populates="execution_details")
    testcase = relationship("Testcase")
    step = relationship("TestStep")