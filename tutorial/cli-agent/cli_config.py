"""
CLI Config — 配置管理。

管理 LLM provider、model、API key 等配置。
支持从 YAML 配置文件加载（cli_agent.yaml），配置文件不入版本控制。
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# 配置文件路径（固定在 cli-agent 目录下）
CONFIG_FILE = Path(__file__).parent / "cli_agent.yaml"


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
    skill_dirs: list = field(default_factory=list)  # Python skill 搜索目录
    skills: list = field(default_factory=list)  # 初始 skill 列表

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


def load_config_file() -> dict:
    """从 cli_agent.yaml 加载配置，文件不存在则返回空 dict。"""
    if not CONFIG_FILE.exists():
        return {}
    try:
        import yaml
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        logger.info(f"加载配置文件: {CONFIG_FILE}")
        return data
    except ImportError:
        logger.warning("未安装 pyyaml，跳过配置文件加载")
        return {}
    except Exception as e:
        logger.warning(f"加载配置文件失败: {e}")
        return {}


def apply_config_file(config: CLIConfig, data: dict):
    """将配置文件数据应用到 CLIConfig，只覆盖非空字段。"""
    if data.get("api_key"):
        config.llm_api_key = data["api_key"]
    if data.get("model"):
        config.set_llm(data["model"])
    if data.get("url"):
        config.set_url(data["url"])
    if data.get("system_prompt"):
        config.system_prompt = data["system_prompt"]
    if data.get("system_prompt_file"):
        p = Path(data["system_prompt_file"]).expanduser()
        if p.exists():
            config.system_prompt = p.read_text(encoding="utf-8")
            config.system_prompt_file = str(p)
    if data.get("skill_dirs"):
        config.skill_dirs = data["skill_dirs"]
    if data.get("skills"):
        config.skills = data["skills"]


def load_config() -> CLIConfig:
    """创建配置并从配置文件加载。"""
    config = CLIConfig()
    data = load_config_file()
    if data:
        apply_config_file(config, data)
    return config
