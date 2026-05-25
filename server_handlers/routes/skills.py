"""
Skill management routes: list skills, refresh cache.
"""

from fastapi import APIRouter, HTTPException

from ..utils import get_skills_with_cache

router = APIRouter(prefix="/api/skills")


@router.get("/")
async def get_available_skills():
    """Get all available skills in the system (with 5min cache)"""
    try:
        skills = get_skills_with_cache()
        return {"skills": skills}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_skills_cache():
    """Force refresh skills cache"""
    try:
        skills = get_skills_with_cache(force_refresh=True)
        return {"skills": skills, "refreshed": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
