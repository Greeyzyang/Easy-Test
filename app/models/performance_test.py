from sqlalchemy import Column, String, CHAR, ForeignKey, JSON, Integer, Enum
from sqlalchemy.orm import relationship

from .base_model import Base
from app.schemas.base_schemas import TestStatus


class PerformanceTest(Base):
    __tablename__ = "load_tests"

    name = Column(String(255), nullable=False, index=True)
    description = Column(String(255), nullable=True)
    project_id = Column(CHAR(36), ForeignKey("projects.id"), nullable=False, index=True)
    status = Column(Enum(TestStatus), default=TestStatus.PENDING, index=True)

    concurrent_users = Column(Integer, nullable=False, default=10)
    run_mode = Column(String(20), default="duration")
    duration_seconds = Column(Integer, nullable=False, default=60)
    total_requests_limit = Column(Integer, nullable=True)

    target_base_url = Column(String(500), nullable=True)

    user_pool_ref = Column(String(255), nullable=True)
    user_pool_mode = Column(String(50), nullable=True)

    request_config = Column(JSON, nullable=True)

    created_by = Column(CHAR(36), ForeignKey("users.id"), nullable=True, index=True)

    project = relationship("Project", back_populates="performance_tests")
    reports = relationship("PerformanceTestReport", back_populates="performance_test", cascade="all, delete-orphan")
