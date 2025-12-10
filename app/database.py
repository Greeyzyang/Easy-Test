from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import DATABASE_URL
from typing import AsyncGenerator, Any, Dict, Optional
from fastapi import Depends, Request, HTTPException
from fastapi_users.db import SQLAlchemyUserDatabase
from app.models.user import User
from app.models.base_model import Base
import logging
import json
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# 设置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 创建密码哈希工具
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# 创建一个自定义的 SQLAlchemyUserDatabase 类，处理各种参数
class CustomSQLAlchemyUserDatabase(SQLAlchemyUserDatabase):
    async def create(self, create_dict: Any, safe: bool = False, request: Optional[Request] = None) -> User:
        """创建用户数据

        Args:
            create_dict: 用户数据（可能是字典或Pydantic模型）
            safe: 是否安全模式
            request: 请求对象

        Returns:
            User: 创建的用户对象
        """
        try:
            # 将 Pydantic 模型转换为字典
            if hasattr(create_dict, 'dict'):
                # 如果是 Pydantic 模型，转为字典
                logger.debug("转换 Pydantic 模型为字典")
                create_dict_real = create_dict.dict()
            elif hasattr(create_dict, '__dict__'):
                # 处理普通对象
                logger.debug("转换对象的 __dict__ 为字典")
                create_dict_real = {}
                for key, value in create_dict.__dict__.items():
                    if not key.startswith('_'):
                        create_dict_real[key] = value
            else:
                # 假设已经是字典
                logger.debug("使用原始字典")
                create_dict_real = create_dict

            # 记录创建字典
            logger.debug(f"数据库适配器收到的处理后创建字典: {create_dict_real}")
            
            # 如果存在密码字段但没有哈希密码字段，自动处理哈希
            if "password" in create_dict_real and "hashed_password" not in create_dict_real:
                password = create_dict_real.pop("password")
                if password:
                    logger.debug("检测到原始密码，自动创建哈希密码")
                    create_dict_real["hashed_password"] = pwd_context.hash(password)
                else:
                    logger.error("密码为空，无法创建哈希")
                    raise HTTPException(status_code=400, detail="密码不能为空")
            
            # 清理字典，移除 SQLAlchemy 不支持的字段
            create_dict_copy = create_dict_real.copy()
            for key in list(create_dict_copy.keys()):
                if key not in [c.name for c in self.user_table.__table__.columns]:
                    logger.debug(f"移除不支持的字段: {key}")
                    create_dict_copy.pop(key, None)
            
            # 统一使用 permissions 列，写入 JSON 字符串
            if "permissions" in create_dict_real:
                permissions = create_dict_real["permissions"]
                if isinstance(permissions, list):
                    create_dict_copy["permissions"] = json.dumps(permissions)
                elif isinstance(permissions, str):
                    try:
                        json.loads(permissions)  # 验证是 JSON
                        create_dict_copy["permissions"] = permissions
                    except Exception:
                        create_dict_copy["permissions"] = '[]'
                else:
                    create_dict_copy["permissions"] = '[]'
            elif "permissions" not in create_dict_copy:
                create_dict_copy["permissions"] = '[]'
            
            # 检查 hashed_password 是否存在
            if "hashed_password" not in create_dict_copy or not create_dict_copy["hashed_password"]:
                logger.error("创建用户时缺少哈希密码")
                raise HTTPException(status_code=400, detail="密码不能为空")
            
            # 记录最终的创建字典
            logger.debug(f"最终的用户创建数据: {create_dict_copy}")
            
            try:
                # 创建用户对象
                user = self.user_table(**create_dict_copy)
                self.session.add(user)
                
                # 提交到数据库
                await self.session.commit()
                await self.session.refresh(user)
                
                logger.info(f"成功创建用户: {user.email}, ID: {user.id}")
                return user
            except Exception as e:
                logger.exception(f"数据库操作出错: {str(e)}")
                await self.session.rollback()
                raise HTTPException(status_code=500, detail=f"数据库错误: {str(e)}")
        except Exception as e:
            logger.exception(f"创建用户时出错: {str(e)}")
            if not isinstance(e, HTTPException):
                raise HTTPException(status_code=500, detail=f"创建用户失败: {str(e)}")
            raise

    async def get(self, id: Any) -> Optional[User]:
        """重写get方法以处理permissions字段"""
        user = await super().get(id)
        return user

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,  # 连接池超时时间
    connect_args={
        "connect_timeout": 10  # 连接超时时间
    }
)

async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# 生成同步数据库URL，替换 aiomysql -> pymysql（用于 Celery/Beat 同步引擎）
SYNC_DATABASE_URL = DATABASE_URL.replace("+aiomysql", "+pymysql") if "+aiomysql" in DATABASE_URL else DATABASE_URL

# 为 sqlite 场景设置 connect_args，否则使用空字典，避免向非 sqlite 驱动传入 check_same_thread
_sync_connect_args = {"check_same_thread": False} if (SYNC_DATABASE_URL.startswith("sqlite") or "sqlite" in SYNC_DATABASE_URL) else {}

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=True,
    pool_size=5,
    max_overflow=10,
    connect_args=_sync_connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

def get_db_session_sync():
    """
    同步获取数据库会话，供 Celery 任务使用。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def create_db_and_tables():
    """创建数据库表"""
    try:
        logger.info("开始创建数据库表")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # 确保 users 表存在 permissions 列（方案B统一字段）
            def _ensure_permissions_column(sync_conn):
                from sqlalchemy import text
                try:
                    # 检查列是否存在（MySQL）
                    check_sql = text(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                          AND table_name = 'users'
                          AND column_name = 'permissions'
                        """
                    )
                    result = sync_conn.execute(check_sql).scalar()
                    if not result:
                        logger.info("users 表缺少 permissions 列，正在补充…")
                        sync_conn.execute(text("ALTER TABLE users ADD COLUMN permissions TEXT NULL"))
                        logger.info("已添加 users.permissions 列")
                except Exception as e:
                    logger.warning(f"检查/添加 permissions 列失败：{e}")

            await conn.run_sync(_ensure_permissions_column)
        logger.info("数据库表创建成功")
    except Exception as e:
        logger.error(f"创建数据库表时出错: {str(e)}")
        raise

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session = None
    try:
        session = async_session_maker()
        yield session
        # 如果没有异常，提交事务
        await session.commit()
    except Exception as e:
        logger.error(f"数据库会话错误: {str(e)}")
        if session:
            await session.rollback()
        raise
    finally:
        if session:
            await session.close()

async def get_user_db(session: AsyncSession = Depends(get_db)):
    try:
        db = CustomSQLAlchemyUserDatabase(session, User)
        yield db
        # 确保事务被提交
        await session.commit()
    except Exception as e:
        logger.error(f"用户数据库会话错误: {str(e)}")
        await session.rollback()
        raise
