import json
import asyncio
import os
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from sqlalchemy import text, select
from app.database import SessionLocal

from langchain_openai import ChatOpenAI
from langchain.tools import StructuredTool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from app.services.ai_service import AIService
# Correct imports based on model definitions
from app.models.testreport import Testreport as TestReport, ExecutionDetail as TestReportCase
from app.models.testcase import Testcase as TestCase
from app.schemas.ai import (
    JiraKeyInput, 
    ProjectKeyInput,
    BugDistributionInput,
    KbQueryInput,
    LimitInput,
    ReportIdInput,
    DiagnoseInput,
    SqlQueryInput,
    VersionRegressionInput,
    JiraInsightInput,
    GenerateTaskRequest
)
from app.config import Settings
from app.utils.logger import get_logger

settings = Settings()
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Middleware: Tool Call Counter (prevents doom loops)
# ---------------------------------------------------------------------------

class ToolCallCounter:
    """Tracks per-tool call counts within a single agent session to prevent doom loops."""

    def __init__(self):
        self.counts: Dict[str, int] = {}
        self.file_edits: Dict[str, int] = {}  # track edits per file/path

    def record(self, tool_name: str, file_path: str | None = None):
        self.counts[tool_name] = self.counts.get(tool_name, 0) + 1
        if file_path:
            key = f"{tool_name}:{file_path}"
            self.file_edits[key] = self.file_edits.get(key, 0) + 1

    def get(self, tool_name: str, file_path: str | None = None) -> int:
        if file_path:
            return self.file_edits.get(f"{tool_name}:{file_path}", 0)
        return self.counts.get(tool_name, 0)

    def reset(self):
        self.counts.clear()
        self.file_edits.clear()

# Per-thread tool counter shared across middleware and stream
_tool_call_counters: Dict[str, ToolCallCounter] = {}


def _get_counter(thread_id: str) -> ToolCallCounter:
    if thread_id not in _tool_call_counters:
        _tool_call_counters[thread_id] = ToolCallCounter()
    return _tool_call_counters[thread_id]


# Per-tool call limits (configurable)
TOOL_CALL_LIMITS: Dict[str, int] = {
    "get_jira_issue_details": 10,
    "generate_test_cases": 5,
    "review_requirement": 10,
    "get_jira_insight": 10,
    "run_sql_query": 20,
    "diagnose_test_failure": 10,
    # MCP tools share a single limit
    "__mcp__": 15,
}


def _make_post_model_hook(thread_id: str):
    """
    Build a post_model_hook that:
    1. Blocks tools exceeding per-tool call limits (doom loop prevention)
    2. Injects verification reminder after generate_test_cases completes
    """

    async def post_model_hook(state: Any) -> Any:
        counter = _get_counter(thread_id)

        # Extract LLM output from state
        messages = state.get("messages", [])
        if not messages:
            return {}

        last_msg = messages[-1]
        tool_calls = getattr(last_msg, "tool_calls", []) or []

        if not tool_calls:
            return {}

        # --- 1. Doom loop prevention: check tool call limits ---
        blocked = []
        for tc in tool_calls:
            name = tc.get("name", "") or ""
            # Try to extract file path from arguments (heuristic)
            args = tc.get("args", {}) or {}
            file_hint = args.get("file_path") or args.get("filename") or args.get("path")

            current = counter.get(name, file_hint)
            limit = TOOL_CALL_LIMITS.get(name, TOOL_CALL_LIMITS.get("__mcp__", 20))

            if current >= limit:
                blocked.append(name)
                logger.warning(
                    f"[Harness] Tool '{name}' exceeded call limit ({limit}) for thread={thread_id}. "
                    f"Blocking call. Counter={counter.counts}"
                )

        if blocked:
            # Return a Command to interrupt and replace tool calls with a warning message
            warning_content = (
                f"[HARNESS BLOCKED] The following tools have been called too many times in this session: "
                f"{', '.join(set(blocked))}. "
                f"Please review the conversation history and provide a response based on the information "
                f"already gathered. Do not repeat the same tool call."
            )
            return Command(
                update={
                    "messages": last_msg.__class__(content=warning_content)
                },
                goto=[],  # end the agent turn, don't continue to tools
            )

        # --- 2. Record calls and inject verification nudge after generate_test_cases ---
        for tc in tool_calls:
            name = tc.get("name", "") or ""
            args = tc.get("args", {}) or {}
            file_hint = args.get("file_path") or args.get("filename") or args.get("path")
            counter.record(name, file_hint)

        return {}

    return post_model_hook


# ---------------------------------------------------------------------------
# Skill Directory Scanner
# ---------------------------------------------------------------------------

_GLOBAL_MEMORYSAVERS: Dict[str, MemorySaver] = {}

# Global MCP tools cache - populated lazily on first use
# Use mutable wrapper so inner functions can rebind the module-level name
_mcp_cache: Dict[str, Any] = {"tools": None, "loaded": False}


