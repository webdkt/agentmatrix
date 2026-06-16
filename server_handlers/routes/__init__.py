"""
Route modules for the AgentMatrix server.
"""

from .system import router as system_router
from .websocket import router as websocket_router
from .config import router as config_router
from .sessions import router as sessions_router
from .agents import router as agents_router
from .agent_profiles import router as agent_profiles_router
from .skills import router as skills_router
from .llm_configs import router as llm_configs_router
from .email_proxy import router as email_proxy_router
from .proxy import router as proxy_router
from .automation import router as automation_router
from .knowledge import router as knowledge_router
from .services import router as services_router


def register_all_routes(app):
    """Register all route modules with the FastAPI app."""
    app.include_router(system_router)
    app.include_router(websocket_router)
    app.include_router(config_router)
    app.include_router(sessions_router)
    app.include_router(agents_router)
    app.include_router(agent_profiles_router)
    app.include_router(skills_router)
    app.include_router(llm_configs_router)
    app.include_router(email_proxy_router)
    app.include_router(proxy_router)
    app.include_router(automation_router)
    app.include_router(knowledge_router)
    app.include_router(services_router)
