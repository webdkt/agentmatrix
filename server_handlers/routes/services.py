"""
Service routes: list, detail, actions, worker events.
"""

from fastapi import APIRouter, HTTPException

from ..state import server_state

router = APIRouter(prefix="/api/services")


def _get_runtime():
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")
    return server_state.matrix_runtime


@router.get("/")
async def list_services():
    """列出所有已注册的 service 及其状态摘要。"""
    runtime = _get_runtime()
    services = runtime.get_services()
    result = []
    for name, svc in services.items():
        status = svc.get_status()
        workers = svc.get_workers()
        status["worker_count"] = len(workers)
        status["working_count"] = sum(1 for w in workers if w.get("status") == "working")
        status["workers"] = workers
        result.append(status)
    return {"services": result}


@router.get("/{name}")
async def get_service_detail(name: str):
    """获取 service 详情：status + workers + actions。"""
    runtime = _get_runtime()
    services = runtime.get_services()
    if name not in services:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
    svc = services[name]
    return {
        "status": svc.get_status(),
        "workers": svc.get_workers(),
        "actions": svc.get_actions(),
    }


@router.post("/{name}/actions/{action_id}")
async def execute_action(name: str, action_id: str, payload: dict = None):
    """手动触发 service action。"""
    runtime = _get_runtime()
    services = runtime.get_services()
    if name not in services:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
    try:
        result = await services[name].execute_action(action_id, payload)
        return {"success": True, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}/workers/{worker_id}/events")
async def get_worker_events(name: str, worker_id: str, limit: int = 200):
    """获取 worker 的 session events。"""
    runtime = _get_runtime()
    services = runtime.get_services()
    if name not in services:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")

    try:
        db = runtime.post_office.email_db
        events = await db.get_latest_session_events(
            owner=name,
            session_id=worker_id,
            limit=limit,
        )
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}/events")
async def get_service_events(name: str, limit: int = 200):
    """获取 service 级事件（activity feed）。"""
    runtime = _get_runtime()
    services = runtime.get_services()
    if name not in services:
        raise HTTPException(status_code=404, detail=f"Service '{name}' not found")

    try:
        db = runtime.post_office.email_db
        events = await db.get_latest_session_events(
            owner=name,
            session_id="__service__",
            limit=limit,
        )
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
