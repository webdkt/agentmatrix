"""
Automation task routes: list, query, and filter automation tasks.
"""

from fastapi import APIRouter, HTTPException, Query
from ..state import server_state

router = APIRouter()


@router.get("/api/automation/tasks")
async def get_automation_tasks(
    agent_name: str = Query(None),
    system_name: str = Query(None),
    process_name: str = Query(None),
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get automation tasks with optional filters."""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    try:
        db = server_state.matrix_runtime.post_office.email_db
        tasks = await db.get_automation_tasks(
            agent_name=agent_name,
            system_name=system_name,
            process_name=process_name,
            status=status,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    return {"success": True, "tasks": tasks}


@router.get("/api/automation/tasks/latest")
async def get_latest_automation_task(
    agent_name: str = Query(...),
    system_name: str = Query(...),
    process_name: str = Query(...),
):
    """Get the most recent automation task for a specific agent/system/process."""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    try:
        db = server_state.matrix_runtime.post_office.email_db
        task = await db.get_latest_automation_task(
            agent_name=agent_name,
            system_name=system_name,
            process_name=process_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    return {"success": True, "task": task}
