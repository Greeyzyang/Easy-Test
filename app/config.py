import secrets
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 自动选择数据库：DATABASE_URL_PROD 优先（Docker环境），否则用 DATABASE_URL_DEV（本地）
_DATABASE_URL_PROD = os.getenv("DATABASE_URL_PROD", "")
DATABASE_URL = _DATABASE_URL_PROD if _DATABASE_URL_PROD else os.getenv("DATABASE_URL_DEV", "mysql+aiomysql://root:root@localhost/test_platform")
SECRET = os.getenv("SECRET", secrets.token_hex(32))
# 自动选择 Redis：DATABASE_URL_PROD 存在时使用 redis:6379
_REDIS_URL_PROD = os.getenv("REDIS_URL_PROD", "")
REDIS_URL = _REDIS_URL_PROD if _REDIS_URL_PROD else os.getenv("REDIS_URL_DEV", "redis://localhost:6379/0")

# 服务器统一基础地址（前后端共用），用于推导 BACKEND_URL / VERIFY_BASE_URL / RESET_BASE_URL
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost")
_BACKEND_PORT = "8000"
_FRONTEND_PORT = "9528"

def _get_backend_url() -> str:
    """从 SERVER_BASE_URL 推导后端地址（替换端口）"""
    base = SERVER_BASE_URL.rstrip("/")
    if base.startswith("http://"):
        return f"http://{base[7:]}:{_BACKEND_PORT}"
    elif base.startswith("https://"):
        return f"https://{base[8:]}:{_BACKEND_PORT}"
    return f"http://{base}:{_BACKEND_PORT}"

def _get_frontend_url(path: str) -> str:
    """从 SERVER_BASE_URL 推导前端带 hash 的 URL"""
    base = SERVER_BASE_URL.rstrip("/")
    if base.startswith("http://"):
        return f"http://{base[7:]}:{_FRONTEND_PORT}/#/{path.lstrip('/')}"
    elif base.startswith("https://"):
        return f"https://{base[8:]}:{_FRONTEND_PORT}/#/{path.lstrip('/')}"
    return f"http://{base}:{_FRONTEND_PORT}/#/{path.lstrip('/')}"

BACKEND_URL = _get_backend_url()
VERIFY_BASE_URL = _get_frontend_url("verify-email")
RESET_BASE_URL = _get_frontend_url("reset-password")

# 固定 SMTP 配置（公司邮箱服务地址，部署时无需改动）
SMTP_SERVER = "smtp.qiye.aliyun.com"
SMTP_PORT = 465
SMTP_USE_TLS = False
SMTP_USE_SSL = True
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("SMTP_USERNAME", "")

from typing import Optional

class Settings:
    # Celery Configuration
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # JIRA Configuration（地址和连接参数已固定，运行时通过 DB 覆盖）
    JIRA_URL: str = "https://ginolt.atlassian.net/"
    JIRA_USER: str = os.getenv("JIRA_USER", "")
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "")
    JIRA_VALIDATE: bool = False
    JIRA_VERIFY: bool = True
    JIRA_TIMEOUT: int = 30

    # LLM Configuration（API Key 必填，其余参数已固定）
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_API_BASE: str = "https://open.bigmodel.cn/api/paas/v4"
    LLM_MODEL_NAME: str = "glm-5"
    LLM_TIMEOUT: int = 600
    LLM_MAX_TOKENS: int = 8000
    LLM_TEMPERATURE: float = 0.3

    # 内部行为参数
    MAX_RETRIES: int = 3
    ENABLE_IMAGE_PROCESSING: bool = False
    KB_PDF_PATH: Optional[str] = "app/Gino_product_specification.pdf"

    # Frontend Base URLs
    BACKEND_URL: str = BACKEND_URL
    VERIFY_BASE_URL: str = VERIFY_BASE_URL
    RESET_BASE_URL: str = RESET_BASE_URL

    # SMTP Email Configuration
    SMTP_SERVER: str = SMTP_SERVER
    SMTP_PORT: int = SMTP_PORT
    SMTP_USERNAME: str = SMTP_USERNAME
    SMTP_PASSWORD: str = SMTP_PASSWORD
    FROM_EMAIL: str = FROM_EMAIL
    SMTP_USE_TLS: bool = SMTP_USE_TLS
    SMTP_USE_SSL: bool = SMTP_USE_SSL

    class Config:
        env_file = ".env"
