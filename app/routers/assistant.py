from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.tasks.ai_tasks import generate_kb_answer_task
from app.services.agent_service import AgentService
from app.utils.response import create_response
from app.routers.users import current_active_user
from app.database import User
from app.models.ai_model import AIModel
from app.schemas.ai import AgentChatRequest
from app.schemas.base_schemas import KBQueryRequest
from app.utils.logger import get_logger
from sqlalchemy import select

logger = get_logger(__name__)

router = APIRouter(
    prefix="/rest/v1/ai",
    tags=["assistant"]
)

@router.post("/chat/")
async def chat_with_agent(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user)
):
    """
    Chat with the AI Agent (LangGraph ReAct with Memory).
    Supports both streaming and non-streaming responses.
    """
    logger.info(f"AI Agent 对话: user={user.username if user else 'anonymous'}, message={request.message}")
    
    # 获取当前激活的模型配置
    result = await db.execute(select(AIModel).where(AIModel.is_active == True))
    active_model = result.scalars().first()
    
    service = AgentService(db, model_config=active_model)
    thread_id = str(user.id) if user else "default_user"
    
    if request.stream:
        async def event_generator():
            try:
                # 统一使用 chat 接口，默认就是流式
                gen = await service.chat(request.message, request.history, thread_id=thread_id, stream=True)
                async for chunk in gen:
                    yield chunk
            except Exception as e:
                logger.error(f"AI Agent 对话流式响应出错: {str(e)}")
                yield f"\n[Error]: {str(e)}"
        
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        # 非流式模式
        try:
            response = await service.chat(request.message, request.history, thread_id=thread_id, stream=False)
            return await create_response({"response": response})
        except Exception as e:
            logger.error(f"AI Agent 对话响应出错: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/kb/query/", status_code=202)
async def kb_query(request: KBQueryRequest, db: AsyncSession = Depends(get_db)):
    """
    知识库问答接口
    """
    logger.info(f"知识库问答查询: {request.question}")
    try:
        task = generate_kb_answer_task.delay(request.question, request.top_k)
        logger.info(f"知识库查询任务已启动: task_id={task.id}")
        return await create_response({
            "task_id": task.id,
            "message": "知识库查询任务已启动，正在处理中..."
        })
    except Exception as e:
        logger.error(f"启动知识库查询任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")
