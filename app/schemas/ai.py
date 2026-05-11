from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class JiraKeyInput(BaseModel):
    jira_key: str = Field(..., description="Jira issue key (e.g., 'GINO-123')")

class InterfaceIdInput(BaseModel):
    interface_id: str = Field(..., description="The ID of the interface (e.g., 'uuid')")

class GeneratedTestcase(BaseModel):
    title: str = Field(..., description="Title of the test case")
    type: str = Field("functional", description="Type of the test case")
    priority: str = Field("P1", description="Priority of the test case")
    precondition: Optional[str] = Field(None, description="Preconditions for the test case")
    steps: List[str] = Field(..., description="Steps to perform")
    expected_result: str = Field(..., description="Expected result")
    # Technical details for persistence
    headers: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Request headers")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query parameters")
    body: Optional[Any] = Field(None, description="Request body")
    expected_response_code: Optional[int] = Field(200, description="Expected response status code")
    assertions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Validation assertions")
    extract_variables: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Variables to extract")

class SaveGeneratedTestcasesRequest(BaseModel):
    interface_id: str = Field(..., description="The ID of the interface")
    testcases: List[GeneratedTestcase] = Field(..., description="List of generated and reviewed test cases to save")

class ReportIdInput(BaseModel):
    report_id: str = Field(..., description="The ID of the test report")

class DiagnoseInput(BaseModel):
    report_id: str = Field(..., description="The ID of the test report")
    case_id: Optional[str] = Field(None, description="Optional specific test case ID to diagnose")

class SqlQueryInput(BaseModel):
    query: str = Field(..., description="The SQL SELECT query to execute")

class BaseProjectInput(BaseModel):
    project_key: str = Field(default="DM", description="The Jira project key (default: DM)")

class ProjectKeyInput(BaseProjectInput):
    versions: Optional[List[str]] = Field(None, description="Optional list of fix versions to filter by")

class BugDistributionInput(BaseProjectInput):
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
    version_type: Optional[str] = Field("all", description="Version type filter: 'official', 'patch', or 'all'")
    fix_versions: Optional[List[str]] = Field(None, description="Optional list of fix versions to filter by")
    limit: Optional[int] = Field(None, description="Limit the number of recent versions to retrieve (e.g. 6)")

class KbQueryInput(BaseModel):
    query: str = Field(..., description="The search query for the knowledge base")

class LimitInput(BaseModel):
    limit: int = Field(default=5, description="Number of items to retrieve")

class VersionRegressionInput(BaseProjectInput):
    versions: List[str] = Field(..., description="The fix versions to check (e.g., ['v1.0.0'])")

class JiraInsightInput(BaseProjectInput):
    versions: List[str] = Field(default_factory=list, description="List of fix versions (e.g. ['10.12.0']). If empty, analyzes recent data.")
    include_regression: bool = Field(default=True, description="Boolean flag: include regression status")
    include_distribution: bool = Field(default=True, description="Boolean flag: include component distribution")
    include_statistics: bool = Field(default=True, description="Boolean flag: include general stats")
    include_cycle_time: bool = Field(default=True, description="Boolean flag: include member cycle time")


class GenerateTaskRequest(BaseModel):
    jira_key: str = Field(..., description="The main Jira issue key")
    linked_req_keys: List[str] = Field(default=[], description="List of linked requirement Jira keys (non-bug issues)")
    task_id: Optional[str] = Field(None, description="Optional pre-existing task_id. If provided, the tool will query this task instead of creating a new one.")

class AgentChatRequest(BaseModel):
    message: str = Field(..., description="User message to the agent")
    history: List[dict] = Field(default=[], description="Chat history as a list of message objects")
    stream: bool = Field(default=True, description="Whether to use streaming response")
