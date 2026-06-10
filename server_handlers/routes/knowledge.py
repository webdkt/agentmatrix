"""
Knowledge Base API routes.
"""

import os
import re
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from ..state import server_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge")


# --- Request models ---

class CreateKBRequest(BaseModel):
    name: str
    description: str
    schema: str


class UpdateSchemaRequest(BaseModel):
    content: str


class CreateSourceRequest(BaseModel):
    path: str
    description: str = ""


# --- Helpers ---

def _get_wiki_dir():
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")
    return server_state.matrix_runtime.paths.wiki_dir


def _get_brain():
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")
    for agent in server_state.matrix_runtime.agents.values():
        if agent.__class__.__name__ == "KnowledgeBaseAgent":
            return agent.brain
    raise HTTPException(status_code=503, detail="KnowledgeBaseAgent not found")


def _validate_kb_name(name: str):
    if not name or len(name) < 2 or name.startswith('.') or name.startswith('_') or '..' in name:
        raise HTTPException(status_code=400, detail=f"Invalid knowledge base name: '{name}'")
    if not re.match(r'^[a-zA-Z0-9_\-]+$', name):
        raise HTTPException(status_code=400, detail=f"Invalid knowledge base name: '{name}'")


_BLOCKED_PATHS = {"/", "/etc", "/root", "/sys", "/proc", "/dev", "/boot",
                  "/private/etc", "/private/var", "/private/tmp"}
_BLOCKED_PREFIXES = ("/etc/", "/sys/", "/proc/", "/dev/", "/boot/", "/root/",
                     "/private/etc/", "/private/var/", "/private/tmp/")


def _is_blocked_path(abs_path: str) -> bool:
    resolved = str(Path(abs_path).resolve())
    if resolved in _BLOCKED_PATHS:
        return True
    return any(resolved.startswith(p) for p in _BLOCKED_PREFIXES)


# --- Endpoints ---

@router.get("/kbs")
async def list_kbs():
    from agentmatrix.desktop.skills.knowledge_base._shared import KBRegistry
    wiki_dir = _get_wiki_dir()
    names = KBRegistry.list_all(wiki_dir)

    result = []
    for name in names:
        try:
            ns = await KBRegistry.get_or_create(name, wiki_dir)
            has_schema = ns.wiki_manager.has_schema()
            stats = await ns.db.get_stats()
            page_count = stats.get("total", 0)
        except Exception:
            has_schema = False
            page_count = 0
        result.append({
            "name": name,
            "has_schema": has_schema,
            "page_count": page_count,
        })

    return {"kbs": result}


