from typing import List, Optional
from pydantic import BaseModel

class JiraFixVersion(BaseModel):
    name: str
    id: Optional[str] = None
    released: Optional[bool] = None
    archived: Optional[bool] = None
    release_date: Optional[str] = None

class JiraBugItem(BaseModel):
    key: str
    components: List[str]
    created: Optional[str] = None
    severity: Optional[str] = None
    resolved: Optional[str] = None
    assignee: Optional[str] = None

class JiraBugDistributionItem(BaseModel):
    module: str
    bug_count: int

class JiraBugDistributionData(BaseModel):
    project_key: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_bugs: int
    items: List[JiraBugDistributionItem]
    bugs: List[JiraBugItem]
    bug_severity: List["JiraSeverityItem"]

class JiraFixVersionsData(BaseModel):
    project_key: str
    versions: List[JiraFixVersion]

class JiraSeverityItem(BaseModel):
    name: str
    count: int

class JiraVersionTrendItem(BaseModel):
    version: str
    bug_count: int
    demand_count: int
    release_date: Optional[str] = None

class JiraVersionTrendData(BaseModel):
    project_key: str
    items: List[JiraVersionTrendItem]
