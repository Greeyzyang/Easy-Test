import json
import redis.asyncio as async_redis
from app.config import REDIS_URL
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def publish_task_progress(task_id: str, status: str, progress: int = 0, text: str = "", channel_prefix: str = "task:progress:", **kwargs):
    """
    统一的 Celery 任务进度推送工具 (异步)。
    
    :param task_id: 任务 ID
    :param status: 状态 (PROGRESS, SUCCESS, FAILURE, PENDING)
    :param progress: 进度百分比 (0-100)
    :param text: 状态描述文本
    :param channel_prefix: Redis 频道前缀，默认为 "task:progress:"
    :param kwargs: 其他需要发送的额外数据
    """
    try:
        r = await async_redis.from_url(REDIS_URL)
        channel = f"{channel_prefix}{task_id}"
        
        payload = {
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "text": text,
            **kwargs
        }
        
        logger.debug(f"[Task Progress Async] Channel: {channel}, Payload: {payload}")
        await r.publish(channel, json.dumps(payload, ensure_ascii=False))
        await r.close()
    except Exception as e:
        logger.error(f"Failed to publish task progress (async) to Redis: {str(e)}")




async def update_celery_task_progress(task, progress: int, text: str, status: str = "PROGRESS", channel_prefix: str = "task:progress:", **kwargs):
    """
    统一更新 Celery 任务状态并推送 WebSocket 消息 (异步)
    
    Args:
        task: Celery 任务实例 (self)
        progress: 进度百分比 (0-100)
        text: 进度描述文本
        status: 任务状态 ('PROGRESS', 'SUCCESS', 'FAILURE')，默认为 'PROGRESS'
        channel_prefix: Redis 频道前缀
        **kwargs: 其他需要包含在 meta/payload 中的数据
    """
    if not task or not task.request.id:
        logger.warning("Task instance or request ID missing, skipping progress update")
        return

    # 1. 更新 Celery 后端状态 (供轮询使用)
    # 注意：Celery meta 中的 status 字段通常用于存储描述文本
    # 注意：避免手动设置 state='FAILURE' 且 meta 为 dict，这会导致 Celery 序列化错误 (ValueError: Exception information must include the exception type)
    # 修复：始终使用 PROGRESS 状态更新 meta，避免手动设置 SUCCESS 导致 task.get() 提前返回 meta 数据而非函数返回值
    try:
        celery_state = 'PROGRESS'
        # if status == 'SUCCESS':
        #     celery_state = 'SUCCESS'
            
        update_result = task.update_state(
            state=celery_state,
            meta={
                'status': status,
                'message': text,
                'progress': progress,
                **kwargs,
            }
        )
        if hasattr(update_result, '__await__'):
            await update_result
    except Exception as e:
        logger.error(f"Failed to update celery state: {e}")
    
    # 2. 推送 WebSocket 消息 (供前端实时展示)
    await publish_task_progress(
        task_id=task.request.id,
        status=status,
        progress=progress,
        text=text,
        channel_prefix=channel_prefix,
        **kwargs
    )
