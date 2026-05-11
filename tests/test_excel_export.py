import os
import sys

import openpyxl


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)


from app.services.agent_service import AgentService


def test_export_includes_analysis_sheet():
    service = AgentService()
    testcases = [
        {
            "id": "DM-18900-001",
            "title": "Test Login",
            "priority": "P0",
            "type": "functional",
            "precondition": "User exists",
            "steps": ["Open URL", "Login"],
            "expected_result": "Success"
        }
    ]
    analysis = [
        "Verify the login path succeeds for a valid user.",
        "Verify invalid credentials are rejected with a clear error."
    ]

    buffer = service.export_testcases_excel("DM-18900", testcases, analysis)
    workbook = openpyxl.load_workbook(buffer)

    assert "Test Cases" in workbook.sheetnames
    assert "Analysis" in workbook.sheetnames
    assert workbook["Analysis"].cell(row=2, column=1).value == analysis[0]


def test_export_includes_knowledge_base_sheet():
    service = AgentService()
    testcases = [
        {
            "id": "DM-18903-001",
            "title": "Review request",
            "priority": "P1",
            "type": "functional",
            "precondition": "Request exists",
            "steps": ["Open request", "Review details"],
            "expected_result": "Request details are displayed"
        }
    ]
    knowledge_sources = ["approval-flow.pdf (Page 4)", "permission-rules.md"]

    buffer = service.export_testcases_excel("DM-18903", testcases, None, knowledge_sources)
    workbook = openpyxl.load_workbook(buffer)

    assert "Knowledge Base" in workbook.sheetnames
    assert workbook["Knowledge Base"].cell(row=2, column=1).value == knowledge_sources[0]


def test_export_normalizes_alias_fields():
    service = AgentService()
    testcases = [
        {
            "id": "DM-18901-001",
            "title": "Submit request",
            "priority": "P1",
            "type": "functional",
            "preconditions": "User is logged in",
            "steps": "Open page\nClick submit",
            "expected_results": ["Submission succeeds", "Confirmation is shown"]
        }
    ]

    buffer = service.export_testcases_excel("DM-18901", testcases)
    workbook = openpyxl.load_workbook(buffer)
    sheet = workbook["Test Cases"]

    assert sheet.cell(row=2, column=7).value == "User is logged in"
    assert sheet.cell(row=2, column=8).value == "1. Open page\n2. Click submit"
    assert sheet.cell(row=2, column=9).value == "1. Submission succeeds\n2. Confirmation is shown"


def test_export_handles_raw_string_steps_and_expected_results_string():
    service = AgentService()
    testcases = [
        {
            "id": "DM-18902-001",
            "title": "Approve request",
            "priority": "P0",
            "type": "functional",
            "precondition": "Request is pending approval",
            "steps": "Open request\nClick approve",
            "expected_result": "Request status becomes approved"
        }
    ]

    buffer = service.export_testcases_excel("DM-18902", testcases)
    workbook = openpyxl.load_workbook(buffer)
    sheet = workbook["Test Cases"]

    assert sheet.cell(row=2, column=8).value == "1. Open request\n2. Click approve"
    assert sheet.cell(row=2, column=9).value == "1. Request status becomes approved\n2. Step 2 completes with expected outcome."
