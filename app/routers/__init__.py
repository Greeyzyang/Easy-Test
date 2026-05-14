from .projects import router as projects_router
from .modules import router as modules_router
from .interfaces import router as interfaces_router
from .testcases import router as testcases_router
from .testsuites import router as testsuites_router
from .testreports import router as testreports_router
from .teststeps import router as teststeps_router
from .functions import router as functions_router
from .variables import router as variables_router
from .assistant import router as assistant_router
from .metrics import router as metrics_router
from .ai_models import router as ai_models_router
from .mcp_servers import router as mcp_servers_router
from .performance_tests import router as performance_tests_router
from .tencent_docs import router as tencent_docs_router

__all__ = [
    "projects_router",
    "modules_router",
    "interfaces_router",
    "testcases_router",
    "testsuites_router",
    "testreports_router",
    "teststeps_router",
    "functions_router",
    "variables_router",
    "assistant_router",
    "metrics_router",
    "ai_models_router",
    "mcp_servers_router",
    "performance_tests_router",
    "tencent_docs_router",
]
