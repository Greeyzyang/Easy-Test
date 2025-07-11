from sqlalchemy import Column, String, CHAR, Text, Enum, Integer, JSON, ForeignKey, Table
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.ext.associationproxy import association_proxy
from .base_model import Base
from app.schemas.base_schemas import TestcaseStatus
from .testsuite import testcase_to_testsuite
from .teststep import TestStep

# 定义关联表
testcase_to_module = Table(
    "testcase_to_module",
    Base.metadata,
    Column("testcase_id", CHAR(36), ForeignKey("testcases.id"), primary_key=True),
    Column("module_id", CHAR(36), ForeignKey("modules.id"), primary_key=True)
)

class Testcase(Base):
    __tablename__ = "testcases"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), index=True, info={"description": "测试用例名称"})
    description = Column(Text, nullable=True, info={"description": "测试用例描述"})
    priority = Column(Integer, default=0, info={"description": "用例优先级"})
    tags = Column(JSON, nullable=True, info={"description": "用例标签"})
    setup = Column(Text, nullable=True, info={"description": "用例前置条件"})
    teardown = Column(Text, nullable=True, info={"description": "用例后置处理"})
    status = Column(
        Enum(TestcaseStatus), 
        default=TestcaseStatus.PENDING,
        server_default=TestcaseStatus.PENDING.value,
        info={"description": "用例状态"}
    )
    
    # 关系定义
    steps = relationship("TestStep", back_populates="testcase", 
                        cascade="all, delete-orphan",
                        order_by=TestStep.order)
    interfaces = association_proxy("steps", "interface")
    testsuites = relationship("Testsuite", secondary=testcase_to_testsuite, 
                            back_populates="testcases")
    modules = relationship("Module", secondary=testcase_to_module,
                         back_populates="testcases")

    @property
    def steps_count(self) -> int:
        """获取测试用例的步骤数量"""
        return len(self.steps)

    def __repr__(self):
        return f"<Testcase {self.name}>"
