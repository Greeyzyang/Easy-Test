import uuid
from typing import Optional
from fastapi import Depends, Request, HTTPException, APIRouter
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
    BearerTransport,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from app.config import SECRET
from app.database import User, get_user_db, CustomSQLAlchemyUserDatabase, get_db
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.email_service import EmailService
from passlib.context import CryptContext
import logging
from sqlalchemy.ext.asyncio import AsyncSession

# 设置日志
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

def get_jwt_strategy():
    return JWTStrategy(secret=SECRET, lifetime_seconds=60*60*12)

# Cookie 认证
cookie_transport = CookieTransport(
    cookie_name="X-Token",
    cookie_secure=False,
    cookie_samesite="lax",
    cookie_path="/",
)
cookie_auth_backend = AuthenticationBackend(
    name="jwt-cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

# Bearer Token 认证
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
bearer_auth_backend = AuthenticationBackend(
    name="jwt-bearer",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

class UserManager(BaseUserManager[User, str]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET
    password_helper = pwd_context

    def parse_id(self, value: any) -> str:
        return str(value)

    async def validate_password(self, password: str, hashed_password: Optional[str] = None) -> bool:
        if hashed_password:
            return self.password_helper.verify_and_update(password, hashed_password)[0]
        return True

    async def create(
        self,
        user_create: UserCreate,
        safe: bool = False,
        request: Optional[Request] = None,
    ) -> User:
        """创建用户"""
        try:
            # 记录传入的用户创建对象
            logger.debug(f"User create object type: {type(user_create)}")
            
            # 获取密码
            password = getattr(user_create, "password", None)
            if not password:
                logger.error("无法获取密码")
                raise HTTPException(status_code=400, detail="密码不能为空")
                
            logger.debug(f"获取到的密码长度: {len(password)}")
            
            # 验证密码
            await self.validate_password(password)
            
            # 创建用户字典
            user_dict = {}
            
            # 尝试不同方法转换对象到字典
            if hasattr(user_create, "dict") and callable(user_create.dict):
                try:
                    user_dict = user_create.dict()
                    logger.debug("使用 .dict() 方法转换成功")
                except Exception as e:
                    logger.warning(f"使用 .dict() 方法转换失败: {e}")
            
            # 如果转换失败，使用 __dict__
            if not user_dict:
                try:
                    # 使用 __dict__ 并过滤私有属性
                    for key, value in user_create.__dict__.items():
                        if not key.startswith('_'):
                            user_dict[key] = value
                    logger.debug("使用 .__dict__ 属性转换成功")
                except Exception as e:
                    logger.warning(f"使用 .__dict__ 转换失败: {e}")
            
            # 如果仍然失败，尝试直接转换
            if not user_dict:
                try:
                    user_dict = dict(user_create)
                    logger.debug("使用 dict() 函数转换成功")
                except Exception as e:
                    logger.warning(f"使用 dict() 函数转换失败: {e}")
            
            # 记录最终的字典
            logger.debug(f"用户字典键值: {list(user_dict.keys())}")
            
            # 移除密码字段，添加哈希密码
            user_dict.pop("password", None)  # 移除原始密码
            hashed_password = self.password_helper.hash(password)
            if not hashed_password:
                raise HTTPException(status_code=500, detail="密码哈希失败")
                
            user_dict["hashed_password"] = hashed_password

            # 若未提供用户名，则使用邮箱或其本地部分作为默认用户名
            username = user_dict.get("username")
            email = user_dict.get("email")
            if not username:
                if email:
                    try:
                        local_part = email.split("@")[0]
                        user_dict["username"] = local_part or email
                    except Exception:
                        user_dict["username"] = email
                else:
                    # 如果没有邮箱（不太可能），生成一个随机用户名
                    user_dict["username"] = f"user_{uuid.uuid4().hex[:8]}"
            
            # 添加额外字段（如果需要）
            if "is_active" not in user_dict:
                user_dict["is_active"] = True
            if "is_verified" not in user_dict:
                user_dict["is_verified"] = True
                
            # 记录最终要发送的字典
            logger.debug(f"最终用户字典: {user_dict}")
            
            # 创建用户
            try:
                created_user = await self.user_db.create(user_dict)
                logger.info(f"用户创建成功! ID: {created_user.id if created_user else 'Unknown'}")
                await self.on_after_register(created_user, request)
                return created_user
            except Exception as e:
                logger.exception(f"调用数据库创建用户时出错: {str(e)}")
                raise HTTPException(status_code=500, detail=f"创建用户失败: {str(e)}")
        except Exception as e:
            logger.exception(f"创建用户过程中出错: {str(e)}")
            if isinstance(e, HTTPException):
                raise
            elif isinstance(e, ValueError):
                raise HTTPException(status_code=400, detail=str(e))
            else:
                raise HTTPException(status_code=500, detail=f"创建用户失败: {str(e)}")

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info(f"用户 {user.id} ({user.email}) 已注册成功.")
        try:
            email_service = EmailService()
            ok = await email_service.send_welcome_email(to_email=user.email, username=user.email)
            if ok:
                logger.info(f"欢迎邮件发送成功 -> {user.email}")
            else:
                logger.warning(f"欢迎邮件发送返回 False（可能未投递） -> {user.email}")
        except Exception as e:
            logger.error(f"发送欢迎邮件失败: {e}")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info(f"用户 {user.id} 忘记了密码. 重置令牌: {token}")
        try:
            email_service = EmailService()
            ok = await email_service.send_password_reset_email(
                to_email=user.email, username=user.email, token=token
            )
            if ok:
                logger.info(f"密码重置邮件发送成功 -> {user.email}")
            else:
                logger.warning(f"密码重置邮件发送返回 False（可能未投递） -> {user.email}")
        except Exception as e:
            logger.error(f"发送密码重置邮件失败: {e}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info(f"为用户 {user.id} 请求验证. 验证令牌: {token}")
        try:
            email_service = EmailService()
            ok = await email_service.send_verification_email(
                to_email=user.email, username=user.email, token=token
            )
            if ok:
                logger.info(f"邮箱验证邮件发送成功 -> {user.email}")
            else:
                logger.warning(f"邮箱验证邮件发送返回 False（可能未投递） -> {user.email}")
        except Exception as e:
            logger.error(f"发送邮箱验证邮件失败: {e}")


async def get_user_db(session: AsyncSession = Depends(get_db)):
    db = CustomSQLAlchemyUserDatabase(session, User)
    yield db

async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)

# FastAPI Users 实例
fastapi_users = FastAPIUsers[User, str](
    get_user_manager,
    [cookie_auth_backend, bearer_auth_backend],
)

# Current user dependencies
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)

# Router
router = APIRouter(prefix="/users", tags=["users"])

# 导出 UserManager 类
__all__ = [
    "UserManager",
    "cookie_auth_backend",
    "bearer_auth_backend",
    "fastapi_users",
    "get_user_manager",
    "current_active_user",
    "current_superuser",
    "router"
]
