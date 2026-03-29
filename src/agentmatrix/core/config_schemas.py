"""
Config Schemas - Pydantic models for configuration validation

Provides:
- Type-safe configuration validation
- JSON Schema generation for Agent discovery
- Structured error messages for LLM-friendly feedback
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator


# ==================== Email Proxy ====================


class SMTPConfig(BaseModel):
    model_config = {"extra": "forbid"}

    host: str = Field(..., description="SMTP server host, e.g. smtp.gmail.com")
    port: int = Field(
        587, description="SMTP port, typically 587 (STARTTLS) or 465 (SSL)"
    )
    user: str = Field(..., description="SMTP username (email address)")
    password: str = Field(..., description="SMTP password or app password")


class IMAPConfig(BaseModel):
    model_config = {"extra": "forbid"}

    host: str = Field(..., description="IMAP server host, e.g. imap.gmail.com")
    port: int = Field(993, description="IMAP port, typically 993 (SSL)")
    user: str = Field(..., description="IMAP username (email address)")
    password: str = Field(..., description="IMAP password or app password")


class EmailProxyConfig(BaseModel):
    model_config = {"extra": "forbid"}  # 拒绝未知字段

    enabled: bool = Field(False, description="Whether email proxy is enabled")
    matrix_mailbox: str = Field(
        "", description="Matrix mailbox address for sending emails to user"
    )
    user_mailbox: str = Field(
        "", description="User mailbox address, only receive from this address"
    )
    smtp: Optional[SMTPConfig] = Field(
        None, description="SMTP configuration for sending emails"
    )
    imap: Optional[IMAPConfig] = Field(
        None, description="IMAP configuration for receiving emails"
    )

    @model_validator(mode="after")
    def check_consistency(self) -> "EmailProxyConfig":
        if self.enabled:
            if not self.matrix_mailbox:
                raise ValueError(
                    "matrix_mailbox is required when email proxy is enabled"
                )
            if not self.user_mailbox:
                raise ValueError("user_mailbox is required when email proxy is enabled")
            if not self.smtp:
                raise ValueError(
                    "smtp configuration is required when email proxy is enabled"
                )
            if not self.imap:
                raise ValueError(
                    "imap configuration is required when email proxy is enabled"
                )
        return self


# ==================== LLM Config ====================


class LLMModelConfig(BaseModel):
    url: str = Field(..., description="API endpoint URL")
    API_KEY: str = Field(
        ..., description="API key (can be env var name like OPENAI_API_KEY)"
    )
    model_name: str = Field(
        ..., description="Model identifier, e.g. gpt-4o, claude-sonnet-4-20250514"
    )


class LLMConfig(BaseModel):
    """Dynamic keys: each key is a model name, value is LLMModelConfig.
    default_slm is required."""

    default_slm: LLMModelConfig = Field(
        ..., description="Default Small Language Model for cerebellum"
    )
    # Other keys handled via model_extra

    class Config:
        extra = "allow"  # Allow arbitrary model names as keys

    @model_validator(mode="before")
    @classmethod
    def validate_default_slm(cls, values: dict) -> dict:
        if isinstance(values, dict) and "default_slm" not in values:
            raise ValueError("llm_config.json must contain 'default_slm' configuration")
        return values

    def get_all_model_names(self) -> List[str]:
        return list(self.model_extra.keys()) if self.model_extra else []

    def get_model_config(self, name: str) -> Optional[LLMModelConfig]:
        if name == "default_slm":
            return self.default_slm
        if self.model_extra and name in self.model_extra:
            data = self.model_extra[name]
            if isinstance(data, dict):
                return LLMModelConfig(**data)
            return data
        return None


# ==================== System Config ==================


class SystemConfig(BaseModel):
    model_config = {"extra": "forbid"}

    user_agent_name: str = Field("User", description="Name of the user agent")
    matrix_version: str = Field("1.0.0", description="AgentMatrix version")
    description: str = Field("", description="World description")
    timezone: str = Field("UTC", description="Default timezone")


# ==================== Agent Profile ====================


class AgentProfile(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(..., description="Agent name (unique identifier)")
    description: str = Field(..., description="One-line description of the agent")
    class_name: str = Field(
        "agentmatrix.agents.base.BaseAgent", description="Full class path"
    )
    backend_model: str = Field(
        "default_llm", description="LLM model name from llm_config.json"
    )
    persona: str = Field(
        "",
        description='Persona prompt, e.g. "You are a helpful assistant."',
    )
    skills: List[str] = Field(
        default_factory=list,
        description='List of skill names, e.g. ["base", "email", "file"]',
    )
    prompts: Optional[Dict[str, str]] = Field(
        None, description="Additional prompt templates"
    )
    cerebellum: Optional[Dict[str, str]] = Field(
        None, description="Cerebellum (SLM) configuration"
    )
    vision_brain: Optional[Dict[str, str]] = Field(
        None, description="Vision brain configuration"
    )
    attribute_initializations: Optional[Dict[str, Any]] = Field(
        None, description="Instance attributes to inject"
    )
    class_attributes: Optional[Dict[str, Any]] = Field(
        None, description="Class-level attributes"
    )
    logging: Optional[Dict[str, Any]] = Field(
        None, description="Component-level logging config"
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Agent name cannot be empty")
        return v.strip()


# ==================== JSON Schema Export ====================


def get_schema(config_type: str) -> dict:
    """
    Get JSON Schema for a config type.

    Args:
        config_type: One of "agent", "llm", "system", "email_proxy"

    Returns:
        dict: JSON Schema

    Raises:
        ValueError: If config_type is unknown
    """
    schema_map = {
        "agent": AgentProfile.model_json_schema,
        "llm": LLMModelConfig.model_json_schema,  # Single model entry
        "system": SystemConfig.model_json_schema,
        "email_proxy": EmailProxyConfig.model_json_schema,
    }

    if config_type not in schema_map:
        raise ValueError(
            f"Unknown config type: '{config_type}'. "
            f"Available types: {list(schema_map.keys())}"
        )

    return schema_map[config_type]()


def get_config_types() -> List[str]:
    """Return list of available config types."""
    return ["agent", "llm", "system", "email_proxy"]
