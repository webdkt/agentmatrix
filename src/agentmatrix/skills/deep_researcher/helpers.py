"""
Research Planner Helpers

- format_prompt() 工具函数
- 解析器：persona_parser, research_plan_parser, parse_research_plan
- 文件读写工具函数
"""

import re
from pathlib import Path
from typing import Any, Optional


# ==========================================
# 文件读写工具
# ==========================================


def read_work_file(work_dir: str, rel_path: str) -> str:
    """读取 work_dir/{rel_path} 文件内容"""
    file_path = Path(work_dir) / rel_path
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8")


def write_work_file(work_dir: str, rel_path: str, content: str) -> None:
    """写入 work_dir/{rel_path} 文件"""
    file_path = Path(work_dir) / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


# ==========================================
# Prompt 格式化工具
# ==========================================


def format_prompt(prompt: str, context: Any = None, **kwargs) -> str:
    """
    根据 context 对象/字典和 kwargs 填充 prompt 占位符

    优先级: kwargs > context
    """
    placeholders = re.findall(r"\{(\w+)\}", prompt)
    format_dict = {}
    missing = []

    for p in placeholders:
        if p in kwargs:
            format_dict[p] = kwargs[p]
        elif isinstance(context, dict) and p in context:
            format_dict[p] = context[p]
        elif context is not None and hasattr(context, p):
            format_dict[p] = getattr(context, p)
        else:
            missing.append(p)

    if missing:
        raise KeyError(f"缺少以下占位符: {', '.join(missing)}")

    return prompt.format(**format_dict)


# ==========================================
# 解析器
# ==========================================


def persona_parser(raw_reply: str, header="[正式文稿]") -> dict:
    """
    解析人设生成输出，提取 [正式文稿] 之后的内容。
    """
    from ..parser_utils import simple_section_parser

    result = simple_section_parser(raw_reply, header)
    if result["status"] == "success":
        content = result["content"]
        if isinstance(content, dict):
            content = content.get(header, "")

        if not content.startswith("你是"):
            return {"status": "error", "feedback": "正式文稿必须以'你是'开头"}

        content = content.replace("你是", "")
        return {"status": "success", "content": content}

    return result


def parse_research_plan(text: str) -> list:
    """
    从 research_plan.md 解析任务列表

    格式: - [pending/in_progress/completed] 任务描述 | 总结: ...
    返回: [{"status": "pending", "task": "...", "summary": "..."}, ...]
    """
    tasks = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line.startswith("- ["):
            continue

        status_match = re.match(r"- \[(\w+)\]\s*(.*)", line)
        if not status_match:
            continue

        status = status_match.group(1).lower()
        rest = status_match.group(2)

        if "|" in rest:
            task_part, summary_part = rest.split("|", 1)
            task = task_part.strip()
            summary = summary_part.replace("总结:", "").strip()
        else:
            task = rest.strip()
            summary = ""

        tasks.append({"status": status, "task": task, "summary": summary})

    return tasks
