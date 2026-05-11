import os
import sys
import json
import importlib.util

# Ensure project root is on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

LLM_PARSING_PATH = os.path.join(ROOT, "app", "utils", "llm_parsing.py")
spec = importlib.util.spec_from_file_location("llm_parsing", LLM_PARSING_PATH)
llm_parsing = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(llm_parsing)  # type: ignore


def run():
    cases = []

    # 1) Pure JSON object
    cases.append(('{ "testcases": [ {"id":"TC-001"} ] }', dict))

    # 2) JSON in ```json code fence
    cases.append(("""```json
{ "testcases": [ {"id":"TC-002"} ] }
```""", dict))

    # 3) JSON in ``` code fence
    cases.append(("""```
{ "testcases": [ {"id":"TC-003"} ] }
```""", dict))

    # 4) Mixed text + JSON extract
    cases.append((
        "analysis...\n{ \"testcases\": [ {\"id\":\"TC-004\"} ] }\nmore text",
        dict
    ))

    # 5) Trailing comma fix
    repaired = llm_parsing.repair_json_string('{ "a": 1, }')
    assert json.loads(repaired) == {"a": 1}

    # 6) List root
    cases.append((
        """```json
[
  {"id": "TC-005"},
  {"id": "TC-006"}
]
```""",
        list
    ))

    # 7) Mixed analysis section plus JSON block
    cases.append((
        """SECTION 1: ANALYSIS
- Verify the core approval flow works for an authorized user.
- Verify rejection is blocked when the item is already closed.

SECTION 2: TEST CASES
```json
{
  "testcases": [
    {"id": "TC-007", "title": "Approve item", "priority": "P0"}
  ]
}
```""",
        dict
    ))

    for idx, (content, expect_type) in enumerate(cases, 1):
        parsed = llm_parsing.extract_json_from_llm_output(content)
        assert parsed is not None, f"Case {idx} failed to parse"
        assert isinstance(parsed, expect_type), f"Case {idx} got {type(parsed)}, expected {expect_type}"

    print("llm_parsing tests passed")


if __name__ == "__main__":
    run()
