from .projects import router as projects_router
from .modules import router as modules_router
from .interfaces import router as interfaces_router
from .testcases import router as testcases_router 
from .testsuites import router as testsuites_router
from .testreports import router as testreports_router
from .teststeps import router as teststeps_router
from .functions import router as functions_router
from .variables import router as variables_router

# 在 __all__ 列表中添加
__all__ = [
    "projects_router",
    "modules_router",
    "interfaces_router",
    "testcases_router",
    "testsuites_router",
    "testreports_router",
    "teststeps_router",
    "functions_router",
    "variables_router"
]
