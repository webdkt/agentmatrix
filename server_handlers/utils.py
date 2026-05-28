"""
Utility functions: skill scanning, agent profile helpers, LLM config helpers.
"""

import re
import json
import time
from pathlib import Path

from .state import server_state


# === LLM Config Helpers ===

REQUIRED_LLM_CONFIGS = ["default_llm", "default_slm", "browser-use-llm"]


def save_llm_configs_to_file(configs: dict):
    """Save LLM configurations dict to the global llm_config_path"""
    server_state.llm_config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(server_state.llm_config_path, "w", encoding="utf-8") as f:
        json.dump(configs, f, indent=4)


def load_llm_configs():
    """Load all LLM configurations from the config service"""
    from agentmatrix.desktop.services.config_service import ConfigService

    if server_state.matrix_runtime is None:
        return {}
    try:
        return ConfigService(server_state.matrix_runtime.paths).list_llm_models()
    except Exception as e:
        print(f"Error loading LLM configs: {e}")
        return {}


def get_llm_config_description(name: str) -> str:
    """Get description for a LLM config based on its name"""
    descriptions = {
        "default_llm": "Primary large language model for main agent reasoning",
        "default_slm": "Smaller/faster model for simple tasks and cerebellum",
        "browser-use-llm": "Model for browser automation tasks",
        "default_vision": "Vision model for image understanding tasks",
    }
    return descriptions.get(name, "Custom LLM configuration")


# === Skills Helpers ===

_skills_cache: list = None
_skills_cache_time: float = 0
_skills_cache_ttl: float = 300


def scan_available_skills() -> list:
    """Scan all available skills from the filesystem"""
    import importlib

    skills_info = []

    try:
        skills_module = importlib.import_module("agentmatrix.desktop.skills")
        skills_dir = Path(skills_module.__file__).parent

        for item in skills_dir.iterdir():
            if (
                item.is_dir()
                and not item.name.startswith("__")
                and not item.name.startswith(".")
            ):
                skill_file = item / "skill.py"
                if skill_file.exists():
                    skill_name = item.name
                    description = get_skill_description(skill_file, skill_name)
                    skills_info.append(
                        {
                            "name": skill_name,
                            "description": description,
                            "source": "built-in",
                        }
                    )
            elif (
                item.is_file()
                and item.name.endswith("_skill.py")
                and not item.name.startswith("__")
            ):
                skill_name = item.name[:-9]
                description = get_skill_description(item, skill_name)
                skills_info.append(
                    {
                        "name": skill_name,
                        "description": description,
                        "source": "built-in",
                    }
                )
    except Exception as e:
        print(f"Error scanning built-in skills: {e}")

    try:
        if server_state.matrix_world_dir:
            workspace_skills_dir = Path(server_state.matrix_world_dir) / "skills"
            if workspace_skills_dir.exists():
                for item in workspace_skills_dir.iterdir():
                    if item.is_dir() and not item.name.startswith("."):
                        skill_file = item / "skill.py"
                        if skill_file.exists():
                            skill_name = item.name
                            description = get_skill_description(skill_file, skill_name)
                            skills_info.append(
                                {
                                    "name": skill_name,
                                    "description": description,
                                    "source": "workspace",
                                }
                            )
    except Exception as e:
        print(f"Error scanning workspace skills: {e}")

    seen = set()
    unique_skills = []
    for skill in skills_info:
        if skill["name"] not in seen:
            seen.add(skill["name"])
            unique_skills.append(skill)

    unique_skills.sort(key=lambda x: x["name"])
    return unique_skills


def get_skill_description(skill_file: Path, skill_name: str) -> str:
    """Extract description from skill file docstring"""
    try:
        content = skill_file.read_text(encoding="utf-8")
        if '"""' in content:
            start = content.find('"""') + 3
            end = content.find('"""', start)
            if end > start:
                docstring = content[start:end].strip()
                for line in docstring.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("=="):
                        return line[:100]
    except Exception:
        pass
    return f"{skill_name} skill"


def get_skills_with_cache(force_refresh: bool = False) -> list:
    """Get skills with caching"""
    global _skills_cache, _skills_cache_time

    now = time.time()
    if (
        not force_refresh
        and _skills_cache is not None
        and (now - _skills_cache_time) < _skills_cache_ttl
    ):
        return _skills_cache

    _skills_cache = scan_available_skills()
    _skills_cache_time = now
    return _skills_cache


# === Agent Profile Helpers ===


def get_agent_yml_path(agent_name: str) -> Path:
    """Get the YAML file path for an agent"""
    return server_state.agents_dir / f"{agent_name}.yml"


def load_agent_profile(agent_name: str) -> dict:
    """Load agent profile from YAML file"""
    import yaml
    from fastapi import HTTPException

    yml_path = get_agent_yml_path(agent_name)
    if not yml_path.exists():
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    with open(yml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_agent_profile(agent_name: str, profile: dict):
    """Save agent profile to YAML file"""
    import yaml

    yml_path = get_agent_yml_path(agent_name)
    with open(yml_path, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, default_flow_style=False, allow_unicode=True)


def agent_profile_to_response(profile: dict) -> dict:
    """Convert agent profile to API response format"""
    skills = profile.get("skills", [])
    if not skills and "mixins" in profile:
        mixins = profile["mixins"]
        if isinstance(mixins, list):
            skills = [
                m.split(".")[-1].replace("SkillMixin", "").lower()
                for m in mixins
                if isinstance(m, str)
            ]

    response = {
        "name": profile.get("name", ""),
        "description": profile.get("description", ""),
        "module": profile.get("module", ""),
        "class_name": profile.get("class_name", ""),
        "backend_model": profile.get("backend_model", "default_llm"),
        "skills": skills,
        "persona": profile.get("persona", {}),
        "cerebellum": profile.get("cerebellum"),
        "vision_brain": profile.get("vision_brain"),
        "prompts": profile.get("prompts", {}),
        "logging": profile.get("logging"),
        "_raw_profile": profile,
    }

    return response
