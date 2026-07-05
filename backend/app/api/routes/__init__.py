from .analysis import router as analysis_router
from .auth import router as auth_router
from .cases import router as cases_router
from .crawler import router as crawler_router
from .dashboard import router as dashboard_router
from .datasets import router as datasets_router
from .entities import router as entities_router
from .evidence import router as evidence_router
from .logs import router as logs_router
from .notifications import router as notifications_router
from .platforms import router as platforms_router
from .reports import router as reports_router
from .signals import router as signals_router
from .tasks import router as tasks_router

__all__ = [
    "analysis_router",
    "auth_router",
    "cases_router",
    "crawler_router",
    "dashboard_router",
    "datasets_router",
    "entities_router",
    "evidence_router",
    "logs_router",
    "notifications_router",
    "platforms_router",
    "reports_router",
    "signals_router",
    "tasks_router",
]
