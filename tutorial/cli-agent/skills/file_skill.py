"""
File Skill — 文件操作（零外部依赖）

提供 read、write、list_dir 三个 action。
"""

import os
from pathlib import Path
from agentmatrix.core.action import register_action


class FileSkillMixin:
    """文件操作 Skill"""

    _skill_description = "文件读写和目录浏览"

    @register_action(
        short_desc="读取文件内容",
        description="读取指定路径的文件内容，返回文本",
        param_infos={"path": "文件路径（绝对或相对路径）"},
    )
    async def read(self, path: str) -> str:
        p = Path(path).expanduser()
        if not p.exists():
            return f"[Error] 文件不存在: {path}"
        if not p.is_file():
            return f"[Error] 不是文件: {path}"
        try:
            content = p.read_text(encoding="utf-8")
            return content
        except Exception as e:
            return f"[Error] 读取失败: {e}"

    @register_action(
        short_desc="写入文件内容",
        description="将内容写入指定路径的文件（不存在则创建，存在则覆盖）",
        param_infos={
            "path": "文件路径",
            "content": "要写入的文本内容",
        },
    )
    async def write(self, path: str, content: str) -> str:
        p = Path(path).expanduser()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"[Done] 已写入 {path} ({len(content)} 字符)"
        except Exception as e:
            return f"[Error] 写入失败: {e}"

    @register_action(
        short_desc="列出目录内容",
        description="列出指定目录下的文件和子目录",
        param_infos={"path": "目录路径（默认当前目录）"},
    )
    async def list_dir(self, path: str = ".") -> str:
        p = Path(path).expanduser()
        if not p.exists():
            return f"[Error] 目录不存在: {path}"
        if not p.is_dir():
            return f"[Error] 不是目录: {path}"
        try:
            entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            lines = []
            for entry in entries:
                if entry.is_dir():
                    lines.append(f"  📁 {entry.name}/")
                else:
                    size = entry.stat().st_size
                    lines.append(f"  📄 {entry.name}  ({size} B)")
            if not lines:
                return f"(空目录: {path})"
            return "\n".join(lines)
        except Exception as e:
            return f"[Error] 列出目录失败: {e}"
