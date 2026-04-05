"""
Parser Utils for Memory Skill

提供 recall action 使用的 parser 函数，配合 think_with_retry 模式使用。
"""

import json
import re


def keyword_groups_parser(raw_reply: str) -> dict:
    """
    解析关键词分组（JSON 格式）— 支持 OR-of-AND 结构

    期望的 JSON 格式：
    {"groups": [["kw1a", "kw1b"], ["kw2"], ["kw3a", "kw3b"]]}

    - 顶层 groups 数组 = OR 关系（按顺序尝试）
    - 每个 group = AND 关系（所有关键词必须同时匹配）
    - 限制：最多 3 组，每组最多 3 个关键词

    支持：
    - 纯 JSON
    - Markdown code block: ```json ... ```

    Args:
        raw_reply: LLM 的原始输出

    Returns:
        {
            "status": "success" | "error",
            "content": List[List[str]],
            "feedback": str (仅错误时)
        }
    """
    json_str = raw_reply.strip()

    # 去除 markdown code block
    if "```json" in json_str:
        match = re.search(r'```json\s*(.*?)\s*```', json_str, re.DOTALL)
        if match:
            json_str = match.group(1)
    elif "```" in json_str:
        match = re.search(r'```\s*(.*?)\s*```', json_str, re.DOTALL)
        if match:
            json_str = match.group(1)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "feedback": f"无效的 JSON 格式：{str(e)}。请输出纯 JSON 格式。"
        }

    if not isinstance(data, dict) or "groups" not in data:
        return {
            "status": "error",
            "feedback": "JSON 必须包含 'groups' 字段"
        }

    groups = data["groups"]
    if not isinstance(groups, list):
        return {
            "status": "error",
            "feedback": "'groups' 必须是数组"
        }

    if len(groups) > 3:
        return {
            "status": "error",
            "feedback": "最多 3 组关键词"
        }

    # 验证每组
    cleaned = []
    for i, group in enumerate(groups):
        if not isinstance(group, list):
            return {
                "status": "error",
                "feedback": f"第 {i+1} 组必须是数组"
            }
        if not group:
            return {
                "status": "error",
                "feedback": f"第 {i+1} 组不能为空"
            }
        if len(group) > 3:
            return {
                "status": "error",
                "feedback": f"第 {i+1} 组最多 3 个关键词"
            }
        if not all(isinstance(k, str) and k.strip() for k in group):
            return {
                "status": "error",
                "feedback": f"第 {i+1} 组的关键词必须是非空字符串"
            }
        cleaned.append([k.strip() for k in group])

    return {
        "status": "success",
        "content": cleaned
    }
