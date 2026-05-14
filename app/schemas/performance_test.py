from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from .base_schemas import ExtractVariableConfig


class PerformanceStepSchema(BaseModel):
    name: str
    interface_id: Optional[str] = None
    override_url: Optional[str] = None
    override_method: Optional[str] = None
    override_headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    override_body: Optional[Dict] = Field(default_factory=dict)
    think_time_ms: int = 0
    extract_variables: Optional[List[ExtractVariableConfig]] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PerformanceScenarioSchema(BaseModel):
    name: str
    enabled: bool = True
    scenario_delay_ms: int = Field(default=0, ge=0, le=600000, description="场景循环间隔(毫秒)，一轮请求完成后等待再开始下一轮")
    steps: List[PerformanceStepSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True


class UserPoolConfigSchema(BaseModel):
    variable_name: Optional[str] = Field(None, description="全局变量名，如 USER_POOL")
    mode: str = Field("random", description="random | round_robin")
    auth_config: Optional[Dict[str, Any]] = Field(
        None,
        description="认证配置，包含 login_url、login_body_template、token_key"
    )

    class Config:
        from_attributes = True


class PerformanceTestBase(BaseModel):
    name: str
    description: Optional[str] = None
    project_id: str
    concurrent_users: int = Field(10, ge=1, le=1000)
    run_mode: Literal["duration", "fixed_requests"] = Field("duration", description="duration=固定时长(秒), fixed_requests=固定总请求数")
    duration_seconds: int = Field(60, ge=5, le=3600, description="固定时长模式：持续秒数")
    total_requests_limit: Optional[int] = Field(None, ge=1, le=10000000, description="固定请求数模式：总请求数上限")
    target_base_url: Optional[str] = None
    user_pool: Optional[UserPoolConfigSchema] = None


class PerformanceTestCreate(PerformanceTestBase):
    scenario: PerformanceScenarioSchema


class PerformanceTestUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[str] = None
    concurrent_users: Optional[int] = Field(None, ge=1, le=1000)
    run_mode: Optional[Literal["duration", "fixed_requests"]] = None
    duration_seconds: Optional[int] = Field(None, ge=5, le=3600)
    total_requests_limit: Optional[int] = Field(None, ge=1, le=10000000)
    target_base_url: Optional[str] = None
    user_pool: Optional[UserPoolConfigSchema] = None
    scenario: Optional[PerformanceScenarioSchema] = None


class PerformanceTestRead(PerformanceTestBase):
    id: str
    status: str
    scenario: Optional[PerformanceScenarioSchema] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    created_by: Optional[str] = None

    class Config:
        from_attributes = True
