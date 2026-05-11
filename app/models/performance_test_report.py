from sqlalchemy import Column, String, CHAR, ForeignKey, JSON, Integer, Enum, Numeric, DateTime
from sqlalchemy.orm import relationship

from .base_model import Base
from app.schemas.base_schemas import TestStatus


class PerformanceTestReport(Base):
    __tablename__ = "load_test_reports"

    performance_test_id = Column(CHAR(36), ForeignKey("load_tests.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(TestStatus), default=TestStatus.IN_PROGRESS)

    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    error_rate = Column(Numeric(5, 4), nullable=True)

    avg_response_time = Column(Numeric(10, 2), nullable=True)
    min_response_time = Column(Numeric(10, 2), nullable=True)
    max_response_time = Column(Numeric(10, 2), nullable=True)
    median_response_time = Column(Numeric(10, 2), nullable=True)
    p90_response_time = Column(Numeric(10, 2), nullable=True)
    p95_response_time = Column(Numeric(10, 2), nullable=True)
    p99_response_time = Column(Numeric(10, 2), nullable=True)
    stddev_response_time = Column(Numeric(10, 2), nullable=True)

    requests_per_second = Column(Numeric(10, 2), nullable=True)

    timeline_data = Column(JSON, nullable=True)
    scenario_stats = Column(JSON, nullable=True)

    performance_test = relationship("PerformanceTest", back_populates="reports")
