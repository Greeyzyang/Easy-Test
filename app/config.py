import secrets
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+aiomysql://root:root@localhost/test_platform")
SECRET = os.getenv("SECRET", secrets.token_hex(32))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
KB_PDF_PATH = os.getenv("KB_PDF_PATH", "app/Gino_product_specification.pdf")

# SMTP邮件服务器配置
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qiye.aliyun.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USERNAME)
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

# 前端链接基址配置（避免硬编码 localhost）
VERIFY_BASE_URL = os.getenv("VERIFY_BASE_URL", "http://localhost:9528/#/verify-email")
RESET_BASE_URL = os.getenv("RESET_BASE_URL", "http://localhost:9528/#/reset-password")

from typing import Optional

class Settings:
    # Celery Configuration
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Jira Configuration
    JIRA_URL: str = os.getenv("JIRA_URL", "")
    JIRA_USER: str = os.getenv("JIRA_USER", "")
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "")
    # 连接校验与证书配置（用于降低初始化时的报错与重试噪音）
    JIRA_VALIDATE: bool = os.getenv("JIRA_VALIDATE", "false").lower() == "true"
    JIRA_VERIFY: bool = os.getenv("JIRA_VERIFY", "true").lower() == "true"

    # LLM Configuration (Optimized for Doubao Model)
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_API_BASE: str = os.getenv("LLM_API_BASE", "")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "")
    
    # Doubao Model Optimization Settings
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "600"))
    JIRA_TIMEOUT: int = int(os.getenv("JIRA_TIMEOUT", "30"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    # 多模态分析开关（默认关闭，避免 Token 爆炸）
    ENABLE_IMAGE_PROCESSING: bool = os.getenv("ENABLE_IMAGE_PROCESSING", "false").lower() == "true"
    # 最大附件处理大小（MB），默认 5MB
    MAX_ATTACHMENT_SIZE_MB: int = int(os.getenv("MAX_ATTACHMENT_SIZE_MB", "5"))
    
    # Doubao-specific LLM Settings
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "8000"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    DOUBAO_SIMPLE_MODE: bool = os.getenv("DOUBAO_SIMPLE_MODE", "true").lower() == "true"

    JIRA_COMPONENTS_XLSX_PATH: Optional[str] = os.getenv("JIRA_COMPONENTS_XLSX_PATH", "app/components.xlsx")

    # SMTP Email Configuration
    SMTP_SERVER: str = SMTP_SERVER
    SMTP_PORT: int = SMTP_PORT
    SMTP_USERNAME: str = SMTP_USERNAME
    SMTP_PASSWORD: str = SMTP_PASSWORD
    FROM_EMAIL: str = FROM_EMAIL
    SMTP_USE_TLS: bool = SMTP_USE_TLS
    SMTP_USE_SSL: bool = SMTP_USE_SSL

    # Frontend Base URLs
    VERIFY_BASE_URL: str = VERIFY_BASE_URL
    RESET_BASE_URL: str = RESET_BASE_URL

    # Knowledge Base PDF Path
    KB_PDF_PATH: Optional[str] = KB_PDF_PATH

    class Config:
        env_file = ".env"
