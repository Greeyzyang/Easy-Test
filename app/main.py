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
    variables_router
)
from app.utils.exceptions import http_exception_handler
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.routers.users import (
    cookie_auth_backend,
    bearer_auth_backend,
    fastapi_users,
    get_user_manager,
    current_active_user,
    UserManager
)
from app.database import User, create_db_and_tables, get_db
from contextlib import asynccontextmanager
from fastapi.security import OAuth2PasswordRequestForm
from app.utils.response import create_response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
import logging
from fastapi_users.jwt import generate_jwt
from app.config import SECRET
from fastapi_users.jwt import decode_jwt
import time
from fastapi_users.db import SQLAlchemyUserDatabase
from passlib.context import CryptContext
import uuid
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建一个 user_manager 实例
user_manager = None  # 移除直接实例化

# 创建 pwd_context 实例
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 确保在应用启动时创建数据库表
    logger.info("开始创建数据库表...")
    await create_db_and_tables()
    logger.info("数据库表创建成功!")
    
    # 检查是否存在管理员用户
    async for db in get_db():
        statement = select(User).where(User.email == "admin@qq.com")
        result = await db.execute(statement)
        admin_user = result.scalar_one_or_none()
        
        if admin_user is None:
            # 创建管理员用户
            try:
                admin_user = User(
                    id=str(uuid.uuid4()),
                    email="admin@qq.com",
                    username="admin",
                    hashed_password=pwd_context.hash("admin1234"),
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
            # 如果用户已存在，更新密码
            try:
                admin_user.hashed_password = pwd_context.hash("admin1234")
                await db.commit()
                logger.info("成功更新管理员用户密码")
            except Exception as e:
                logger.error(f"更新管理员用户密码失败: {str(e)}")
    
    yield
    logger.info("应用关闭...")

app = FastAPI(lifespan=lifespan)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 可以更精确地指定前端地址
    allow_credentials=True,        # 允许携带凭证
    allow_methods=["*"],           # 允许所有 HTTP 方法
    allow_headers=["*"],           # 允许所有 HTTP 头
    expose_headers=["*"],          # 暴露所有头部信息，包括授权相关的头
    max_age=3600,                  # 预检请求结果缓存时间
)

@app.post("/auth/jwt/login")
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    logger.info("接收到登录请求")
    logger.info("表单数据: username=%s, password长度=%d", form_data.username, len(form_data.password) if form_data.password else 0)
    
    statement = select(User).where(User.email == form_data.username)
    logger.info("执行SQL查询: %s", str(statement))
    
    result = await db.execute(statement)
    user = result.scalar_one_or_none()
    
    if user is None:
        logger.warning("未找到用户: %s", form_data.username)
        raise HTTPException(status_code=400, detail="Invalid credentials: User not found")
        
    logger.info("找到用户: email=%s, is_active=%s, is_verified=%s", 
                user.email, user.is_active, user.is_verified)
    
    # 使用 pwd_context 直接验证密码
    try:
        is_password_valid = pwd_context.verify(form_data.password, user.hashed_password)
        logger.info("密码验证结果: %s", is_password_valid)
    except Exception as e:
        logger.error("密码验证出错: %s", str(e))
        raise HTTPException(status_code=400, detail="Invalid credentials: Password validation error")
    
    if not is_password_valid:
        raise HTTPException(status_code=400, detail="Invalid credentials: Incorrect password")
    
    # 使用 fastapi-users 的方式创建访问令牌
    # 包含必要的声明字段
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "aud": "fastapi-users:auth",  # 这是 fastapi-users 期望的 audience
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_superuser": user.is_superuser,
        # 添加过期时间
        "exp": int(time.time()) + 60*60*12  # 12小时后过期
    }
    token = generate_jwt(token_data, SECRET)
    logger.info("生成的 JWT token: %s...(已截断)", token[:20] if token else "None")
    
    # 设置cookie和CORS安全头
    # 与 fastapi-users 的 cookie_auth_backend 使用相同的 cookie 名称和设置
    cookie_transport = cookie_auth_backend.transport
    cookie_name = cookie_transport.cookie_name  # 应该是 "X-Token"
    
    response.set_cookie(
        key=cookie_name, 
        value=token, 
        httponly=True, 
        max_age=3600, 
        samesite="lax",  # 对于跨域请求更安全
        secure=False     # 生产环境中应设为True
    )
    
    # 返回标准OAuth2格式的token，以便前端可以使用 Bearer 认证
    return await create_response(data={
        "X-Token": token,
        "token_type": "bearer",
        "expires_in": 3600
    })

@app.post("/auth/direct-register", response_model=UserRead)
async def direct_register(
    user_create: UserCreate,
    request: Request,
    user_manager: UserManager = Depends(get_user_manager)
):
    """直接注册用户的API，用于调试和测试"""
    try:
        logger.debug(f"收到直接注册请求: {user_create.dict()}")
        
        # 使用UserManager创建用户
        user = await user_manager.create(user_create, request=request)
        
        # 返回用户信息
        return user
    except Exception as e:
        logger.error(f"直接注册失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/me")
async def get_user_info(user: User = Depends(current_active_user)):
    return await create_response(
        data={
            "email": user.email,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "is_superuser": user.is_superuser
        }
    )

@app.get("/test")
async def some_function(request: Request, response: Response):
    logger.info("Received cookies: %s", request.cookies)
    logger.info("Received headers: %s", request.headers)
    token = request.cookies.get("X-Token")
    logger.info("Token: %s", token) 
    return {"msg": "Check console for cookies"}

@app.get("/debug-auth")
async def debug_auth(request: Request):
    """调试端点：显示所有认证相关信息"""
    auth_header = request.headers.get("Authorization", "None")
    cookies = request.cookies
    
    # 如果存在 Bearer token，解析并验证它
    token_info = "无效"
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        try:
            # 尝试解码 token
            decoded = decode_jwt(token, SECRET)
            token_info = {
                "valid": True,
                "sub": decoded.get("sub"),
                "email": decoded.get("email"),
                "exp": decoded.get("exp"),
                "aud": decoded.get("aud")
            }
        except Exception as e:
            token_info = {"valid": False, "error": str(e)}
    
    return {
        "auth_header": auth_header,
        "token_info": token_info,
        "cookies": cookies,
        "headers": dict(request.headers)
    }

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
app.include_router(fastapi_users.get_auth_router(cookie_auth_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_auth_router(bearer_auth_backend), prefix="/auth/jwt-bearer", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])
app.add_exception_handler(HTTPException, http_exception_handler)