@router.post("/kbs")
async def create_kb(req: CreateKBRequest):
    from agentmatrix.desktop.skills.knowledge_base._shared import KBRegistry

    _validate_kb_name(req.name)
    wiki_dir = _get_wiki_dir()

    try:
        ns = await KBRegistry.get_or_create(req.name, wiki_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create knowledge base: {e}")

    if req.schema:
        ns.wiki_manager.init_with_schema(req.schema)

    return {"name": req.name, "has_schema": bool(req.schema)}


@router.get("/kbs/{name}")
async def get_kb(name: str):
    from agentmatrix.desktop.skills.knowledge_base._shared import KBRegistry

    _validate_kb_name(name)
    wiki_dir = _get_wiki_dir()
    ns = KBRegistry.get(name)
    if ns is None:
        try:
            ns = await KBRegistry.get_or_create(name, wiki_dir)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    has_schema = ns.wiki_manager.has_schema()
    schema = ns.wiki_manager.read_schema()

    try:
        stats = await ns.db.get_stats()
        page_count = stats.get("total", 0)
    except Exception:
        page_count = 0

    return {
        "name": name,
        "has_schema": has_schema,
        "schema": schema,
        "page_count": page_count,
    }


@router.put("/kbs/{name}/schema")
async def update_schema(name: str, req: UpdateSchemaRequest):
    from agentmatrix.desktop.skills.knowledge_base._shared import KBRegistry

    _validate_kb_name(name)
    wiki_dir = _get_wiki_dir()
    ns = await KBRegistry.get_or_create(name, wiki_dir)

    ns.wiki_manager.init_with_schema(req.content)
    return {"name": name, "has_schema": True}


@router.get("/kbs/{name}/pages")
async def list_pages(name: str):
    from agentmatrix.desktop.skills.knowledge_base._shared import KBRegistry

    _validate_kb_name(name)
    wiki_dir = _get_wiki_dir()
    ns = await KBRegistry.get_or_create(name, wiki_dir)

    file_pages = ns.wiki_manager.list_page_files()

    try:
        db_pages = await ns.db.get_all_pages()
    except Exception:
        db_pages = []

    db_map = {p["rel_path"]: p for p in db_pages}

    result = []
    for rel_path in file_pages:
        db_info = db_map.get(rel_path, {})
        result.append({
            "path": rel_path,
            "title": db_info.get("title", ""),
            "summary": db_info.get("summary", ""),
            "category": db_info.get("category", ""),
        })

    return {"pages": result}


@router.get("/kbs/{name}/pages/{path:path}")
async def get_page(name: str, path: str):
    from agentmatrix.desktop.skills.knowledge_base._shared import KBRegistry

    _validate_kb_name(name)
    wiki_dir = _get_wiki_dir()
    ns = await KBRegistry.get_or_create(name, wiki_dir)

    content = ns.wiki_manager.read_page(path)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Page '{path}' not found")

    return {"path": path, "content": content}


@router.get("/kbs/{name}/sources")
async def list_sources(name: str):
    from agentmatrix.desktop.skills.knowledge_base._shared import KBRegistry

    _validate_kb_name(name)
    wiki_dir = _get_wiki_dir()
    ns = await KBRegistry.get_or_create(name, wiki_dir)

    sources = await ns.db.get_all_sources()
    return {"sources": sources}


@router.post("/kbs/{name}/sources")
async def create_source(name: str, req: CreateSourceRequest):
    from agentmatrix.desktop.skills.knowledge_base._shared import KBRegistry, resolve_user_path

    _validate_kb_name(name)
    wiki_dir = _get_wiki_dir()
    ns = await KBRegistry.get_or_create(name, wiki_dir)

    abs_path = str(resolve_user_path(req.path))
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {abs_path}")

    if _is_blocked_path(abs_path):
        raise HTTPException(status_code=403, detail=f"Blocked path: {abs_path}")

    source_type = "directory" if os.path.isdir(abs_path) else "file"
    source_id = await ns.db.register_source(abs_path, req.description, source_type)

    if source_type == "directory":
        changed = await ns.db.scan_source_directory(source_id, abs_path)
        await ns.db.update_source_timestamps(source_id, scanned=True)
        file_count = len(await ns.db.get_source_files(source_id))
    else:
        changed = []
        file_count = 0

    return {
        "source_id": source_id,
        "path": abs_path,
        "type": source_type,
        "file_count": file_count,
        "new_files": len(changed),
    }


@router.delete("/kbs/{name}/sources/{source_id}")
async def delete_source(name: str, source_id: int):
    from agentmatrix.desktop.skills.knowledge_base._shared import KBRegistry

    _validate_kb_name(name)
    wiki_dir = _get_wiki_dir()
    ns = await KBRegistry.get_or_create(name, wiki_dir)

    await ns.db.delete_source(source_id)
    return {"deleted": True}


@router.get("/schema-draft/{task_id}")
async def get_schema_draft(task_id: str):
    """Read schema draft file from /tmp."""
    if not re.match(r'^[a-zA-Z0-9_\-]+$', task_id):
        raise HTTPException(status_code=400, detail=f"Invalid task_id: '{task_id}'")
    draft_path = Path("/tmp") / f"{task_id}-schema-draft.md"
    if draft_path.exists():
        try:
            content = draft_path.read_text(encoding="utf-8")
            return {"content": content, "exists": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read draft: {e}")
    return {"content": "", "exists": False}