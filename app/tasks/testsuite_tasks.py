import asyncio
from app.celery_app import celery_app
from app.database import async_session_maker
from app.models.testsuite import Testsuite
from app.services.testreport_service import TestreportService
import logging
from sqlalchemy import select

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name='execute_testsuite_task')
async def execute_testsuite_task(self, testsuite_id: str):
    """
    Celery 任务：执行指定的测试套件
    """
    logger.info(f"Celery 任务 'execute_testsuite_task' 开始执行测试套件: {testsuite_id}")

    async with async_session_maker() as db_session:
        try:
            statement = select(Testsuite).where(Testsuite.id == testsuite_id)
            testsuite = (await db_session.execute(statement)).scalar_one_or_none()

            if not testsuite:
                logger.error(f"未找到测试套件: {testsuite_id}")
                return {"status": "error", "message": f"未找到测试套件: {testsuite_id}"}

            logger.info(f"成功获取测试套件: {testsuite.name}")

            test_report_service = TestreportService(db_session)
            generated_report = await test_report_service.generate_report(
                testsuite_id=testsuite.id,
                project_id=testsuite.project_id,
                env_name=testsuite.env_name,
                websocket_list=None
            )
            logger.info(f"测试报告创建成功，ID: {generated_report.id}")

            return {"status": "success", "report_id": generated_report.id}

        except Exception as e:
            await db_session.rollback()
            logger.error(f"执行测试套件 {testsuite_id} 失败: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}