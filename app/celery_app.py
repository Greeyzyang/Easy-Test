import os
from celery import Celery
from app.config import REDIS_URL

# 初始化 Celery 应用
# broker: 消息代理，用于存储任务队列
# backend: 结果后端，用于存储任务执行结果
os.environ.setdefault('OBJC_DISABLE_INITIALIZE_FORK_SAFETY', 'YES')
celery_app = Celery(
    'fastapi_project',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        'app.tasks.testsuite_tasks',
        'app.tasks.ai_tasks',  # 加上这一行
    ]
)

# 可选：配置 Celery 时区和任务序列化方式
celery_app.conf.update(
    timezone='Asia/Shanghai', # 设置时区为上海
    enable_utc=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    beat_scheduler='celery.beat.PersistentScheduler', # 持久化调度器，用于保存定时任务状态
    beat_schedule={}, # 初始的定时任务列表，我们将通过API动态添加
    worker_pool='solo'
)

# 在 Celery Beat 启动后，读取数据库中的 cron_expression，为每个测试套件注册定时任务
from celery.schedules import crontab
from app.database import SessionLocal
from app.models.testsuite import Testsuite
# 新增：直接导入任务函数，避免名字解析差异
from app.tasks.testsuite_tasks import execute_testsuite_task

def _parse_cron(cron_expression: str):
    parts = cron_expression.strip().split()
    # Celery 官方 crontab 不支持“秒”字段，这里忽略第一个“秒”字段
    if len(parts) == 6:
        parts = parts[1:]
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expression}")
    minute, hour, day_of_month, month_of_year, day_of_week = parts
    return crontab(minute=minute, hour=hour, day_of_month=day_of_month, month_of_year=month_of_year, day_of_week=day_of_week)

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """在 Beat 进程中，启动时从数据库加载所有定时任务"""
    session = SessionLocal()
    try:
        suites = session.query(Testsuite).filter(Testsuite.cron_expression.isnot(None)).all()
        for s in suites:
            try:
                schedule = _parse_cron(s.cron_expression)
                sender.add_periodic_task(
                    schedule,
                    # 修改：使用任务对象的签名，确保与 worker 注册一致
                    execute_testsuite_task.s(s.id),
                    name=f"schedule_testsuite_{s.id}",
                )
                print(f"✓ 注册定时任务 schedule_testsuite_{s.id}: {s.cron_expression}")
            except Exception as e:
                print(f"! 注册 {s.id} 失败: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    celery_app.start()
