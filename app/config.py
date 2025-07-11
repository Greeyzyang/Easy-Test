import secrets
DATABASE_URL = "mysql+aiomysql://root:root@localhost/test_platform"
SECRET = secrets.token_hex(32)
REDIS_URL = "redis://localhost:6379/0" # Celery 消息代理和结果后端
