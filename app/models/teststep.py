from sqlalchemy import Column, String, CHAR, Text, Integer, ForeignKey, JSON, Enum, Numeric
import uuid
from sqlalchemy.orm import relationship
from .base_model import Base
from app.schemas.base_schemas import TestStepStatus, RequestType

class TestStep(Base):
    __tablename__ = "teststeps"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), index=True, info={"description": "步骤名称"})
    description = Column(Text, nullable=True, info={"description": "步骤描述"})
    testcase_id = Column(CHAR(36), ForeignKey("testcases.id"), nullable=False)
    interface_id = Column(CHAR(36), ForeignKey("interfaces.id"), nullable=False)
    
    # 请求配置
    headers = Column(JSON, nullable=True, info={"description": "请求头配置"})
    body = Column(JSON, nullable=True, info={"description": "请求体配置"})
    params = Column(JSON, nullable=True, info={"description": "请求参数配置"})
    request_type = Column(Enum(RequestType), default=RequestType.JSON, server_default=RequestType.JSON.value, 
                         info={"description": "请求类型"})
    file_config = Column(JSON, nullable=True, info={"description": "文件上传配置"})
    
    # 验证配置
    expected_response_code = Column(Integer, nullable=True, info={"description": "预期响应码"})
    assertions = Column(JSON, nullable=True, info={"description": "断言规则列表"})
    
    # 变量提取
    extract_variables = Column(JSON, nullable=True, info={"description": "变量提取配置"})
    
    # 执行状态
    status = Column(Enum(TestStepStatus), default=TestStepStatus.PENDING, server_default=TestStepStatus.PENDING.value,
                   info={"description": "执行状态"})
    
    # 关系
    testcase = relationship("Testcase", back_populates="steps")
    interface = relationship("Interface", back_populates="steps")
    
    # 添加执行结果相关字段
    actual_response = Column(JSON, nullable=True, info={"description": "实际响应结果"})
    error_message = Column(Text, nullable=True, info={"description": "错误信息"})
    duration = Column(Numeric(precision=10, scale=1), nullable=True, info={"description": "执行时长(ms，保留一位小数)"})
    retry_count = Column(Integer, default=0, info={"description": "重试次数"})
    
    # 新增的order字段
    order = Column(Integer, nullable=False, default=0, info={"description": "测试步骤的顺序"})
    