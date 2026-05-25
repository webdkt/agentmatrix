"""
Pydantic request/response models for the API.
"""

from typing import Optional
from pydantic import BaseModel


class LLMConfig(BaseModel):
    """LLM configuration model"""
    url: str
    api_key: str
    model_name: str


class AgentConfigRequest(BaseModel):
    """Agent configuration request model"""
    name: str
    description: str
    class_name: str = "agentmatrix.agents.base.BaseAgent"
    backend_model: str = "default_llm"
    skills: list = []
    persona: dict = {}
    cerebellum: Optional[dict] = None
    vision_brain: Optional[dict] = None
    prompts: Optional[dict] = None
    logging: Optional[dict] = None
    extra_fields: Optional[dict] = None


class AgentUpdateRequest(BaseModel):
    """Agent update request model"""
    description: Optional[str] = None
    class_name: Optional[str] = None
    backend_model: Optional[str] = None
    skills: Optional[list] = None
    persona: Optional[dict] = None
    cerebellum: Optional[dict] = None
    vision_brain: Optional[dict] = None
    prompts: Optional[dict] = None
    logging: Optional[dict] = None
    extra_fields: Optional[dict] = None


class LLMConfigUpdateRequest(BaseModel):
    """LLM configuration update request"""
    url: str
    api_key: str
    model_name: str


class LLMConfigCreateRequest(BaseModel):
    """LLM configuration create request"""
    name: str
    url: str
    api_key: str
    model_name: str


class InvokeUIActionRequest(BaseModel):
    """UI action invoke request"""
    payload: Optional[dict] = None
