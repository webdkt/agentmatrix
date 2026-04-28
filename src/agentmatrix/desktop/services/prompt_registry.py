"""
PromptRegistry - 系统级 Prompt 注册中心

自动扫描 .matrix/configs/prompts/ 目录下所有 .md 文件，
文件名转大写作为访问键。

例如: system_prompt.md → registry.SYSTEM_PROMPT
"""

import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class PromptRegistry:
    def __init__(self, prompts_dir: Path):
        self._prompts_dir = prompts_dir
        self._prompts: Dict[str, str] = {}
        self._load_all()

    def _load_all(self):
        """扫描并加载所有 .md prompt 文件"""
        self._prompts.clear()

        if not self._prompts_dir.exists():
            logger.warning(f"⚠️ Prompts directory not found: {self._prompts_dir}")
            return

        for md_file in sorted(self._prompts_dir.glob("*.md")):
            key = self._filename_to_key(md_file.name)
            content = md_file.read_text(encoding="utf-8")
            self._prompts[key] = content
            logger.debug(f"📄 Loaded prompt: {key} ({len(content)} chars)")

        logger.info(f"✅ Loaded {len(self._prompts)} prompts from {self._prompts_dir}")

    @staticmethod
    def _filename_to_key(filename: str) -> str:
        """
        文件名 → 注册键

        system_prompt.md → SYSTEM_PROMPT
        any-file_name.md → ANY_FILE_NAME
        """
        name = filename
        if name.endswith(".md"):
            name = name[:-3]
        return name.upper().replace("-", "_").replace(" ", "_")

    def reload(self):
        """重新加载所有 prompts（热更新）"""
        self._load_all()

    def get(self, name: str) -> str:
        """
        获取 prompt 内容

        Raises:
            KeyError: prompt 不存在
        """
        if name not in self._prompts:
            available = list(self._prompts.keys())
            raise KeyError(
                f"Prompt '{name}' not found in {self._prompts_dir}. "
                f"Available: {available}"
            )
        return self._prompts[name]

    def list_prompts(self) -> List[str]:
        """列出所有已加载的 prompt 名称"""
        return list(self._prompts.keys())

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            return super().__getattribute__(name)
        try:
            return self._prompts[name]
        except KeyError:
            raise AttributeError(
                f"Prompt '{name}' not found. "
                f"Ensure {self._prompts_dir}/{name.lower()}.md exists. "
                f"Available: {list(self._prompts.keys())}"
            )

    def __contains__(self, name: str) -> bool:
        return name in self._prompts

    def __repr__(self):
        return f"PromptRegistry(dir={self._prompts_dir}, prompts={list(self._prompts.keys())})"
