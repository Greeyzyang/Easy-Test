import re
from pydantic import BaseModel, Field
from typing import List, Optional


class ConvertTestcaseRequest(BaseModel):
    """测试用例格式转换请求"""
    doc_url: str = Field(..., description="腾讯文档完整 URL，如 https://docs.qq.com/sheet/DSVNDeERaUnpSc1VF?u=xxx&tab=f6ilfw")
    jira_id: Optional[str] = Field(None, description="Jira 单号，用于过滤测试用例，如 DM-19290")


class TestcaseRecord(BaseModel):
    """转换后的单条测试用例记录"""
    case_id: int = Field(..., description="用例序号")
    task: str = Field(default="", description="Jira 单号，如 DM-19290")
    module: str = Field(..., description="所属模块，如 laws")
    test_priority: str = Field(default="", description="测试优先级：Medium/Important/Low")
    pre_condition: str = Field(default="", description="前置条件")
    case_title: str = Field(..., description="用例标题")
    case_steps: str = Field(default="", description="测试步骤")
    expected_result: str = Field(default="", description="预期结果")
    actual_results: str = Field(default="", description="实际结果")
    tester: str = Field(default="", description="测试人员")
    run_time: str = Field(default="", description="执行时间")
    note: str = Field(default="", description="备注")
    copy_text: str = Field(default="", description="用于复制到剪贴板的 Markdown 文本")


class ConvertTestcaseResponse(BaseModel):
    """测试用例格式转换响应"""
    jira_id: str = Field(..., description="Jira 单号")
    module_name: str = Field(..., description="模块名称")
    total_count: int = Field(..., description="测试用例总数")
    records: List[TestcaseRecord] = Field(default_factory=list, description="转换后的测试用例列表")
    card_html: str = Field(..., description="卡片样式的 HTML")
