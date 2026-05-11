import json
import asyncio
import redis
from app.celery_app import celery_app
from app.services.ai_service import ai_service
from app.services.testcase_generation_service import testcase_generation_service
from app.utils.logger import get_logger
from app.config import REDIS_URL
from app.utils.task_utils import update_celery_task_progress, publish_task_progress
from app.database import async_session_maker
from sqlalchemy import select
from app.models.interface import Interface
from app.utils.llm_parsing import extract_json_from_llm_output

logger = get_logger(__name__)


def _build_jira_testcase_cache_key(jira_key: str, linked_req_keys: list[str] | None = None) -> str:
    return testcase_generation_service._build_jira_testcase_cache_key(jira_key, linked_req_keys)


def _recover_testcases_from_raw_output(llm_response: str, jira_key: str) -> list[dict]:
    return testcase_generation_service._recover_testcases_from_raw_output(llm_response, jira_key)


async def _generate_testcases_logic(self, jira_key: str, linked_req_keys: list[str] | None = None):
    return await testcase_generation_service.generate_from_jira(
        jira_key=jira_key,
        linked_req_keys=linked_req_keys,
        task_id=getattr(getattr(self, "request", None), "id", None),
        celery_task=self,
    )

# -------------------------------------------------------------------------
# 1. Generate Test Cases from Jira (Async Logic + Sync Wrapper)
# -------------------------------------------------------------------------

@celery_app.task(bind=True)
def generate_testcases_task(self, jira_key: str, linked_req_keys: list[str] | None = None):
    """
    [Sync Wrapper] Generate test cases from Jira.
    Compatible with Celery solo worker.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        testcase_generation_service.generate_from_jira(
            jira_key=jira_key, 
            linked_req_keys=linked_req_keys, 
            task_id=self.request.id, 
            celery_task=self
        )
    )


# -------------------------------------------------------------------------
# 2. Generate Interface Test Cases (Async Logic + Sync Wrapper)
# -------------------------------------------------------------------------

async def _generate_interface_testcases_logic(self, interface_id: str):
    """
    [Async Core] Generate test cases from Interface definition.
    """
    try:
        # _get_model_name is a synchronous method in AIService
        current_model = ai_service._get_model_name()
    except Exception:
        current_model = "AI"

    try:
        await update_celery_task_progress(self, 10, f'获取接口信息...（{current_model}）')
        
        # 1. Fetch Interface Details from DB
        interface_data = None
        async with async_session_maker() as session:
            stmt = select(Interface).where(Interface.id == interface_id)
            result = await session.execute(stmt)
            interface = result.scalars().first()
            if interface:
                interface_data = {
                    "name": interface.name,
                    "url": interface.url,
                    "method": interface.method.value if hasattr(interface.method, 'value') else str(interface.method),
                    "description": interface.description,
                    "headers": interface.headers,
                    "params": interface.params,
                    "body": interface.body
                }
        
        if not interface_data:
            error_msg = f"接口 ID {interface_id} 不存在"
            await update_celery_task_progress(self, 100, error_msg, status='FAILURE')
            return {'status': 'FAILURE', 'error': error_msg}

        # 2. Generate Test Cases
        await update_celery_task_progress(self, 40, f'AI 正在分析接口并生成用例...（{current_model}）')
        
        # Note: generate_testcases_from_interface returns dict (parsed) or dict with error
        result = ai_service.generate_testcases_from_interface(interface_data)
        
        if "error" in result:
             await update_celery_task_progress(self, 100, f"生成失败: {result['error']}", status='FAILURE')
             return {'status': 'FAILURE', 'error': result['error']}

        # 3. Complete
        await update_celery_task_progress(self, 100, '生成完成', status='SUCCESS', result=result)
        return {'status': 'SUCCESS', 'result': result}

    except Exception as e:
        logger.error(f"Interface task failed: {e}")
        await update_celery_task_progress(self, 100, f'任务执行失败: {str(e)}', status='FAILURE')
        return {'status': 'FAILURE', 'error': str(e)}

@celery_app.task(bind=True)
def generate_interface_testcases_task(self, interface_id: str):
    """
    [Sync Wrapper] Generate test cases from Interface.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    return loop.run_until_complete(_generate_interface_testcases_logic(self, interface_id))


# -------------------------------------------------------------------------
# 3. Generate KB Answer / RAG (Async Logic + Sync Wrapper)
# -------------------------------------------------------------------------

async def _generate_kb_answer_logic(self, query: str, kb_name: str = "default", history: list = None):
    """
    [Async Core] RAG Query.
    """
    try:
        current_model = await ai_service._get_model_name()
    except Exception:
        current_model = "AI"

    try:
        await update_celery_task_progress(self, 10, f'正在检索知识库...（{current_model}）')
        
        # 1. Query KB
        result = await ai_service.query_kb(query, top_k=3)
        
        # 2. Complete
        await update_celery_task_progress(self, 100, '检索完成', status='SUCCESS', result=result)
        return {'status': 'SUCCESS', 'result': result}

    except Exception as e:
        logger.error(f"KB task failed: {e}")
        await update_celery_task_progress(self, 100, f'任务执行失败: {str(e)}', status='FAILURE')
        return {'status': 'FAILURE', 'error': str(e)}

@celery_app.task(bind=True)
def generate_kb_answer_task(self, query: str, kb_name: str = "default", history: list = None):
    """
    [Sync Wrapper] RAG Query.
    """
    return asyncio.run(_generate_kb_answer_logic(self, query, kb_name, history))
