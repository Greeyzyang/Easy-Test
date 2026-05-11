import asyncio
from app.celery_app import celery_app
from app.database import async_session_maker, DATABASE_URL
from app.models import PerformanceTest
from app.services.performance_test_service import PerformanceTestService
from app.utils.logger import get_logger
from app.utils.task_utils import update_celery_task_progress, publish_task_progress

logger = get_logger(__name__)


async def _progress_callback(report_id: str, status: str, progress: int, text: str, task=None, **kwargs):
    extra_data = {k: v for k, v in kwargs.items() if k not in ("report_id",)}
    if task:
        await update_celery_task_progress(
            task, progress, text, status,
            report_id=report_id, **extra_data
        )
    else:
        await publish_task_progress(
            task_id="unknown",
            status=status,
            progress=progress,
            text=text,
            report_id=report_id,
            **extra_data
        )


@celery_app.task(bind=True, name="run_performance_test_task")
def run_performance_test_task(self, performance_test_id: str):
    logger.info(f"Celery task 'run_performance_test_task' starting for performance_test: {performance_test_id}")
    task_id = self.request.id
    try:
        return asyncio.run(_async_run_performance_test(performance_test_id, task_id))
    except Exception as e:
        logger.error(f"Performance test task failed: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def _async_run_performance_test(performance_test_id: str, task_id: str):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    local_engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    local_session_maker = async_sessionmaker(local_engine, expire_on_commit=False, class_=AsyncSession)

    async with local_session_maker() as db_session:
        try:
            service = PerformanceTestService(db_session)
            callback = lambda **kw: _progress_callback(task=self, **kw)
            report = await service.run_performance_test(
                performance_test_id=performance_test_id,
                task_id=task_id,
                progress_callback=callback,
            )
            await db_session.commit()
            logger.info(f"Performance test report created: {report.id}")
            return {"status": "success", "report_id": report.id}
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Performance test {performance_test_id} failed: {str(e)}", exc_info=True)
            await publish_task_progress(
                task_id=task_id,
                status="FAILURE",
                progress=0,
                text=f"Performance test failed: {str(e)}",
            )
            return {"status": "error", "message": str(e)}
        finally:
            await local_engine.dispose()
