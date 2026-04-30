"""
Shell Skill — 执行 bash 命令

提供 bash action，支持异步执行 shell 命令并返回 stdout/stderr。
"""

import asyncio
from agentmatrix.core.action import register_action


class ShellSkillMixin:
    """Shell 命令执行 Skill"""

    _skill_description = "执行 bash shell 命令"

    @register_action(
        short_desc="执行 bash 命令",
        description="执行 bash 命令并返回 stdout 和 stderr。超时 60 秒。",
        param_infos={"command": "要执行的 bash 命令"},
    )
    async def bash(self, command: str) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

            parts = []
            if stdout:
                parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                parts.append(f"[stderr]\n{stderr.decode('utf-8', errors='replace')}")
            if proc.returncode != 0:
                parts.append(f"[exit code: {proc.returncode}]")

            return "\n".join(parts) if parts else "(无输出)"
        except asyncio.TimeoutError:
            return "[Error] 命令执行超时（60 秒）"
        except Exception as e:
            return f"[Error] 执行失败: {e}"
