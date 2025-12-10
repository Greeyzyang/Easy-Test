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
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USERNAME)
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

# 前端链接基址配置（避免硬编码 localhost）
VERIFY_BASE_URL = os.getenv("VERIFY_BASE_URL", "http://localhost:9528/#/verify-email")
RESET_BASE_URL = os.getenv("RESET_BASE_URL", "http://localhost:9528/#/reset-password")

class Settings:
    # Celery Configuration
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Jira Configuration
    JIRA_URL: str = "https://ginolt.atlassian.net/"
    JIRA_USER: str = "yangzhi@ginolegaltech.cn"
    JIRA_API_TOKEN: str = "ATATT3xFfGF0IQy00pDWY7N0mJUHVj3sQ1SMAuf_YwSsI3TI9JjVRV2B01aiWjr-Po7mZ4wlLMLJ5E6xpEor8aD101N-wodn7dxnUA6Hs6zSQINPs_UXMErTGX-LBo7pCJ-QOmXghRyq1IG9sEJx-mRNwd9ZyHxomA40a-k7Do1AaNx4Gbm5_jQ=449A3781"
    # 连接校验与证书配置（用于降低初始化时的报错与重试噪音）
    JIRA_VALIDATE: bool = False  # 初始化时不访问 serverInfo，避免不可达时持续重试报警
    JIRA_VERIFY: bool = True     # HTTPS 证书校验，若公司代理拦截可在 .env 中临时设为 False（不建议生产环境）

    # LLM Configuration (Optimized for Doubao Model)
    LLM_API_KEY: str = "d1a85980-dc2b-427d-be4c-bd75b615f768"
    LLM_API_BASE: str = "https://ark.cn-beijing.volces.com/api/v3"
    LLM_MODEL_NAME: str = "doubao-seed-1-6-250615"
    
    # Doubao Model Optimization Settings
    LLM_TIMEOUT: int = 600  # Increased timeout for Doubao model (10 minutes)
    JIRA_TIMEOUT: int = 30  # Keep Jira timeout at 30s
    MAX_RETRIES: int = 3    # Maximum retry attempts
    ENABLE_IMAGE_PROCESSING: bool = False  # Disable image processing
    
    # Doubao-specific LLM Settings
    LLM_MAX_TOKENS: int = 30000  # 适中的token限制，防止响应被截断
    LLM_TEMPERATURE: float = 0.3  # 提高创造性和多样性
    DOUBAO_SIMPLE_MODE: bool = True  # 启用简单模式，提高JSON格式稳定性

    JIRA_COMPONENTS_XLSX_PATH: str | None = "app/components.xlsx"

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
    KB_PDF_PATH: str | None = KB_PDF_PATH

    class Config:
        env_file = ".env"
