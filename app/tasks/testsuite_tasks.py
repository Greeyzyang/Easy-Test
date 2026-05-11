import asyncio
from app.celery_app import celery_app
from app.database import async_session_maker
from app.models.testsuite import Testsuite
from app.services.testreport_service import TestreportService
from sqlalchemy import select
from app.utils.logger import get_logger
from app.utils.task_utils import publish_task_progress

logger = get_logger(__name__)

@celery_app.task(bind=True, name='execute_testsuite_task')
def execute_testsuite_task(self, testsuite_id: str):
    """
    Celery 任务：执行指定的测试套件 (同步包装器)
    """
    logger.info(f"Celery 任务 'execute_testsuite_task' 开始执行测试套件: {testsuite_id}")
    task_id = self.request.id
    try:
        # 使用 asyncio.run 执行异步核心逻辑
        return asyncio.run(async_execute_testsuite(testsuite_id, task_id))
    except Exception as e:
        logger.error(f"Celery 任务执行失败: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def async_execute_testsuite(testsuite_id: str, task_id: str = None):
    """
    异步核心逻辑
    """
    # 修复：Celery 任务中 asyncio.run() 会创建新循环，导致全局 engine 绑定的循环不一致。
    # 解决方案：在任务内部创建局部的 async engine。
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.config import DATABASE_URL
    
    local_engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    local_session_maker = async_sessionmaker(local_engine, expire_on_commit=False, class_=AsyncSession)
    
    async with local_session_maker() as db_session:
        try:
            statement = select(Testsuite).where(Testsuite.id == testsuite_id)
            testsuite = (await db_session.execute(statement)).scalar_one_or_none()

            if not testsuite:
                error_msg = f"未找到测试套件: {testsuite_id}"
                logger.error(error_msg)
                if task_id:
                    await publish_task_progress(task_id, "FAILURE", text=error_msg)
                return {"status": "error", "message": error_msg}

            logger.info(f"成功获取测试套件: {testsuite.name}")

            test_report_service = TestreportService(db_session)
            generated_report = await test_report_service.generate_report(
                testsuite_id=testsuite.id,
                env_name=testsuite.env_name,
                websocket_list=None,
                task_id=task_id
            )
            logger.info(f"测试报告创建成功，ID: {generated_report.id}")
            if task_id:
                await publish_task_progress(task_id, "SUCCESS", 100, "测试套件执行完成", report_id=generated_report.id)

            return {"status": "success", "report_id": generated_report.id}

        except Exception as e:
            await db_session.rollback()
            logger.error(f"执行测试套件 {testsuite_id} 失败: {str(e)}", exc_info=True)
            if task_id:
                await publish_task_progress(task_id, "FAILURE", text=f"执行失败: {str(e)}")
            return {"status": "error", "message": str(e)}
        finally:
             await local_engine.dispose()