from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class PerformanceTestReportRead(BaseModel):
    id: str
    performance_test_id: str
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: Optional[float] = None
    avg_response_time: Optional[float] = None
    min_response_time: Optional[float] = None
    max_response_time: Optional[float] = None
    median_response_time: Optional[float] = None
    p90_response_time: Optional[float] = None
    p95_response_time: Optional[float] = None
    p99_response_time: Optional[float] = None
    stddev_response_time: Optional[float] = None
    requests_per_second: Optional[float] = None
    timeline_data: Optional[List[Dict[str, Any]]] = None
    scenario_stats: Optional[Dict[str, Any]] = None
    created_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class PerformanceTestReportListItem(BaseModel):
    id: str
    performance_test_id: str
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: Optional[float] = None
    avg_response_time: Optional[float] = None
    p90_response_time: Optional[float] = None
    p99_response_time: Optional[float] = None
    requests_per_second: Optional[float] = None
    created_time: Optional[datetime] = None

    class Config:
        from_attributes = True
