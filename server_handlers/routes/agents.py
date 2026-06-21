"""
Agent management routes: list, detail, status, control, workspace, terminal, UI actions.
Deduplicated: pause/resume each defined once (the second/correct version).
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request

from ..state import server_state
from ..models import InvokeUIActionRequest

router = APIRouter(prefix="/api/agents")


@router.get("/")
async def get_agents():
    """Get all agents with their details"""
    if not server_state.matrix_runtime:
        return {"agents": []}

    try:
        agents_list = []
        for name, agent in server_state.matrix_runtime.agents.items():
            if name == server_state.matrix_runtime.get_user_agent_name():
                continue

            agents_list.append(
                {
                    "name": name,
                    "description": getattr(agent, "description", "No description"),
                    "backend_model": getattr(agent, "backend_model", "default_llm"),
                    "skills": getattr(agent, "skills", []),
                }
            )

        return {"agents": agents_list}
    except Exception as e:
        print(f"Error getting agents: {e}")
        return {"agents": [], "error": str(e)}


@router.get("/{agent_name}")
async def get_agent(agent_name: str):
    """Get a specific agent's details"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent = server_state.matrix_runtime.agents[agent_name]

    return {
        "name": agent_name,
        "description": getattr(agent, "description", "No description"),
        "backend_model": getattr(agent, "backend_model", "default_llm"),
        "skills": getattr(agent, "skills", []),
    }


@router.get("/{agent_name}/status/history")
async def get_agent_status_history(agent_name: str):
    """Get agent status history (last 3)"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent = server_state.matrix_runtime.agents[agent_name]

    if hasattr(agent, "get_status_history"):
        return agent.get_status_history()
    else:
        return []


@router.get("/{agent_name}/profile")
async def get_agent_profile(agent_name: str):
    """Get agent configuration info"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent = server_state.matrix_runtime.agents[agent_name]

    profile = {
        "name": agent.name,
        "description": getattr(agent, "description", ""),
        "class_name": agent.__class__.__module__ + "." + agent.__class__.__name__,
        "backend_model": getattr(agent, "backend_model", "default_llm"),
        "skills": getattr(agent, "skills", []),
        "persona": getattr(agent, "persona", ""),
    }

    return profile


@router.get("/{agent_name}/log")
async def get_agent_log(agent_name: str, lines: int = 200):
    """Get agent log content"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    log_path = (
        server_state.matrix_runtime.paths.matrix_root / ".matrix" / "logs" / f"{agent_name}.log"
    )

    if not log_path.exists():
        return {"content": "", "path": str(log_path)}

    def read_log_file():
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            content = (
                "".join(all_lines[-lines:])
                if len(all_lines) > lines
                else "".join(all_lines)
            )
        return content

    try:
        content = await asyncio.to_thread(read_log_file)
        return {"content": content, "path": str(log_path)}
    except Exception as e:
        return {"content": "", "error": str(e)}


@router.get("/{agent_name}/sessions")
async def get_agent_sessions(agent_name: str):
    """Get agent session history"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    try:
        db = server_state.matrix_runtime.post_office.email_db
        sessions = await db.get_agent_sessions(agent_name)
        return {"sessions": sessions}
    except Exception as e:
        print(f"Error getting agent sessions: {e}")
        return {"sessions": [], "error": str(e)}


@router.get("/{agent_name}/sessions/{session_id}/events")
async def get_session_events(
    agent_name: str,
    session_id: str,
    limit: int = 200,
    direction: str = "latest",
    before: str = None,
):
    """Get agent session events with pagination"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    try:
        db = server_state.matrix_runtime.post_office.email_db
        if direction == "older" and before:
            events = await db.get_session_events_before(agent_name, session_id, before, limit)
        else:
            events = await db.get_latest_session_events(agent_name, session_id, limit)
        total = await db.get_session_event_count(agent_name, session_id)
        return {"events": events, "total": total}
    except Exception as e:
        print(f"Error getting session events: {e}")
        return {"events": [], "total": 0, "error": str(e)}


@router.post("/{agent_name}/stop")
async def stop_agent(agent_name: str):
    """Stop agent's current task"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent = server_state.matrix_runtime.agents[agent_name]

    try:
        agent.stop()
        return {"success": True, "message": f"Agent '{agent_name}' stopped"}
    except Exception as e:
        print(f"Error stopping agent '{agent_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_name}/pause")
