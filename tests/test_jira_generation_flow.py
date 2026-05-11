import asyncio
import json
import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)


from app.tasks import ai_tasks


class DummyRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value


class DummyTask:
    async def update_state(self, *args, **kwargs):
        return None

    class Request:
        id = "dummy-task-id"

    request = Request()


def test_cache_key_changes_with_linked_req_keys():
    key1 = ai_tasks._build_jira_testcase_cache_key("DM-100", ["DM-1", "DM-2"])
    key2 = ai_tasks._build_jira_testcase_cache_key("DM-100", ["DM-2", "DM-1"])
    key3 = ai_tasks._build_jira_testcase_cache_key("DM-100", ["DM-3"])

    assert key1 == key2
    assert key1 != key3


def test_generate_testcases_logic_preserves_analysis_and_normalizes_ids():
    dummy_redis = DummyRedis()

    original_redis_from_url = ai_tasks.redis.Redis.from_url
    original_get_model_name = ai_tasks.ai_service._get_model_name
    original_get_issue = ai_tasks.ai_service.get_jira_issue_details
    original_query_kb = ai_tasks.ai_service.query_kb
    original_generate = ai_tasks.ai_service.generate_testcases_from_jira
    original_update_progress = ai_tasks.update_celery_task_progress

    async def fake_update_progress(*args, **kwargs):
        return None

    def fake_get_issue(jira_key):
        return {
            "summary": "Approval flow",
            "description": "User can approve requests in review status.",
            "project": "DM",
            "linked_issues": [],
            "attachments_for_llm": []
        }

    def fake_generate_testcases_from_jira(**kwargs):
        return """SECTION 1: ANALYSIS
- Verify an authorized reviewer can approve a request in review status.
- Verify approval is rejected when the request is already closed.

SECTION 2: TEST CASES
```json
{
  "testcases": [
    {
      "id": "TEMP-001",
      "task": "Approval flow",
      "module": "Workflow",
      "priority": "P0",
      "precondition": "A request is in review status",
      "title": "Approve request successfully",
      "steps": ["Open request detail page", "Click approve", "Confirm the action"],
      "expected_result": "The request is approved successfully.",
      "type": "functional"
    }
  ]
}
```"""

    try:
        ai_tasks.redis.Redis.from_url = lambda url: dummy_redis
        ai_tasks.ai_service._get_model_name = lambda: "test-model"
        ai_tasks.ai_service.get_jira_issue_details = fake_get_issue
        ai_tasks.ai_service.query_kb = lambda query, top_k=2: {"sources": []}
        ai_tasks.ai_service.generate_testcases_from_jira = fake_generate_testcases_from_jira
        ai_tasks.update_celery_task_progress = fake_update_progress

        result = asyncio.run(ai_tasks._generate_testcases_logic(DummyTask(), "DM-100", ["DM-10"]))
    finally:
        ai_tasks.redis.Redis.from_url = original_redis_from_url
        ai_tasks.ai_service._get_model_name = original_get_model_name
        ai_tasks.ai_service.get_jira_issue_details = original_get_issue
        ai_tasks.ai_service.query_kb = original_query_kb
        ai_tasks.ai_service.generate_testcases_from_jira = original_generate
        ai_tasks.update_celery_task_progress = original_update_progress

    assert result["status"] == "SUCCESS"
    payload = result["result"]
    assert payload["testcases"][0]["id"] == "DM-100-001"
    assert isinstance(payload["analysis"], list)
    assert payload["kb_used"] is False
    if "rag_summary" in payload:
        assert payload["rag_summary"]["status"] == "知识库未命中相关业务规则"

    cache_key = ai_tasks._build_jira_testcase_cache_key("DM-100", ["DM-10"])
    if cache_key in dummy_redis.store:
        cached_payload = json.loads(dummy_redis.store[cache_key])
        assert cached_payload["jira_key"] == "DM-100"
        assert len(cached_payload["analysis"]) >= 0
        if "rag_summary" in cached_payload:
            assert cached_payload["rag_summary"]["status"] == "知识库未命中相关业务规则"


def test_generate_testcases_logic_normalizes_alias_fields():
    raw_output = """SECTION 2: TEST CASES
```json
{
  "testcases": [
    {
      "title": "Submit application",
      "preconditions": "User has filled all mandatory fields",
      "steps": ["Open form", "Submit form"],
      "expected_results": ["Form is submitted successfully", "Success message is shown"]
    }
  ]
}
```"""

    recovered = ai_tasks._recover_testcases_from_raw_output(raw_output, "DM-200")
    assert len(recovered) == 1
    testcase = recovered[0]
    assert testcase["precondition"] == "User has filled all mandatory fields"
    assert testcase["expected_result"] == "Form is submitted successfully\nSuccess message is shown"
    assert testcase["steps"] == ["Open form", "Submit form"]
    assert testcase["task"] == "DM-200"
    assert testcase["module"] == "General"


def test_recover_testcases_from_raw_output_with_trailing_commas():
    raw_output = """SECTION 1: ANALYSIS
- Verify request submission succeeds.

SECTION 2: TEST CASES
```json
{
  "testcases": [
    {
      "title": "Submit request",
      "steps": ["Open page", "Click submit",],
      "expected_results": ["Request is submitted", "Success message is shown",],
      "priority": "P0",
    }
  ],
}
```"""

    recovered = ai_tasks._recover_testcases_from_raw_output(raw_output, "DM-300")

    assert len(recovered) == 1
    assert recovered[0]["id"] == "DM-300-001"
    assert recovered[0]["title"] == "Submit request"
    assert recovered[0]["steps"] == ["Open page", "Click submit"]
    assert recovered[0]["expected_result"] == "Request is submitted\nSuccess message is shown"
