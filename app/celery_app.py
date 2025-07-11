from celery import Celery
from app.config import REDIS_URL

# 初始化 Celery 应用
# broker: 消息代理，用于存储任务队列
# backend: 结果后端，用于存储任务执行结果
celery_app = Celery(
    'fastapi_project',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['app.tasks.testsuite_tasks'] # 稍后我们将在这个文件中定义任务
)

# 可选：配置 Celery 时区和任务序列化方式
celery_app.conf.update(
    timezone='Asia/Shanghai', # 设置时区为上海
    enable_utc=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    beat_scheduler='celery.beat.PersistentScheduler', # 持久化调度器，用于保存定时任务状态
    beat_schedule={} # 初始的定时任务列表，我们将通过API动态添加
)

if __name__ == '__main__':
    celery_app.start() 