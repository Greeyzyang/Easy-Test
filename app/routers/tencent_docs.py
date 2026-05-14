from fastapi import APIRouter, HTTPException
from app.schemas.testcase_convert import (
    ConvertTestcaseRequest,
    TestcaseRecord,
)
from app.services.tencent_docs_service import get_tencent_docs_service
from app.utils.response import create_response, ResponseModel
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/rest/v1/tencent-docs", tags=["tencent-docs"])


@router.post("/convert/testcases/", response_model=ResponseModel)
async def convert_testcases(request: ConvertTestcaseRequest):
    """
    将腾讯文档中的测试用例转换为卡片样式 HTML。

    - 传入腾讯文档的完整 URL（包含 tab 参数）和 Jira 单号
    - 直接定位到指定 sheet 获取测试用例
    - 返回卡片样式的 HTML，可直接在页面中渲染
    """
    logger.info(f"测试用例转换请求: url={request.doc_url}, jira={request.jira_id}")

    try:
        service = get_tencent_docs_service()
        result = await service.convert_testcases(
            doc_url=request.doc_url,
            jira_id=request.jira_id,
        )

        records = [
            TestcaseRecord(
                case_id=r["case_id"],
                task=r["task"],
                module=r["module"],
                test_priority=r["test_priority"],
                pre_condition=r["pre_condition"],
                case_title=r["case_title"],
                case_steps=r["case_steps"],
                expected_result=r["expected_result"],
                actual_results=r["actual_results"],
                tester=r["tester"],
                run_time=r["run_time"],
                note=r["note"],
                copy_text=r.get("copy_text", ""),
            )
            for r in result["records"]
        ]

        return await create_response(data={
            "jira_id": result["jira_id"],
            "module_name": result["module_name"],
            "total_count": result["total_count"],
            "records": [r.model_dump() for r in records],
            "card_html": result["card_html"],
        })

    except ValueError as e:
        logger.warning(f"测试用例转换参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"测试用例转换运行时错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"测试用例转换失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")
