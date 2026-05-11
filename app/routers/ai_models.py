from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import List
from openai import AsyncOpenAI

from app.database import get_db
from app.models.ai_model import AIModel
from app.schemas.ai_model import AIModelCreate, AIModelRead, AIModelUpdate, AIModelTestConnection
from app.utils.logger import get_logger
from app.utils.response import create_response, ResponseModel

router = APIRouter(prefix="/rest/v1/ai-models", tags=["ai-models"])
logger = get_logger(__name__)

@router.post("/test-connection", response_model=ResponseModel)
async def test_connection(model_in: AIModelTestConnection):
    try:
        client = AsyncOpenAI(
            api_key=model_in.api_key,
            base_url=model_in.base_url,
            timeout=10.0,
            max_retries=0
        )
        
        # 尝试进行一次简单的对话
        response = await client.chat.completions.create(
            model=model_in.model_name,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=16
        )
        
        return await create_response(data={"success": True, "msg": "连接成功！"})
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        # Return success=True but with error info in data so frontend can handle it gracefully
        # Or just return data with success=False
        return await create_response(data={"success": False, "error": str(e)})

@router.get("/", response_model=ResponseModel)
async def list_ai_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AIModel).order_by(AIModel.created_time.desc()))
    models = result.scalars().all()
    data = [AIModelRead.model_validate(m) for m in models]
    return await create_response(data=data)

@router.post("/", response_model=ResponseModel, status_code=201)
async def create_ai_model(model_in: AIModelCreate, db: AsyncSession = Depends(get_db)):
    # 如果设置为激活，先取消其他模型的激活状态
    # 但Create schema里没有 is_active 字段，默认是 False
    # 如果需要可以在 Create schema 中加入 is_active，这里暂不处理
    
    new_model = AIModel(**model_in.model_dump())
    db.add(new_model)
    await db.commit()
    await db.refresh(new_model)
    return await create_response(data=AIModelRead.model_validate(new_model))

@router.put("/{model_id}/activate", response_model=ResponseModel)
async def activate_ai_model(model_id: str, db: AsyncSession = Depends(get_db)):
    # 1. 检查模型是否存在
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="AI Model not found")
    
    # 2. 将所有其他模型设为非激活
    await db.execute(update(AIModel).where(AIModel.id != model_id).values(is_active=False))
    
    # 3. 将当前模型设为激活
    # 使用 update 语句直接更新数据库，确保状态一致性
    await db.execute(update(AIModel).where(AIModel.id == model_id).values(is_active=True))
    
    await db.commit()
    
    # 4. 刷新模型对象状态
    await db.refresh(model)
    return await create_response(data=AIModelRead.model_validate(model))

@router.put("/{model_id}/deactivate", response_model=ResponseModel)
async def deactivate_ai_model(model_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="AI Model not found")
    
    await db.execute(update(AIModel).where(AIModel.id == model_id).values(is_active=False))
    await db.commit()
    await db.refresh(model)
    return await create_response(data=AIModelRead.model_validate(model))

@router.put("/{model_id}", response_model=ResponseModel)
async def update_ai_model(model_id: str, model_in: AIModelUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="AI Model not found")
    
    update_data = model_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(model, field, value)
    
    await db.commit()
    await db.refresh(model)
    return await create_response(data=AIModelRead.model_validate(model))

@router.delete("/{model_id}", response_model=ResponseModel)
async def delete_ai_model(model_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="AI Model not found")
    
    await db.delete(model)
    await db.commit()
    return await create_response(data=None, msg="Deleted successfully")
