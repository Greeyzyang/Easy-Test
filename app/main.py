from fastapi import FastAPI, HTTPException, Depends, Request, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    projects_router,
    modules_router,
    interfaces_router,
    testcases_router,
    testsuites_router,
    testreports_router,
    teststeps_router,
    functions_router,
    variables_router,
    assistant_router,
    metrics_router,
    ai_models_router,
    mcp_servers_router,
    performance_tests_router
)
from app.utils.exceptions import http_exception_handler
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.routers.users import (
    bearer_auth_backend,
    fastapi_users,
    get_user_manager,
    current_active_user,
    UserManager
)
from app.database import User, create_db_and_tables, get_db
from contextlib import asynccontextmanager
from sqlalchemy import select
from fastapi.responses import JSONResponse
from app.utils.logger import setup_logging, get_logger
import os
import logging
from app.config import SECRET
from fastapi_users.jwt import decode_jwt
import time
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from passlib.context import CryptContext
import uuid
from datetime import datetime
from app.database import engine, Base
from app.celery_app import celery_app
from app.tasks import testsuite_tasks, ai_tasks

# 初始化统一日志
# 默认开启DEBUG模式以便调试
setup_logging(level=logging.DEBUG)
logger = get_logger(__name__)

# 创建一个 user_manager 实例
user_manager = None  # 移除直接实例化

# 创建 pwd_context 实例
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 确保在应用启动时创建数据库表
    logger.info("开始创建数据库表...")
    await create_db_and_tables()
    logger.info("数据库表创建成功!")
    
    # 检查是否存在管理员用户
    async for db in get_db():
        default_email = os.getenv("ADMIN_DEFAULT_EMAIL", "admin@qq.com")
        default_password = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin1234")
        force_reset = os.getenv("FORCE_RESET_ADMIN_PASSWORD", "0") == "1"
        statement = select(User).where(User.email == default_email)
        result = await db.execute(statement)
        admin_user = result.scalar_one_or_none()
        
        if admin_user is None:
            # 创建管理员用户
            try:
                admin_user = User(
                    id=str(uuid.uuid4()),
                    email=default_email,
                    username="admin",
                    hashed_password=pwd_context.hash(default_password),
                    is_active=True,
                    is_superuser=True,
                    is_verified=True,
                    created_time=datetime.now(),
                    updated_time=datetime.now()
                )
                db.add(admin_user)
                await db.commit()
                logger.info("成功创建管理员用户")
            except Exception as e:
                logger.error(f"创建管理员用户失败: {str(e)}")
        else:
            # 已存在管理员用户：仅在显式要求时重置密码，或当提供的新默认密码与当前不一致时重置
            try:
                should_reset = False
                if force_reset:
                    should_reset = True
                else:
                    try:
                        if default_password:
                            is_same = pwd_context.verify(default_password, admin_user.hashed_password)
                            should_reset = not is_same
                    except Exception:
                        should_reset = False

                if should_reset:
                    admin_user.hashed_password = pwd_context.hash(default_password)
                    await db.commit()
                    logger.info("成功更新管理员用户密码")
                else:
                    logger.info("管理员用户已存在，跳过密码更新")
            except Exception as e:
                logger.error(f"更新管理员用户密码失败: {str(e)}")
    
    yield
    logger.info("应用关闭...")

app = FastAPI(lifespan=lifespan)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)



# 自定义处理注册用户的异常
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"全局异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": f"服务器内部错误: {str(exc)}"}
    )

# 注册路由
app.include_router(projects_router)
app.include_router(modules_router)
app.include_router(interfaces_router)
app.include_router(testcases_router)
app.include_router(testsuites_router)
app.include_router(testreports_router)
app.include_router(teststeps_router)
app.include_router(functions_router)
app.include_router(variables_router)
app.include_router(assistant_router)
app.include_router(metrics_router)
app.include_router(ai_models_router)
app.include_router(mcp_servers_router)
app.include_router(performance_tests_router)
# 将 Bearer 认证挂载到标准 /auth/jwt 路径，统一登录接口
# 之前的 cookie_auth_backend 已被移除，因为前端统一使用 Bearer Token
app.include_router(fastapi_users.get_auth_router(bearer_auth_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])
app.add_exception_handler(HTTPException, http_exception_handler)