async def pause_agent(agent_name: str):
    """Pause agent execution"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    try:
        agent = server_state.matrix_runtime.agents[agent_name]
        await agent.pause()

        return {
            "success": True,
            "message": f"Agent '{agent_name}' paused successfully",
            "agent_name": agent_name,
            "paused": True,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_name}/resume")
async def resume_agent(agent_name: str):
    """Resume agent execution"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    try:
        agent = server_state.matrix_runtime.agents[agent_name]
        await agent.resume()

        return {
            "success": True,
            "message": f"Agent '{agent_name}' resumed successfully",
            "agent_name": agent_name,
            "paused": False,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_name}/status")
async def get_agent_status(agent_name: str):
    """Get agent current execution status"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    try:
        agent = server_state.matrix_runtime.agents[agent_name]

        if hasattr(agent, "get_current_status"):
            result = {
                "success": True,
                "agent_name": agent_name,
                **agent.get_current_status(),
            }
        else:
            result = {
                "success": True,
                "agent_name": agent_name,
                "message": str(getattr(agent, "status", "unknown")),
                "timestamp": None,
            }
        # 暴露 agent 运行时附加信息（如 DesignCollabAgent 的 preview_port）
        preview_port = getattr(agent, "preview_port", None)
        if preview_port:
            result["preview_port"] = preview_port
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_name}/pending_user_input")
async def get_pending_user_input(agent_name: str):
    """Get agent's pending user input question"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    try:
        agent = server_state.matrix_runtime.agents[agent_name]

        if not agent._user_input_future or agent._user_input_future.done():
            return {"success": True, "agent_name": agent_name, "waiting": False}

        return {
            "success": True,
            "agent_name": agent_name,
            "waiting": True,
            "question": agent._pending_user_question,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_name}/collab")
async def toggle_collab_mode(agent_name: str, request: Request):
    """Toggle collaboration mode on/off"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent = server_state.matrix_runtime.agents[agent_name]

    try:
        body = await request.json()
        enabled = body.get("enabled", True)
        agent.collab_mode = enabled

        return {"status": "ok", "collab_mode": agent.collab_mode}
    except Exception as e:
        print(f"Error toggling collab mode for '{agent_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_name}/terminal/exec")
async def terminal_exec(agent_name: str, request: Request):
    """Execute shell command in agent's container session"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent = server_state.matrix_runtime.agents[agent_name]

    if not agent.container_session or not agent.container_session.is_active:
        try:
            await asyncio.to_thread(agent._init_container_session)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to reinitialize container session: {e}")

    try:
        body = await request.json()
        command = body.get("command", "").strip()
        if not command:
            raise HTTPException(status_code=400, detail="Empty command")

        exit_code, stdout, stderr = await asyncio.to_thread(
            agent.container_session.execute, command, 10.0
        )

        return {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "timeout": exit_code == -1,
        }
    except Exception as e:
        print(f"Error executing terminal command for '{agent_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_name}/workspace")
async def get_agent_workspace(agent_name: str):
    """Get agent workspace file tree"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    if agent_name not in server_state.matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent = server_state.matrix_runtime.agents[agent_name]

    try:
        workspace = agent.private_workspace
        if not workspace or not workspace.exists():
            return {"files": []}

        files = []
        for item in sorted(workspace.iterdir()):
            stat = item.stat()
            files.append({
                "name": item.name,
                "path": str(item),
                "is_dir": item.is_dir(),
                "size": stat.st_size if item.is_file() else None,
                "modified": stat.st_mtime,
            })

        return {"files": files, "workspace_path": str(workspace)}
    except Exception as e:
        print(f"Error getting workspace for '{agent_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_name}/ui_actions")
async def get_agent_ui_actions(agent_name: str):
    """Get agent's exposed UI action schema"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    agent = server_state.matrix_runtime.agents.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    return {"schema": agent.get_ui_schema()}


@router.post("/{agent_name}/ui_actions/{action_name}")
async def invoke_agent_ui_action(agent_name: str, action_name: str, request: InvokeUIActionRequest):
    """Invoke a specific UI action on an agent"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    agent = server_state.matrix_runtime.agents.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    try:
        result = await agent.execute_ui_action(action_name, request.payload or {})
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_name}/prompt")
async def get_agent_prompt(agent_name: str):
    """Get agent's full system prompt"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    agent = server_state.matrix_runtime.agents.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    system_prompt = agent.preview_system_prompt()

    return {"agent_name": agent_name, "system_prompt": system_prompt}