def _scan_skill_directory() -> Dict[str, Dict[str, str]]:
    """Hot-scan app/prompts/skills/ directory to generate SKILL_REGISTRY dynamically."""
    import re as _re
    skills_dir = os.path.join(os.getcwd(), "app/prompts/skills")
    if not os.path.exists(skills_dir):
        return {}
    registry = {}
    for fname in os.listdir(skills_dir):
        if fname.endswith(".md") and not fname.startswith("_"):
            skill_name = fname[:-3]  # "jira_skill.md" -> "jira_skill"
            fpath = os.path.join(skills_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                # Simple frontmatter parsing (between first ---)
                if content.startswith("---"):
                    end = content.find("\n---\n", 3)
                    if end > 0:
                        fm = content[3:end]
                        for line in fm.splitlines():
                            if line.startswith("name:"):
                                skill_name = line.split(":", 1)[1].strip()
            except Exception:
                pass
            registry[skill_name] = {
                "description": f"Local skill from {fname}",
                "filename": fname
            }
    return registry


class StrContentChatModel(ChatOpenAI):
    """Wrapper to ensure all message content is converted to string."""
    
    def _convert_content_to_str(self, content: Any) -> str:
        """Convert any content type to string."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        parts.append(f"[Tool: {block.get('name', 'unknown')}]")
                    else:
                        parts.append(str(block))
                elif isinstance(block, str):
                    parts.append(block)
                else:
                    parts.append(str(block))
            return " ".join(parts) if parts else ""
        return str(content)
    
    def _normalize_message(self, msg: Any) -> Any:
        """Normalize a message to ensure content is a string."""
        if hasattr(msg, "content") and msg.content is not None:
            if not isinstance(msg.content, str):
                msg.content = self._convert_content_to_str(msg.content)
        return msg
    
    def _normalize_messages(self, messages: List[Any]) -> List[Any]:
        """Normalize all messages in a list."""
        return [self._normalize_message(m) for m in messages]
    
    async def _astream(self, *args, **kwargs):
        """Override astream to normalize messages."""
        if args:
            args = (self._normalize_messages(args[0]),) + args[1:]
        elif "messages" in kwargs:
            kwargs["messages"] = self._normalize_messages(kwargs["messages"])
        async for chunk in super()._astream(*args, **kwargs):
            yield chunk
    
    def _agonerate(self, *args, **kwargs):
        """Override agenerate to normalize messages."""
        if args:
            args = (self._normalize_messages(args[0]),) + args[1:]
        elif "messages" in kwargs:
            kwargs["messages"] = self._normalize_messages(kwargs["messages"])
        return super()._agonerate(*args, **kwargs)


class AgentService:
    # Hot-scanned at startup; updated dynamically by create_skill_file / install_skill
    SKILL_REGISTRY: Dict[str, Dict[str, str]] = _scan_skill_directory()

    def __init__(self, db: Optional[Any] = None, model_config: Optional[Any] = None):
        self.db = db
        self.ai_service = AIService()
        self.tools_map = self._init_tools()
        self.skills = None
        self.model_provider = None
        self.model_alias = None
        self.model_base_url = None
        
        # Production Safety: Verify consistency between Tool Map and Skill Registry
        # This ensures that every skill with tools is registered for routing
        unknown_skills = set(self.tools_map.keys()) - set(self.SKILL_REGISTRY.keys())
        if unknown_skills:
            logger.warning(f"Found skills in Tool Map not present in Registry: {unknown_skills}")

        # Configure LLM based on model_config or settings
        if model_config:
            api_key = model_config.api_key
            base_url = model_config.base_url
            model_name = model_config.model_name
            self.model_provider = getattr(model_config, "provider", None)
            self.model_alias = getattr(model_config, "name", None)
            self.model_base_url = base_url
        else:
            api_key = settings.LLM_API_KEY
            base_url = settings.LLM_API_BASE
            model_name = settings.LLM_MODEL_NAME
            self.model_provider = "config"
            self.model_alias = None
            self.model_base_url = base_url

        # Initialize LLM for Agent
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0,
            streaming=True # Enable streaming by default for the LLM
        )
        
        self.model_name = model_name
        self.system_prompt = self._load_system_prompt(model_name)
        self.memory = MemorySaver()
        self.agent_executor = create_react_agent(
            self.llm,
            [tool for tools in self.tools_map.values() for tool in tools],
            checkpointer=self.memory,
            state_modifier=self.system_prompt
        )

    def _rebuild_agent(self, tools: List[Any], thread_id: str = "default"):
        # NOTE: post_model_hook is not supported in this version of langgraph.
        # Doom loop prevention and tool call counting are handled in _stream_generator
        # via on_tool_start events (see _tool_call_counters usage there).
        self.agent_executor = create_react_agent(
            self.llm,
            tools,
            checkpointer=self.memory,
            state_modifier=self.system_prompt,
        )

    async def _load_mcp_tools(self) -> List[Any]:
        """Load MCP server tools from DB. Called lazily on first agent use."""
        if _mcp_cache["loaded"]:
            return _mcp_cache["tools"] or []

        try:
            from app.services.mcp_browser_service import get_mcp_browser_service
            service = get_mcp_browser_service()
            _mcp_cache["tools"] = await service.get_mcp_tools()
        except Exception as e:
            logger.warning(f"Failed to load MCP tools: {e}")
            _mcp_cache["tools"] = []

        _mcp_cache["loaded"] = True
        return _mcp_cache["tools"] or []

    def _get_active_tools(self, skills: Optional[List[str]]) -> List[Any]:
        if skills:
            tools: List[Any] = []
            for s in skills:
                if s in self.tools_map:
                    tools.extend(self.tools_map[s])
            if tools:
                return tools
        all_tools = [tool for tools in self.tools_map.values() for tool in tools]
        always_tools = self.tools_map.get("agent_skill", [])
        return all_tools + always_tools

    def _set_thread_memory(self, thread_id: str):
        mem = _GLOBAL_MEMORYSAVERS.get(thread_id)
        if mem is None:
            mem = MemorySaver()
            _GLOBAL_MEMORYSAVERS[thread_id] = mem
        self.memory = mem
        self._rebuild_agent(self._get_active_tools(self.skills), thread_id)

    def _convert_history(self, history: List[Dict[str, Any]], max_items: int = 6) -> List[Any]:
        msgs: List[Any] = []
        if not history:
            return msgs
        recent = history[-max_items:]
        for idx, item in enumerate(recent):
            role = (item.get("role") or "").lower()
            content = item.get("content")
            
            # Log problematic items for debugging
            if content is not None and not isinstance(content, (str, list, dict)):
                logger.warning(f"[History {idx}] Unexpected content type: role={role}, type={type(content)}, value={str(content)[:200]}")
            
            # Skip None content
            if content is None:
                continue
            
            # Skip empty content
            if isinstance(content, str) and not content.strip():
                continue
            
            # Handle non-string content: convert nested structures to string
            # This handles cases where assistant messages have tool_calls
            if not isinstance(content, str):
                # If content is a list of content blocks, extract text
                if isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif block.get("type") == "tool_use":
                                text_parts.append(f"[Tool: {block.get('name', 'unknown')}]")
                        elif isinstance(block, str):
                            text_parts.append(block)
                    content = " ".join(text_parts) if text_parts else ""
                elif isinstance(content, dict):
                    # Handle dict content - extract relevant fields
                    content = content.get("text", str(content))
                else:
                    content = str(content)
            
            if not content:
                continue
                
            if role in ("user", "human"):
                msgs.append(HumanMessage(content=content))
            elif role in ("assistant", "ai", "bot"):
                msgs.append(AIMessage(content=content))
            elif role == "system":
                msgs.append(SystemMessage(content=content))
        
        logger.debug(f"[_convert_history] Converted {len(msgs)} messages from {len(recent)} history items")
        return msgs

    async def _prepare_agent(self, message: str, history: List[Dict], thread_id: str) -> List[str]:
        self._set_thread_memory(thread_id)
        if self.skills is None:
            detected_skills = await self._detect_and_initialize(message, history, thread_id)
        else:
            detected_skills = self.skills
        return detected_skills

    def _initial_metadata(self, detected_skills: List[str], history: List[Dict]) -> str:
        def _already_shown(h: List[Dict]) -> bool:
            if not h:
                return False
            for item in h[-6:]:
                role = (item.get("role") or "").lower()
                content = (item.get("content") or "")
                if role in ("assistant", "ai", "bot") and ("Current AI Model:" in content or "当前模型" in content):
                    return True
            return False

        if _already_shown(history):
            return ""

        active_skills_str = ', '.join(detected_skills)
        provider = self.model_provider or "unknown"
        alias = (self.model_alias or "").strip()
        model_line = self.model_name
        if alias and alias != self.model_name:
            model_line = f"{alias} ({self.model_name})"

        return (
            f"**Current AI Provider: {provider}**\n"
            f"**Current AI Model: {model_line}**\n"
            f"**Active Skills: {active_skills_str}**\n\n"
        )

    def _load_system_prompt(self, model_name: str = "") -> str:
        """Load and format the system prompt from base and skills files."""
        try:
            base_prompt = ""
            # 1. Load Base System Prompt
            base_path = os.path.join(os.getcwd(), "app/prompts/base_system.md")
            if os.path.exists(base_path):
                with open(base_path, "r", encoding="utf-8") as f:
                    base_prompt = f.read()
            else:
                # Fallback to legacy file if base not found (for safety)
                logger.warning(f"Base system prompt not found at {base_path}, checking legacy...")
                legacy_path = os.path.join(os.getcwd(), "app/prompts/qa_agent_system.md")
                if os.path.exists(legacy_path):
                    with open(legacy_path, "r", encoding="utf-8") as f:
                        base_prompt = f.read()
                else:
                    logger.error("No system prompt file found!")
                    return "You are a helpful AI assistant."

            # 2. Load Skills Prompts
            skills_content = ""
            skills_dir = os.path.join(os.getcwd(), "app/prompts/skills")
            if os.path.exists(skills_dir):
                # Dynamic Skill Loading using Registry
                target_skills = []
                
                if self.skills:
                    # Map skill name -> filename using Registry
                    for skill in self.skills:
                        if skill in self.SKILL_REGISTRY:
                            target_skills.append(self.SKILL_REGISTRY[skill]['filename'])
                        else:
                            # Fallback
                            target_skills.append(f"{skill}.md")
                else:
                    # Load all available skills from Registry
                    target_skills = [info['filename'] for info in self.SKILL_REGISTRY.values()]

                for skill_file in target_skills:
                    # Normalize filename (just in case)
                    if not skill_file.endswith(".md") and "." not in skill_file:
                         skill_file += ".md"
                         
                    skill_path = os.path.join(skills_dir, skill_file)
                    if os.path.exists(skill_path):
                        with open(skill_path, "r", encoding="utf-8") as f:
                            skills_content += "\n\n" + f.read()
            
            # Combine
            full_content = base_prompt + skills_content

            # Replace placeholders
            current_date = datetime.now().strftime("%Y-%m-%d")
            content = full_content.replace("{{current_date}}", current_date)
            content = content.replace("{{current_model}}", model_name or "Unknown Model")
            
            # Active Skills Replacement
            if self.skills:
                active_skills_str = ', '.join(self.skills)
            else:
                active_skills_str = ', '.join(self.SKILL_REGISTRY.keys())
            content = content.replace("{{active_skills}}", active_skills_str)
            
            return content
        except Exception as e:
            logger.error(f"Error loading system prompt: {e}")
            return "You are a helpful AI assistant."

    def _init_tools(self) -> Dict[str, List[StructuredTool]]:
        """
        Initialize tools and group them by skill domain.
        Returns a dictionary mapping skill names to lists of tools.
        """
        # 1. Jira Skill Tools
        jira_tools = [
            StructuredTool.from_function(
                func=self.get_jira_issue_details,
                name="get_jira_issue_details",
                description="""Fetch full details of a Jira issue by key (e.g. "DM-1234").
- ALWAYS call this FIRST before any other Jira operation on that key.
- Returns: summary, description, status, priority, attachments (images as base64), linked_issues.
- If the key is malformed (not XX-1234), returns an error string; do NOT retry with same key.
- Descriptions may contain Confluence links, screen IDs, or acceptance criteria in plain text.
- Image attachments are pre-downloaded and passed as base64; handle them as multimodal context.""",
                args_schema=JiraKeyInput
            ),
            StructuredTool.from_function(
                func=self.get_linked_requirements,
                name="get_linked_requirements",
                description="""Extract non-Bug linked requirement keys from a Jira issue.
- Pass the same jira_key used in get_jira_issue_details.
- Returns JSON: {"linked_requirements": [...], "count": N}.
- Bug-type links (Bug/缺陷) are excluded automatically.
- IMPORTANT: Always pass returned keys as linked_req_keys to generate_test_cases for full coverage.
- If no linked requirements exist, returns {"linked_requirements": [], "count": 0}.
- NEVER assume linked_req_keys are available without calling this tool first.""",
                args_schema=JiraKeyInput
            ),
            StructuredTool.from_function(
                func=self.review_requirement,
                name="review_requirement",
                description="""Review a Jira requirement for testability and coverage gaps.
- Call AFTER get_jira_issue_details (not before).
- Returns structured review: completeness, ambiguity, missing info, testability score, and risks.
- Use this as a quality gate before calling generate_test_cases.
- If the requirement is vague, the review will explicitly state what assumptions were made.
- This tool does NOT modify or create anything; it's read-only quality assessment.""",
                args_schema=JiraKeyInput
            ),
            StructuredTool.from_function(
                func=self.get_jira_trend_chart,
                name="get_jira_trend_chart",
                description="""Generate a line chart (ECharts JSON) of Bug vs Demand counts per version for a project.
- project_key: Jira project key (e.g. "DM"), NOT a Jira issue key.
- version_type: filter by "all", "released", or "unreleased" versions.
- start_date / end_date: optional date range; defaults to last 180 days if not provided.
- fix_versions: optional list of specific version names to filter on.
- limit: optionally limit to last N versions.
- Returns: Markdown with embedded ```echarts``` block containing ECharts config.
- If no data, returns a plain text message; NOT an error that stops the agent.
- X-axis shows version numbers (not months) for better readability.""",
                args_schema=BugDistributionInput
            ),
            StructuredTool.from_function(
                func=self.get_jira_bug_distribution_chart,
                name="get_jira_bug_distribution_chart",
                description="""Generate two pie charts (ECharts JSON): Bug severity distribution and Top-10 bug modules.
- project_key: Jira project key (e.g. "DM").
- start_date / end_date / version_type / fix_versions: same filters as get_jira_trend_chart.
- Returns two ```echarts``` blocks: one for severity, one for top-10 module donut chart.
- If total_bugs == 0, returns plain text message (not error).
- Both charts use "donut" style for visual clarity.
- Useful for regression analysis and identifying high-risk modules before test planning.""",
                args_schema=BugDistributionInput
            ),
            StructuredTool.from_function(
                func=self.get_version_member_cycle_time_chart,
                name="get_version_member_cycle_time",
                description="""Generate a bar+line combo chart (ECharts JSON) showing each team member's average bug fix time (cycle time) for specific versions.
- project_key: Jira project key.
- versions: LIST of version names (e.g. ["10.0.1", "10.0.2"]). At least one required.
- Bar = avg cycle time (hours), Line = bug count per member.
- Use this to identify slow fixers or overloaded team members.
- If no data found for the specified versions, returns a plain text message.
- Results are sorted by avg cycle time descending (slowest first).""",
                args_schema=VersionRegressionInput
            ),
            StructuredTool.from_function(
                func=self.get_jira_insight,
                name="get_jira_insight",
                description="""Run a comprehensive multi-section Jira analysis for a project.
- Combines: regression status table + unresolved bug list + bug distribution charts + member cycle time.
- project_key: Jira project key. Defaults to "DM" if not provided.
- versions: optional filter; if provided, insights focus on those specific versions.
- include_regression: default True (shows open/reopened bug counts per version).
- include_distribution: default True (shows severity + module charts).
- include_cycle_time: default True (shows member efficiency chart, only if versions provided).
- Returns: JSON string with version_exists, is_version_released, analysis_content (Markdown).
- Use this as a "single shot" report; do NOT call individual chart tools if this is used.""",
                args_schema=JiraInsightInput
            ),
            StructuredTool.from_function(
                func=self.generate_test_cases,
                name="generate_test_cases",
                description="""[MOST COMPLEX TOOL] Generate test cases from a Jira requirement using AI.
- jira_key: Jira issue key (e.g. "DM-5678"). MANDATORY. Must be XX-1234 format.
- linked_req_keys: list of linked requirement keys from get_linked_requirements output. Optional but RECOMMENDED for full coverage.
- task_id: optional; if omitted, a UUID is auto-generated for progress tracking.
- WORKFLOW: This tool internally calls get_jira_issue_details, then RAG KB retrieval, then LLM generation, then caches to Redis.
- RETURNS: Markdown with analysis highlights, KB retrieval status, a case summary table, AND an Excel download URL.
- The download URL is valid for 24h (Redis TTL). Tell the user to download promptly.
- ERRORS: If Jira key is not found, returns "SYSTEM_ERROR: Generation failed: ..." — report this to the user verbatim.
- CRITICAL: Do NOT call this without first calling get_jira_issue_details on the same jira_key. The agent needs the issue context to generate quality cases.
- If the requirement is unclear or missing attachments, this tool will generate cases with "Assumption noted in ANALYSIS section" — this is expected behavior, not a bug.""",
                args_schema=GenerateTaskRequest
            )
        ]

        # 2. Testing Skill Tools
        testing_tools = [
            StructuredTool.from_function(
                func=self.list_recent_reports,
                name="list_recent_reports",
                description="""List the most recent test execution reports with pass rate and status.
- limit: max number of reports to return (default 5, max 50).
- Returns: Markdown table with ID, Status, Pass Rate, Created At.
- Use this to find a report_id before calling get_test_report_summary or diagnose_test_failure.
- If no reports exist, returns plain text "No recent test reports found." (not error).""",
                args_schema=LimitInput
            ),
            StructuredTool.from_function(
                func=self.get_test_report_summary,
                name="get_test_report_summary",
                description="""Get a detailed summary of a specific test execution report.
- report_id: the full UUID of the test report (find via list_recent_reports).
- Returns: key-value summary with status, pass rate, total/passed/failed counts, duration.
- If report not found, returns "Report {id} not found." (not error).
- Use this to understand overall test health before diagnosing individual failures.""",
                args_schema=ReportIdInput
            ),
            StructuredTool.from_function(
                func=self.diagnose_test_failure,
                name="diagnose_test_failure",
                description="""Diagnose failure reasons in a test report, optionally scoped to a single case.
- report_id: REQUIRED. UUID of the test report to analyze.
- case_id: OPTIONAL. If provided, only analyzes that specific case; if omitted, analyzes ALL FAILED cases (up to 5).
- Returns: Markdown with per-case diagnosis: error message, likely root cause, and suggested fix direction.
- This tool reads ExecutionDetail records from the database; it does NOT re-run tests.
- If no failed cases found, returns "No failed cases found to diagnose."
- Limit to 5 failures per call to keep output readable; ask the user to specify case_id for deeper analysis.""",
                args_schema=DiagnoseInput
            ),
            StructuredTool.from_function(
                func=self.run_sql_query,
                name="run_sql_query",
                description="""[RESTRICTED] Execute a read-only SELECT query against the test database.
- SECURITY: ONLY SELECT statements are allowed. Any INSERT, UPDATE, DELETE, DROP, or ALTER is rejected.
- query: the full SQL SELECT statement to execute.
- Returns: Markdown table with results (max 10 rows shown, with "...and N more rows." note).
- Common use cases: verify test data setup, check DB state after test run, cross-reference Jira with local records.
- NEVER use this for destructive operations. If user asks for INSERT/UPDATE/DELETE, refuse and explain why.
- If the query syntax is invalid, returns the database error message (not a Python error).""",
                args_schema=SqlQueryInput
            )
        ]

        # 3. Knowledge Skill Tools
        knowledge_tools = [
            StructuredTool.from_function(
                func=self.query_knowledge_base,
                name="query_knowledge_base",
                description="""Search the internal RAG knowledge base (uploaded PDFs and QA documents) for relevant context.
- query: natural language search query. Use Chinese for Chinese documents, English for English docs.
- The KB contains: product requirement docs, API specs, QA guidelines, and uploaded PDFs.
- Returns: answer text + source citations (filename and page number).
- If no relevant results, returns "未找到答案" (not an error).
- KB context is automatically prepended to generate_test_cases when available; you do NOT need to call this manually before generate_test_cases.
- Use this tool when the user asks questions about product knowledge, testing standards, or API behavior.""",
                args_schema=KbQueryInput
            )
        ]

        # 4. Agent Skill Tools (always available, for skill self-management)
        agent_tools = [
            StructuredTool.from_function(
                func=self.create_skill_file,
                name="create_skill_file",
                description="""[ADMIN TOOL] Create a new local Skill .md file and register it in the running session.
- name: alphanumeric + hyphens/underscores only (e.g. "api_testing_skill"). No spaces.
- description: one-line description shown in skill directory.
- content: full Markdown content for the skill file.
- File is written to app/prompts/skills/{name}.md and available immediately in this session (no restart needed).
- BEFORE creating: always call get_skill_directory to check if the skill already exists (avoid duplication).
- Use this when you discover a repeated workflow or specialized knowledge that should be codified.
- This tool is for enriching the agent's own capabilities, not for user-facing content.""",
            ),
            StructuredTool.from_function(
                func=self.get_skill_directory,
                name="get_skill_directory",
                description="""List all locally installed skills available in the current session.
- Returns: Markdown list of skill names + descriptions.
- Always call this BEFORE creating or installing a new skill to avoid duplication.
- Shows both locally created skills and skills installed from GitHub.
- If no skills are installed, returns instructions on how to use list_remote_skills.
- This tool is read-only; it does not modify anything.""",
            ),
            StructuredTool.from_function(
                func=self.list_remote_skills,
                name="list_remote_skills",
                description="""Browse available skills from the GitHub anthropics/skills repository.
- query: optional keyword filter (e.g. "testing", "api", "documentation").
- Returns: Markdown list of matching skill names with GitHub URLs.
- Skills are organized by domain (e.g. testing, code review, documentation).
- Use this to discover community-maintained skills before installing.
- After finding a skill you want, call install_skill(name) to add it locally.""",
            ),
            StructuredTool.from_function(
                func=self.install_skill,
                name="install_skill",
                description="""[ADMIN TOOL] Install a skill from the GitHub anthropics/skills repository.
- name: the exact skill name (must match a directory in the GitHub repo, e.g. "computer-use-demo").
- Fetches the SKILL.md file from https://github.com/anthropics/skills/tree/main/skills/{name}/.
- File is saved to app/prompts/skills/{name}.md and registered immediately (no restart needed).
- BEFORE installing: always call list_remote_skills to browse available skills.
- If skill already exists locally, returns an error (use the existing one).
- If HTTP 404: the skill name does not exist in the repository (check spelling).
- After installation, the new skill is automatically available in this session.""",
            )
        ]

        return {
            "jira_skill": jira_tools,
            "testing_skill": testing_tools,
            "knowledge_skill": knowledge_tools,
            "agent_skill": agent_tools
        }

    async def _detect_and_initialize(self, message: str, history: List[Dict], thread_id: str) -> List[str]:
        """
        Detect intent and initialize the agent with appropriate skills and tools.
        """
        detected_skills = await self._detect_intent(message, history)
        logger.info(f"Auto-detected skills for message '{message[:20]}...': {detected_skills}")

        self.skills = detected_skills
        self.system_prompt = self._load_system_prompt(self.model_name)

        # Merge static tools with dynamic MCP tools from DB
        static_tools = self._get_active_tools(detected_skills)
        mcp_tools = await self._load_mcp_tools()
        all_tools = static_tools + mcp_tools

        self._rebuild_agent(all_tools, thread_id)
        return detected_skills

    async def _stream_chat_pipeline(self, message: str, history: List[Dict], thread_id: str):
        """
        Pipeline for streaming chat: Intent Detection -> Agent Execution
        """
        try:
            # Log raw history for debugging
            logger.info(f"[Stream] Raw history length: {len(history) if history else 0}")
            for i, h in enumerate(history or []):
                role = h.get("role", "?")
                content = h.get("content")
                ctype = type(content).__name__
                logger.info(f"[Stream] History[{i}] role={role}, content_type={ctype}, content={str(content)[:150] if content else 'None'}")
            
            detected_skills = await self._prepare_agent(message, history, thread_id)
            metadata = self._initial_metadata(detected_skills, history)
            if metadata:
                yield metadata

            # 2. Agent Execution Phase
            config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
            converted_msgs = self._convert_history(history)
            new_messages = converted_msgs + [HumanMessage(content=message)]
            
            # Log detailed message info for debugging
            for i, m in enumerate(new_messages):
                content_type = type(m.content).__name__
                content_preview = str(m.content)[:100] if m.content else "None"
                logger.info(f"[Msg {i}] {type(m).__name__}: content_type={content_type}, preview={content_preview}")
            
            async for chunk in self._stream_generator({"messages": new_messages}, config):
                yield chunk
                
        except Exception as e:
            logger.error(f"Streaming pipeline error: {e}")
            yield f"Sorry, I encountered an error: {str(e)}"

    async def chat(self, message: str, history: List[Dict] = [], thread_id: str = "default", stream: bool = False):
        """
        Run the agent with the user message.
        If skills were not explicitly provided during init, automatically detect intent.
        """
        if stream:
            return self._stream_chat_pipeline(message, history, thread_id)

        try:
            detected_skills = await self._prepare_agent(message, history, thread_id)

            # Increase recursion limit to handle complex tool chains
            config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
            
            # React agent expects a list of messages
            # Note: We largely rely on the MemorySaver (checkpointer) for history.
            # The 'history' param is kept for compatibility but we mainly use the new message.
            messages = self._convert_history(history) + [HumanMessage(content=message)]
            
            # Execute agent
            final_state = await self.agent_executor.ainvoke({"messages": messages}, config=config)
            content = final_state["messages"][-1].content
            
            metadata = self._initial_metadata(detected_skills, history)
            if metadata:
                content = metadata + content

            return content
            
        except Exception as e:
            logger.error(f"Agent chat error: {e}")
            return f"Sorry, I encountered an error: {str(e)}"

    async def _detect_intent(self, message: str, history: List[Dict] = []) -> List[str]:
        """
        Use LLM to classify user intent and select relevant skills.
        Considers recent chat history for context.
        """
        try:
            # Simple heuristic optimization: if message is very short and no history, just load all
            if len(message) < 5 and not history:
                 return list(self.SKILL_REGISTRY.keys())

            # Format recent history (last 2 turns)
            context_str = ""
            if history:
                recent_history = history[-2:]
                for msg in recent_history:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    context_str += f"{role}: {content}\n"

            # Dynamic Skill Description Construction
            skills_desc = ""
            for idx, (skill_name, info) in enumerate(self.SKILL_REGISTRY.items(), 1):
                skills_desc += f"{idx}. `{skill_name}`: {info['description']}\n"

            prompt = f"""You are an intelligent Intent Classifier for a QA Platform.
Analyze the user's input (and recent context) to select the most relevant skills.

**Available Skills:**
{skills_desc}
**Rules:**
- Return ONLY a JSON list of strings. Example: ["jira_skill"]
- **Priority Rule - Playwright**: If the input mentions "浏览器", "网页", "打开", "搜索", "点击", "自动化", "UI测试", "Playwright", "自动化测试", "Web", "http://", "https://", "截图", "打开网页", MUST include `playwright_skill`. Do not use other skills for browser/Web tasks.
- **Priority Rule - Jira**: If the input mentions a specific version number (like 10.x.x), release, or status check, it is STRICTLY `jira_skill`. Do not include `knowledge_skill` unless the user explicitly asks for "documentation" or "manual".
- If context implies a follow-up (e.g., "how about that bug?"), use history to infer the domain.
- Only return `knowledge_skill` if the query is about static knowledge, concepts, or product feature descriptions.

**Few-shot Examples:**
| User Input | Return |
|---|---|
| "帮我看看DM-1234的测试用例" | ["jira_skill"] |
| "最近测试报告通过率怎么样" | ["testing_skill"] |
| "查询下关于登录的知识库" | ["knowledge_skill"] |
| "打开百度搜一下AI" | ["playwright_skill"] |
| "生成DM-5678的用例" | ["jira_skill"] |
| "最近的报告情况如何" | ["testing_skill"] |
| "帮我创建个API测试skill" | ["agent_skill"] |

**Context:**
{context_str}

**User Input:** "{message}"
"""
            # Use invoke, not ainvoke if self.llm is ChatOpenAI (it supports async but check method)
            # The existing code uses create_react_agent(self.llm...) so self.llm is a ChatModel.
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()
            
            # Extract JSON list
            import re
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
            else:
                logger.warning(f"Intent classification failed to parse JSON: {content}")
                # Fallback
                return list(self.SKILL_REGISTRY.keys())
                
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            # Fallback to all skills
            return list(self.SKILL_REGISTRY.keys())

    async def _stream_generator(self, inputs, config):
        """Generator for streaming tokens from the agent."""
        try:
            step_counter = 0
            header_shown = False
            running_tools = {}

            # Extract thread_id for doom loop prevention
            thread_id = (
                (config or {})
                .get("configurable", {})
                .get("thread_id", "default")
            )
            counter = _get_counter(thread_id)

            def _shorten(data: Any, limit: int = 280) -> str:
                try:
                    if isinstance(data, (dict, list)):
                        s = json.dumps(data, ensure_ascii=False)
                    else:
                        s = str(data)
                except Exception:
                    s = str(data)
                s = s.strip()
                return s if len(s) <= limit else (s[:limit] + "…")
            def _resolve_tool_name(meta: Dict[str, Any], evt: Dict[str, Any], data: Dict[str, Any]) -> str:
                return (
                    (meta or {}).get("name")
                    or (evt or {}).get("name")
                    or (data or {}).get("name")
                    or (data or {}).get("tool_name")
                    or (data or {}).get("tool")
                    or "unknown_tool"
                )
            def _resolve_run_id(evt: Dict[str, Any], data: Dict[str, Any]) -> Optional[str]:
                return (evt or {}).get("run_id") or (data or {}).get("run_id") or (data or {}).get("id")

            # Use astream_events to get token-level streaming and tool traces
            async for event in self.agent_executor.astream_events(inputs, config=config, version="v2"):
                kind = event.get("event")

                if kind == "on_tool_start":
                    data = event.get("data", {})
                    name = _resolve_tool_name(None, event, data)
                    run_id = _resolve_run_id(event, data)

                    # --- Harness: Doom Loop Prevention ---
                    args = data.get("input") or {}
                    if isinstance(args, dict):
                        file_hint = args.get("file_path") or args.get("filename") or args.get("path")
                    else:
                        file_hint = None
                    current = counter.get(name, file_hint)
                    limit = TOOL_CALL_LIMITS.get(name, TOOL_CALL_LIMITS.get("__mcp__", 20))
                    if current >= limit:
                        # Skip this tool call (do not yield tool start, agent gets empty result)
                        logger.warning(
                            f"[Harness] Tool '{name}' exceeded limit ({limit}) on thread={thread_id}. "
                            f"Skipping call."
                        )
                        running_tools[run_id] = {"name": name, "skipped": True}
                        continue

                    counter.record(name, file_hint)

                    step_counter += 1
                    if not header_shown:
                        header_shown = True
                        yield "\n—— 执行过程 ——\n"
                    running_tools[run_id] = {"name": name, "t": datetime.utcnow()}
                    input_preview = _shorten(data.get("input"))
                    yield f"\n[步骤{step_counter}] 调用工具: {name}\n输入: {input_preview}\n"
                    continue

                if kind == "on_tool_end":
                    data = event.get("data", {})
                    run_id = _resolve_run_id(event, data)
                    meta = running_tools.pop(run_id, {}) if run_id in running_tools else {}
                    name = _resolve_tool_name(meta, event, data)
                    started = meta.get("t")
                    duration = 0.0
                    if started:
                        try:
                            duration = (datetime.utcnow() - started).total_seconds()
                        except Exception:
                            duration = 0.0
                    output_preview = _shorten(data.get("output"))
                    yield f"[完成] {name} 用时 {duration:.2f}s\n输出摘要: {output_preview}\n"
                    continue

                if kind == "on_tool_error":
                    data = event.get("data", {})
                    run_id = _resolve_run_id(event, data)
                    meta = running_tools.pop(run_id, {}) if run_id in running_tools else {}
                    name = _resolve_tool_name(meta, event, data)
                    err = _shorten(data.get("error") or data.get("output") or "unknown error")
                    yield f"[失败] {name}\n错误: {err}\n"
                    continue

                # Stream tokens from the final LLM response (when it's not a tool call)
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if hasattr(chunk, "content") and chunk.content:
                        # Handle content blocks - extract text from block structure
                        content = chunk.content
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    yield block.get("text", "")
                                elif isinstance(block, str):
                                    yield block
                        elif isinstance(content, str):
                            yield content
                        else:
                            yield str(content)
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"\n[Error during streaming: {str(e)}]"

    def get_jira_issue_details(self, jira_key: str) -> str:
        """Get Jira issue details."""
        try:
            issue = self.ai_service.get_jira_issue_details(jira_key)
            if not issue:
                return f"Could not find Jira issue {jira_key}."
            
            return f"### Jira Issue: {jira_key}\n" \
                   f"- **Summary**: {issue.get('summary')}\n" \
                   f"- **Status**: {issue.get('status')}\n" \
                   f"- **Priority**: {issue.get('priority')}\n" \
                   f"- **Description**: {issue.get('description')}\n"
        except Exception as e:
            return f"Error getting Jira issue: {str(e)}"

    def query_knowledge_base(self, query: str) -> str:
        """Query the internal knowledge base."""
        try:
            result = self.ai_service.query_kb(query)
            answer = result.get("answer", "未找到答案")
            sources = result.get("sources", [])
            
            response = f"{answer}\n\n**参考来源:**\n"
            if not sources:
                response += "- 无\n"
            else:
                # 简单去重
                seen_sources = set()
                idx = 1
                for source in sources:
                    metadata = source.get("metadata", {})
                    if not isinstance(metadata, dict):
                        metadata = {}
                    
                    src_name = os.path.basename(metadata.get('source', 'Unknown'))
                    page = metadata.get('page', 'N/A')
                    key = f"{src_name}-p{page}"
                    
                    if key not in seen_sources:
                        response += f"{idx}. {src_name} (Page {page})\n"
                        seen_sources.add(key)
                        idx += 1
            
            return response
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Agent KB query failed: {error_details}")
            return f"查询知识库失败 (Technical Details): {str(e)}\n\nTraceback:\n{error_details}"

    def review_requirement(self, jira_key: str) -> str:
        """Review a requirement."""
        try:
            issue = self.ai_service.get_jira_issue_details(jira_key)
            if not issue:
                return f"Could not find Jira issue {jira_key}."
            
            return self.ai_service.review_requirement(issue)
        except Exception as e:
            return f"Error reviewing requirement: {str(e)}"

    def get_linked_requirements(self, jira_key: str) -> str:
        """Return non-bug linked requirement keys for a Jira issue (JSON)."""
        try:
            info = self.ai_service.get_jira_issue_details(jira_key)
            if not info:
                return json.dumps({"linked_requirements": [], "count": 0})
            linked = info.get("linked_issues") or []
            req_links = []
            for li in linked:
                if not isinstance(li, dict):
                    continue
                it = (li.get("issuetype") or "").strip()
                if it in {"Bug", "缺陷"}:
                    continue
                key = li.get("key")
                if key:
                    req_links.append(key)
            return json.dumps({"linked_requirements": req_links, "count": len(req_links)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"linked_requirements": [], "count": 0, "error": str(e)}, ensure_ascii=False)

    def generate_test_cases(self, jira_key: str, linked_req_keys: List[str] = [], task_id: Optional[str] = None) -> str:
        """
        Generate test cases from a Jira requirement.
        
        Uses the testcase_generation_service which handles:
        - Caching (Redis)
        - Jira issue fetching (with linked_requirements auto-derivation)
        - RAG knowledge base retrieval
        - LLM generation
        - Result parsing and normalization
        - Progress pushing (WebSocket + Redis)
        """
        try:
            # task_id 由调用方（如 Celery task）传入，保持 ID 一致
            # 如果未传入（agent 直接调用场景），则生成一个
            import uuid
            effective_task_id = task_id or str(uuid.uuid4())
            
            from app.services.testcase_generation_service import testcase_generation_service
            
            result_data = testcase_generation_service.generate_from_jira_sync(
                jira_key=jira_key,
                linked_req_keys=linked_req_keys,
                task_id=effective_task_id
            )

            if result_data.get('status') == 'SUCCESS':
                data = result_data.get('result') or {}
                testcases = data.get("testcases", [])
                analysis = data.get("analysis", [])
                
                md_output = f"### Generated {len(testcases)} Test Cases for {jira_key}\n\n"
                
                # Render Analysis Context (including RAG status) directly to LLM output
                if isinstance(analysis, list) and analysis:
                    md_output += "#### Analysis & Context Highlights\n"
                    for item in analysis[:8]:  # Show more items to ensure RAG status is visible
                        # Ensure bullet point format
                        if not item.startswith('-') and not item.startswith('*'):
                            item = f"- {item}"
                        md_output += f"{item}\n"
                    md_output += "\n"

                rag_summary = data.get("rag_summary") or {}
                if isinstance(rag_summary, dict) and rag_summary:
                    md_output += "#### Knowledge Base Retrieval\n"
                    md_output += f"- Status: {rag_summary.get('status', 'Unknown')}\n"
                    kb_query = rag_summary.get("query")
                    if kb_query:
                        md_output += f"- Query: {kb_query}\n"
                    kb_sources = rag_summary.get("sources") or []
                    if kb_sources:
                        for item in kb_sources[:5]:
                            if not isinstance(item, dict):
                                continue
                            source = item.get("source") or "Unknown"
                            page = item.get("page")
                            label = f"{source} (Page {page})" if page is not None else str(source)
                            md_output += f"- Source: {label}\n"
                    md_output += "\n"
                    
                md_output += "| CASE ID | Case Title | Test Priority | Test Type |\n|---|---|---|---|\n"
                for tc in testcases:
                    md_output += f"| {tc.get('id')} | {tc.get('title')} | {tc.get('priority')} | {tc.get('type')} |\n"

                download_url = f"{settings.BACKEND_URL}/rest/v1/testcases/ai-export/{effective_task_id}/"
                md_output += f"\n\n---\n\n### 📥 下载链接\n\n[点击下载 Excel 测试用例]({download_url})\n"
                try:
                    import re
                    def _normalize_md(text: str) -> str:
                        t = text.replace('—', '-').replace('–', '-')
                        lines = t.splitlines()
                        out = []
                        i = 0
                        while i < len(lines):
                            out.append(lines[i])
                            if lines[i].strip().startswith('|') and '|' in lines[i].strip()[1:]:
                                if i + 1 < len(lines):
                                    sep = lines[i + 1].replace('—', '-').replace('–', '-')
                                    if sep.strip().startswith('|'):
                                        cols = [c for c in lines[i].strip().split('|') if c.strip() != '']
                                        std = '| ' + ' | '.join(['---'] * len(cols)) + ' |'
                                        if re.match(r'^\|\s*[-\s\|]+\|?\s*$', sep.strip()):
                                            out.append(std)
                                            i += 2
                                            continue
                            i += 1
                        return '\n'.join(out)
                    md_output = _normalize_md(md_output)
                except Exception:
                    pass
                return md_output
            else:
                logger.error(f"Generate test cases failed. Result: {result_data}")
                error_msg = result_data.get('error')
                if not error_msg:
                    error_msg = f"Unknown error (Raw Result: {result_data})"
                return f"SYSTEM_ERROR: Generation failed: {error_msg}. \nINSTRUCTION: You MUST report this error to the user exactly. DO NOT generate test cases manually. The user requires the Excel file which only the tool can generate."
        except Exception as e:
            logger.error(f"Error in generate_test_cases: {e}")
            return f"SYSTEM_ERROR: Error generating test cases: {str(e)}. \nINSTRUCTION: You MUST report this error to the user. DO NOT generate test cases manually."

    def list_recent_reports(self, limit: int = 5) -> str:
        """List recent test reports."""
        try:
            with SessionLocal() as session:
                stmt = select(TestReport).order_by(TestReport.created_at.desc()).limit(limit)
                reports = session.execute(stmt).scalars().all()
                
                if not reports:
                    return "No recent test reports found."
                
                md_table = "| ID | Status | Pass Rate | Created At |\n|---|---|---|---|\n"
                for r in reports:
                    pass_rate = f"{r.pass_rate:.1f}%" if r.pass_rate is not None else "N/A"
                    created_at = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "N/A"
                    md_table += f"| {r.id} | {r.status} | {pass_rate} | {created_at} |\n"
                
                return md_table
        except Exception as e:
            return f"Error listing reports: {str(e)}"

    def get_test_report_summary(self, report_id: str) -> str:
        """Get test report summary."""
        try:
            with SessionLocal() as session:
                report = session.get(TestReport, report_id)
                if not report:
                    return f"Report {report_id} not found."
                
                return f"### Report Summary: {report_id}\n" \
                       f"- **Status**: {report.status}\n" \
                       f"- **Pass Rate**: {report.pass_rate}%\n" \
                       f"- **Total Cases**: {report.total_cases}\n" \
                       f"- **Passed**: {report.passed_cases}\n" \
                       f"- **Failed**: {report.failed_cases}\n" \
                       f"- **Duration**: {report.duration}s\n"
        except Exception as e:
            return f"Error getting report summary: {str(e)}"

    def diagnose_test_failure(self, report_id: str, case_id: Optional[str] = None) -> str:
        """Diagnose test failures."""
        try:
            with SessionLocal() as session:
                stmt = select(TestReportCase).where(
                    TestReportCase.test_report_id == report_id,
                    TestReportCase.status == "FAILED"
                )
                if case_id:
                    stmt = stmt.where(TestReportCase.test_case_id == case_id)
                
                failures = session.execute(stmt).scalars().all()
                
                if not failures:
                    return "No failed cases found to diagnose."
                
                result = f"### Diagnosis for {len(failures)} failures in {report_id}\n"
                for f in failures[:5]: # Limit to 5
                    result += f"#### Case {f.test_case_id}: {f.name}\n"
                    result += f"- **Error**: {f.error_message}\n"
                    result += f"- **Suggestion**: Check logs and data setup.\n\n"
                
                return result
        except Exception as e:
            return f"Error diagnosing failure: {str(e)}"

    def run_sql_query(self, query: str) -> str:
        """Run safe SQL query."""
        if not query.lower().strip().startswith("select"):
            return "Only SELECT queries are allowed."
        
        try:
            with SessionLocal() as session:
                result = session.execute(text(query))
                rows = result.fetchall()
                if not rows:
                    return "No results."
                
                keys = result.keys()
                md_table = "| " + " | ".join(keys) + " |\n"
                md_table += "| " + " | ".join(["---"] * len(keys)) + " |\n"
                
                for row in rows[:10]:
                    md_table += "| " + " | ".join([str(v) for v in row]) + " |\n"
                
                if len(rows) > 10:
                    md_table += f"\n*...and {len(rows)-10} more rows.*"
                
                return md_table
        except Exception as e:
            return f"Error executing SQL: {str(e)}"

    def create_skill_file(self, name: str, description: str, content: str) -> str:
        """Create a new local Skill file (.md) and register it at runtime."""
        import re
        skills_dir = os.path.join(os.getcwd(), "app/prompts/skills")
        os.makedirs(skills_dir, exist_ok=True)

        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return f"Error: Skill name must contain only letters, numbers, hyphens, underscores. Got: '{name}'"

        filepath = os.path.join(skills_dir, f"{name}.md")
        if os.path.exists(filepath):
            return f"Error: Skill '{name}' already exists."

        frontmatter = (
            f"---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"source: local\n"
            f"created_by: agent\n"
            f"created_at: {datetime.now().isoformat()}\n"
            f"---\n\n"
        )
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(frontmatter + content)

        self.SKILL_REGISTRY[name] = {"description": description, "filename": f"{name}.md"}

        return (f"Skill '{name}' created at {filepath}.\n"
                f"Description: {description}\n"
                f"Available immediately in this session.")

    def get_skill_directory(self) -> str:
        """Return a list of all locally installed Skills."""
        lines = ["# Available Skills (Local)\n"]
        if not self.SKILL_REGISTRY:
            lines.append("- No skills installed yet.\n")
            lines.append("\nUse `list_remote_skills` to browse available skills from GitHub.")
            return "\n".join(lines)

        for skill_name, info in sorted(self.SKILL_REGISTRY.items()):
            desc = info.get("description", "No description")
            lines.append(f"- **{skill_name}**: {desc}")
        lines.append("\nUse `list_remote_skills` to browse remote skills.")
        return "\n".join(lines)

    def list_remote_skills(self, query: str = "") -> str:
        """Browse available skills from the GitHub anthropics/skills repository."""
        import urllib.request
        import json

        url = "https://api.github.com/repos/anthropics/skills/contents/skills"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                items = json.loads(resp.read().decode())

            skills = []
            for item in items:
                if item["type"] == "dir":
                    name = item["name"]
                    if query and query.lower() not in name.lower():
                        continue
                    skills.append(f"- **{name}**: https://github.com/anthropics/skills/tree/main/skills/{name}")

            if not skills:
                return f"No remote skills found matching '{query}'."

            header = f"# Remote Skills from GitHub (anthropics/skills)\nFiltered by: '{query}'\n" if query else "# Remote Skills from GitHub (anthropics/skills)\n"
            return header + "\n".join(skills) + "\n\nUse `install_skill(name)` to install one."
        except Exception as e:
            return f"Error fetching remote skills: {e}"

    def install_skill(self, name: str) -> str:
        """Install a skill from the GitHub anthropics/skills repository."""
        import urllib.request
        import urllib.error

        if name in self.SKILL_REGISTRY:
            return f"Skill '{name}' is already installed locally."

        url = f"https://raw.githubusercontent.com/anthropics/skills/main/skills/{name}/SKILL.md"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")

            skills_dir = os.path.join(os.getcwd(), "app/prompts/skills")
            os.makedirs(skills_dir, exist_ok=True)

            lines = content.splitlines()
            if lines and lines[0] == "---":
                end = next((i for i, l in enumerate(lines[1:], 1) if l == "---"), None)
                if end:
                    fm_lines = ["---"]
                    fm_lines.append(f"name: {name}")
                    for line in lines[1:end]:
                        if line.startswith("description:"):
                            fm_lines.append(line)
                    fm_lines.append("source: github:anthropics/skills")
                    fm_lines.append(f"installed_at: {datetime.now().isoformat()}")
                    fm_lines.append("---")
                    content = "\n".join(fm_lines) + "\n" + "\n".join(lines[end + 1:])

            filepath = os.path.join(skills_dir, f"{name}.md")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            self.SKILL_REGISTRY[name] = {
                "description": f"Installed from GitHub: {name}",
                "filename": f"{name}.md"
            }

            return (f"Skill '{name}' installed successfully from GitHub.\n"
                    f"File: {filepath}\n"
                    f"Available immediately in this session.")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return f"Skill '{name}' not found in anthropics/skills repository."
            return f"HTTP error {e.code}: {e.reason}"
        except Exception as e:
            return f"Error installing skill '{name}': {e}"

    def get_jira_trend_chart(self, project_key: str, start_date: str = None, end_date: str = None, version_type: str = "all", **kwargs) -> str:
        """Get Jira trend chart by version."""
        try:
            limit = kwargs.get('limit')
            fix_versions = kwargs.get('fix_versions')
            
            # Determine start_date
            if not start_date and not limit:
                # Default to last 6 months if not provided AND no limit is specified
                start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
                time_label = "Last 6 Months"
            elif limit:
                time_label = f"Last {limit} Versions"
            else:
                time_label = f"Since {start_date}"
                if end_date:
                    time_label += f" to {end_date}"
            
            # Use ai_service to get version trend data
            # This ensures X-axis displays Version Numbers instead of Months
            trend_data = self.ai_service.get_project_version_trend(
                project_key, 
                start_date=start_date, 
                end_date=end_date, 
                version_type=version_type,
                limit=limit,
                fix_versions=fix_versions
            )
            
            if "error" in trend_data:
                return f"Error generating trend chart: {trend_data['error']}"
            
            items = trend_data.get("items", [])
            if not items:
                return f"No {version_type if version_type != 'all' else ''} version data found for project {project_key} in {time_label}."
            
            # Prepare ECharts data
            versions = [item['version'] for item in items]
            bug_counts = [item['bug_count'] for item in items]
            task_counts = [item['demand_count'] for item in items] 
            
            option = {
                "title": {"text": f"Version Trend ({project_key}) - {time_label} ({version_type})", "left": "center"},
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["Bug", "Task"], "bottom": 0},
                "xAxis": {
                    "type": "category", 
                    "data": versions,
                    "axisLabel": {"interval": 0, "rotate": 30} # Rotate labels to avoid overlap
                },
                "yAxis": {"type": "value"},
                "series": [
                    {"name": "Bug", "type": "line", "data": bug_counts},
                    {"name": "Task", "type": "line", "data": task_counts}
                ]
            }
            
            return f"```echarts\n{json.dumps(option, ensure_ascii=False, indent=2)}\n```"

        except Exception as e:
            return f"Error generating trend chart: {str(e)}"

    def get_jira_bug_distribution_chart(self, project_key: str, start_date: str = None, end_date: str = None, version_type: str = "all", **kwargs) -> str:
        """Get bug distribution charts (Severity Pie & Module Bar) for a project. Returns ECharts visualizations."""
        try:
            fix_versions = kwargs.get('fix_versions')
            
            # 仅在未指定修复版本时使用默认时间窗，避免「按版本看测试情况」时漏掉创建较早的 Bug
            # （与 Jira 中 fixVersion 无条件统计不一致，易出现少 1 条等问题）
            if not start_date and not fix_versions:
                start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
            
            # Use ai_service to get distribution data (supports v3 API and fix_versions filtering)
            data = self.ai_service.get_project_bug_distribution(
                project_key, 
                start_date=start_date, 
                end_date=end_date, 
                fix_versions=fix_versions,
                version_type=version_type
            )
            
            if "error" in data:
                return f"Error getting bug distribution: {data['error']}"
            
            if data.get("total_bugs", 0) == 0:
                 return f"No bugs found for project {project_key} (Versions: {fix_versions})."

            # 1. Severity Pie Chart
            severity_data = data.get("bug_severity", [])
            pie_data = [{"name": item["name"], "value": item["count"]} for item in severity_data]
            
            pie_option = {
                "title": {"text": f"Bug Severity Distribution", "left": "center"},
                "tooltip": {"trigger": "item"},
                "legend": {"orient": "vertical", "left": "left"},
                "series": [
                    {
                        "name": "Severity",
                        "type": "pie",
                        "radius": "50%",
                        "data": pie_data,
                        "emphasis": {
                            "itemStyle": {
                                "shadowBlur": 10,
                                "shadowOffsetX": 0,
                                "shadowColor": "rgba(0, 0, 0, 0.5)"
                            }
                        }
                    }
                ]
            }
            
            # 2. Module Pie Chart (was Bar Chart)
            module_data = data.get("items", [])
            # Sort by bug count desc
            module_data.sort(key=lambda x: x["bug_count"], reverse=True)
            # Take top 10 modules
            top_modules = module_data[:10]
            
            # Prepare data for pie chart
            module_pie_data = [{"name": item["module"], "value": item["bug_count"]} for item in top_modules]
            
            bar_option = {
                "title": {"text": f"Top 10 Bug Modules", "left": "center"},
                "tooltip": {"trigger": "item"},
                "legend": {"type": "scroll", "orient": "vertical", "right": 10, "top": 20, "bottom": 20},
                "series": [
                    {
                        "name": "Module",
                        "type": "pie",
                        "radius": ["40%", "70%"], # Donut chart style for variety
                        "avoidLabelOverlap": False,
                        "itemStyle": {
                            "borderRadius": 10,
                            "borderColor": '#fff',
                            "borderWidth": 2
                        },
                        "label": {
                            "show": False,
                            "position": "center"
                        },
                        "emphasis": {
                            "label": {
                                "show": True,
                                "fontSize": 20,
                                "fontWeight": "bold"
                            }
                        },
                        "labelLine": {
                            "show": False
                        },
                        "data": module_pie_data
                    }
                ]
            }

            return (
                f"### Bug Distribution Charts\n\n"
                f"#### Severity Distribution\n"
                f"```echarts\n{json.dumps(pie_option, ensure_ascii=False, indent=2)}\n```\n\n"
                f"#### Module Distribution (Top 10)\n"
                f"```echarts\n{json.dumps(bar_option, ensure_ascii=False, indent=2)}\n```"
            )
            
        except Exception as e:
            return f"Error generating distribution charts: {str(e)}"

    def get_version_member_cycle_time_chart(self, project_key: str, versions: List[str]) -> str:
        """生成成员修复效率（Cycle Time）的 ECharts 柱状图配置。"""
        try:
            data = self.ai_service.get_version_member_cycle_time(project_key, versions)
            if "error" in data:
                return f"获取数据失败: {data['error']}"
            
            member_stats = data.get("member_cycle_time", [])
            if not member_stats:
                return f"未找到项目 `{project_key}` 版本 `{versions}` 的成员修复效率数据。"
            
            # 按平均耗时排序
            member_stats.sort(key=lambda x: x["avg_cycle_time_hours"], reverse=True)
            
            assignees = [m["assignee"] for m in member_stats]
            avg_hours = [m["avg_cycle_time_hours"] for m in member_stats]
            bug_counts = [m["bug_count"] for m in member_stats]
            
            option = {
                "title": { "text": f"成员 Bug 修复效率 (Avg Cycle Time)", "subtext": f"版本: {', '.join(versions)}", "left": "center" },
                "tooltip": { "trigger": "axis", "axisPointer": { "type": "shadow" } },
                "legend": { "data": ["平均修复时长(小时)", "修复 Bug 数"], "bottom": 0 },
                "grid": { "left": "3%", "right": "4%", "bottom": "15%", "containLabel": True },
                "xAxis": { "type": "category", "data": assignees, "axisLabel": { "rotate": 45, "interval": 0 } },
                "yAxis": [
                    { "type": "value", "name": "时长 (小时)" },
                    { "type": "value", "name": "Bug 数", "position": "right", "alignTicks": True }
                ],
                "series": [
                    { 
                        "name": "平均修复时长(小时)", 
                        "type": "bar", 
                        "data": avg_hours, 
                        "itemStyle": { "color": "#5470c6" },
                        "label": { "show": True, "position": "top" }
                    },
                    { 
                        "name": "修复 Bug 数", 
                        "type": "line", 
                        "yAxisIndex": 1,
                        "data": bug_counts, 
                        "itemStyle": { "color": "#91cc75" },
                        "symbolSize": 8
                    }
                ]
            }
            
            return f"以下是成员修复效率统计图表：\n\n```echarts\n{json.dumps(option, ensure_ascii=False, indent=2)}\n```"
        except Exception as e:
            return f"生成图表失败: {str(e)}"

    def get_jira_insight(self, project_key: str, versions: Optional[List[str]] = None, include_regression: bool = True, include_distribution: bool = True, include_statistics: bool = True, include_cycle_time: bool = True) -> str:
        """Get comprehensive insights about a Jira project/version."""
        try:
            if not project_key:
                project_key = "DM"

            # Check version status using real Jira data
            version_exists = False
            is_version_released = False
            
            # Fetch all project versions
            all_versions_data = self.ai_service.get_project_fix_versions(project_key)
            
            if isinstance(all_versions_data, dict) and "error" in all_versions_data:
                # Fallback if error occurs (e.g. project not found)
                version_exists = False
            elif versions:
                # Check if the requested version(s) exist and are released
                # We consider "released" if ANY of the requested versions is released (usually only one is requested)
                for v_name in versions:
                    # Clean up version name (remove quotes and whitespace)
                    clean_v_name = v_name.strip("'\"").strip()
                    
                    # Try exact match first
                    found_v = next((v for v in all_versions_data if v["name"] == clean_v_name), None)
                    
                    # If not found, try case-insensitive match
                    if not found_v:
                         found_v = next((v for v in all_versions_data if v["name"].lower() == clean_v_name.lower()), None)
                    
                    if found_v:
                        version_exists = True
                        if found_v.get("released"):
                            is_version_released = True
                            
            else:
                # If no specific version requested, we assume "recent" context which always exists
                version_exists = True
                is_version_released = False # Default for general insight

            results = []
            results.append(f"# Jira Insight for {project_key} - {versions if versions else 'Recent'}")
            
            if include_distribution:
                 results.append("## Bug Distribution")
                 results.append(self.get_jira_bug_distribution_chart(project_key, fix_versions=versions))
            
            if include_regression:
                results.append("## Regression Status")
                regression_data = self.ai_service.get_version_regression_status(project_key, versions)
                if isinstance(regression_data, list):
                    md_table = "| Version | Status | Open Bugs | Reopened Bugs |\n|---|---|---|---|\n"
                    for item in regression_data:
                        md_table += f"| {item.get('version')} | {item.get('status')} | {item.get('open_bugs')} | {item.get('reopened_bugs')} |\n"
                    results.append(md_table)
                    
                    # Add detailed list of unresolved bugs if any
                    for item in regression_data:
                        if item.get('open_bugs', 0) > 0 or item.get('reopened_bugs', 0) > 0:
                            v = item.get('version')
                            results.append(f"### Unresolved Bugs in {v}")
                            # Fetch specific unresolved bugs to show Assignee
                            bug_types = '"Bug", "缺陷"'
                            not_resolved_statuses = '"Closed", "Resolved", "Done", "已关闭", "已解决"'
                            jql_unresolved = f"project = {project_key} AND fixVersion = '{v}' AND issuetype in ({bug_types}) AND status not in ({not_resolved_statuses})"
                            
                            # Use _search_jql_v3 to avoid HTTP 410 (Jira API v2 deprecated)
                            search_result = self.ai_service._search_jql_v3(jql_unresolved, max_results=10, fields=["summary", "assignee", "status"])
                            unresolved_issues = search_result.get("issues", [])
                            
                            bug_table = "| Key | Summary | Assignee | Status |\n|---|---|---|---|\n"
                            for issue in unresolved_issues:
                                key = issue.get("key")
                                fields = issue.get("fields", {})
                                summary = fields.get("summary", "")
                                assignee_obj = fields.get("assignee")
                                assignee = assignee_obj.get("displayName") if assignee_obj else "Unassigned"
                                status_obj = fields.get("status", {})
                                status_name = status_obj.get("name", "Unknown")
                                
                                bug_table += f"| {key} | {summary} | {assignee} | {status_name} |\n"
                            results.append(bug_table)
                else:
                    results.append(f"Error fetching regression status: {regression_data}")

            if include_cycle_time and versions:
                results.append("## Member Cycle Time")
                results.append(self.get_version_member_cycle_time_chart(project_key, versions))
            
            # Return JSON structure as expected by the System Prompt
            response_data = {
                "version_exists": version_exists,
                "is_version_released": is_version_released,
                "project_key": project_key,
                "versions": versions,
                "analysis_content": "\n\n".join(results)
            }
            
            return json.dumps(response_data, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({"error": str(e), "version_exists": False})

    def export_testcases_excel(self, filename_prefix: str, testcases: List[Dict], analysis: List[str] | None = None, knowledge_sources: List[str] | None = None) -> Any:
        """Export testcases to Excel."""
        import io
        import openpyxl
        from openpyxl.styles import Alignment, Font, Border, Side
        import re

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Test Cases"

        normalized_testcases = []
        for tc in testcases:
            if not isinstance(tc, dict):
                continue
            normalized = dict(tc)
            if "expected_results" in normalized and "expected_result" not in normalized:
                exp = normalized.get("expected_results")
                if isinstance(exp, list):
                    normalized["expected_result"] = "\n".join(str(x) for x in exp if str(x).strip())
                elif exp is not None:
                    normalized["expected_result"] = str(exp)
            if normalized.get("preconditions") and not normalized.get("precondition"):
                normalized["precondition"] = normalized.get("preconditions")
            steps = normalized.get("steps", [])
            if isinstance(steps, str):
                normalized["steps"] = [line.strip() for line in steps.splitlines() if line.strip()]
            normalized_testcases.append(normalized)

        if analysis:
            analysis_ws = wb.create_sheet(title="Analysis")
            analysis_ws.cell(row=1, column=1, value="Analysis Highlights")
            analysis_ws.cell(row=1, column=1).font = Font(bold=True)
            for idx, item in enumerate(analysis, 2):
                analysis_ws.cell(row=idx, column=1, value=item)
            analysis_ws.column_dimensions['A'].width = 120

        if knowledge_sources:
            kb_ws = wb.create_sheet(title="Knowledge Base")
            kb_ws.cell(row=1, column=1, value="Knowledge Sources")
            kb_ws.cell(row=1, column=1).font = Font(bold=True)
            for idx, item in enumerate(knowledge_sources, 2):
                kb_ws.cell(row=idx, column=1, value=item)
            kb_ws.column_dimensions['A'].width = 120

        # Headers (Updated to match Template and English requirement)
        headers = ["CASE ID", "Task", "Module", "Case Title", "Test Priority", "Test Type", "Pre-Condition", "Case Steps", "Expected Result"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")

        jira_key_for_task = ""
        if isinstance(normalized_testcases, list) and len(normalized_testcases) > 0:
            first_id = str(normalized_testcases[0].get("id", ""))
            m = re.match(r"^([A-Z]+-\d+)-\d{3}$", first_id)
            if m:
                jira_key_for_task = m.group(1)
        if not jira_key_for_task and re.match(r"^[A-Z]+-\d+$", str(filename_prefix)):
            jira_key_for_task = str(filename_prefix)

        # Data
        for row_idx, tc in enumerate(normalized_testcases, 2):
            # Format steps
            steps_text = ""
            steps_data = tc.get("steps", [])
            if isinstance(steps_data, list):
                for i, step in enumerate(steps_data, 1):
                    steps_text += f"{i}. {step}\n"
            else:
                steps_text = str(steps_data)

            ws.cell(row=row_idx, column=1, value=tc.get("id", ""))
            ws.cell(row=row_idx, column=2, value=jira_key_for_task or tc.get("task", ""))
            ws.cell(row=row_idx, column=3, value=tc.get("module", ""))
            ws.cell(row=row_idx, column=4, value=tc.get("title", ""))
            ws.cell(row=row_idx, column=5, value=tc.get("priority", ""))
            ws.cell(row=row_idx, column=6, value=tc.get("type", ""))
            ws.cell(row=row_idx, column=7, value=tc.get("precondition", ""))
            
            cell_steps = ws.cell(row=row_idx, column=8, value=steps_text.strip())
            cell_steps.alignment = Alignment(wrap_text=True, vertical="top")
            
            exp_value = tc.get("expected_results") if "expected_results" in tc else tc.get("expected_result", "")
            exp_list = []
            if isinstance(exp_value, list):
                exp_list = [str(x) for x in exp_value]
            elif isinstance(exp_value, str) and exp_value.strip():
                lines = [ln.strip() for ln in re.split(r"\r?\n", exp_value) if ln.strip()]
                exp_list = lines
            step_count = len(steps_data) if isinstance(steps_data, list) else 0
            expected_text = ""
            if step_count: 
                for i in range(step_count):
                    txt = exp_list[i] if i < len(exp_list) else f"Step {i+1} completes with expected outcome."
                    expected_text += f"{i+1}. {txt}\n"
            else:
                expected_text = exp_value if isinstance(exp_value, str) else "\n".join(exp_list)
            cell_expected = ws.cell(row=row_idx, column=9, value=expected_text.strip())
            cell_expected.alignment = Alignment(wrap_text=True, vertical="top")

        # Adjust column widths
        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 25
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 30
        ws.column_dimensions['E'].width = 10
        ws.column_dimensions['F'].width = 12
        ws.column_dimensions['G'].width = 30
        ws.column_dimensions['H'].width = 50
        ws.column_dimensions['I'].width = 50

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer
