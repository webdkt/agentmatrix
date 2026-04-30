"""
CLI Config — 配置管理。

管理 LLM provider、model、API key 等配置。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CLIConfig:
    """CLI Agent 配置"""

    # LLM 配置
    llm_url: str = "https://api.deepseek.com/chat/completions"
    llm_api_key: str = ""
    llm_model: str = "deepseek-v4-pro"

    # Agent 配置
    agent_name: str = "CLI-Agent"
    system_prompt_file: Optional[str] = None
    system_prompt: str = "你是一个有用的 AI 助手，可以通过工具完成用户的任务。"

    # Skill 配置
    skill_dir: Optional[str] = None  # MD skill 目录

    # 压缩阈值
    compression_token_threshold: int = 64000

    def set_llm(self, value: str):
        """设置 LLM 配置。

        支持的格式：
        - provider:model（如 openai:gpt-4o、deepseek:deepseek-chat）
        - url:model（如 https://my-api.com/v1/chat/completions:gpt-4o）
        - url（仅设置 URL，model 不变）
        - model（仅设置 model，URL 不变）
        """
        if ":" not in value:
            # 没有冒号：可能是纯 model 名，也可能是纯 URL
            if value.startswith("http"):
                self.llm_url = value
            else:
                self.llm_model = value
            return

        # 有冒号：需要区分是 provider:model 还是 url:model
        # URL 格式：以 http 开头，冒号后面是端口号或 model
        if value.startswith("http"):
            # URL 格式。尝试从末尾提取 model（最后一个 : 分隔）
            # 但 URL 本身包含 :// 和可能的 :port
            # 策略：找最后一个不在 URL 主体中的冒号
            # 简单方法：如果最后 : 后面不以 / 开头且不全是数字，当 model
            last_colon = value.rfind(":")
            before = value[:last_colon]
            after = value[last_colon + 1:]

            # 如果 after 是纯数字（端口号）或以 / 开头（路径），则整体是 URL
            if after.startswith("/") or after.isdigit():
                self.llm_url = value
            else:
                self.llm_url = before
                self.llm_model = after
            return

        # provider:model 格式
        provider, model = value.split(":", 1)
        provider = provider.lower()

        if provider == "openai":
            self.llm_url = "https://api.openai.com/v1/chat/completions"
            self.llm_model = model
        elif provider == "deepseek":
            self.llm_url = "https://api.deepseek.com/chat/completions"
            self.llm_model = model
        elif provider == "gemini":
            self.llm_url = "https://generativelanguage.googleapis.com/v1beta"
            self.llm_model = model
        else:
            self.llm_model = f"{provider}/{model}"

    def set_url(self, url: str):
        """单独设置 API endpoint URL。"""
        self.llm_url = url
