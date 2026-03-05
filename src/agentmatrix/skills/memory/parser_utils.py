"""
Parser Utils for Memory Skill

提供 recall action 使用的 parser 函数，配合 think_with_retry 模式使用。
"""

import json
import re


def recall_answer_parser(raw_reply: str) -> dict:
    """
    解析 recall 的 LLM 回答（强制 JSON 格式）

    期望的 JSON 格式：
    {
        "answer": "答案内容",
        "can_answer_user": true 或 false (布尔值)
    }

    支持：
    - 纯 JSON
    - Markdown code block: ```json ... ```
    - 字符串 "True"/"False" 会自动转换为布尔值

    Args:
        raw_reply: LLM 的原始输出

    Returns:
        {
            "status": "success" | "error",
            "content": {"answer": str, "can_answer_user": bool},
            "feedback": str (仅错误时)
        }
    """
    # 1. 尝试提取 JSON（支持 markdown code block）
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

    # 2. 尝试解析 JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "feedback": f"无效的 JSON 格式：{str(e)}。请输出纯 JSON 格式，不要有其他文字。"
        }

    # 3. 验证 JSON 结构
    if not isinstance(data, dict):
        return {
            "status": "error",
            "feedback": f"JSON 必须是对象格式，当前是 {type(data).__name__}"
        }

    if "answer" not in data:
        return {
            "status": "error",
            "feedback": "JSON 缺少必需字段 'answer'"
        }

    if "can_answer_user" not in data:
        return {
            "status": "error",
            "feedback": "JSON 缺少必需字段 'can_answer_user'"
        }

    # 4. 处理 can_answer_user 的值（支持字符串和布尔值）
    can_answer_raw = data["can_answer_user"]

    # 如果是字符串，转换为布尔值
    if isinstance(can_answer_raw, str):
        can_answer_raw = can_answer_raw.strip().lower()
        if can_answer_raw in ["true", "1", "yes"]:
            can_answer = True
        elif can_answer_raw in ["false", "0", "no"]:
            can_answer = False
        else:
            return {
                "status": "error",
                "feedback": f"'can_answer_user' 的值必须是布尔值或 'True'/'False' 字符串，当前是：{data['can_answer_user']}"
            }
    elif isinstance(can_answer_raw, bool):
        can_answer = can_answer_raw
    elif isinstance(can_answer_raw, int):
        # 支持数字 0/1
        can_answer = bool(can_answer_raw)
    else:
        return {
            "status": "error",
            "feedback": f"'can_answer_user' 的类型必须是布尔值、字符串或整数，当前是：{type(can_answer_raw).__name__}"
        }

    # 5. 成功，返回结构化数据
    return {
        "status": "success",
        "content": {
            "answer": str(data["answer"]).strip(),
            "can_answer_user": can_answer
        }
    }


def events_list_parser(raw_reply: str) -> dict:
    """
    解析 event list（Markdown 格式）

    期望格式：
    [EVENTS]
    # 事件1
    实体1, 实体2

    # 事件2
    实体A

    Returns:
        {
            "status": "success" | "error",
            "content": List[Dict],  # [{"event": str, "entities": List[str]}]
            "feedback": str (仅错误时)
        }
    """
    # 1. 提取 [EVENTS] section
    if "[EVENTS]" not in raw_reply:
        return {
            "status": "error",
            "feedback": "必须包含 [EVENTS] section"
        }

    # 提取 [EVENTS] 后的内容
    events_section = raw_reply.split("[EVENTS]")[-1].strip()

    # 2. 按 `# ` 分割出各个事件
    lines = events_section.split('\n')
    events = []
    current_event = None
    current_entities = []

    for line in lines:
        line = line.strip()
        if not line:
            # 空行，继续
            continue

        # 检查是否是二级标题（事件描述）
        if line.startswith('# '):
            # 保存上一个事件（如果有）
            if current_event:
                events.append({
                    "event": current_event,
                    "entities": current_entities.copy()
                })

            # 开始新事件
            current_event = line[2:].strip()  # 去掉 `# `
            current_entities = []
        else:
            # 实体列表
            if current_event is not None:
                # 按逗号分割
                entities_in_line = [e.strip() for e in line.split(',') if e.strip()]
                if entities_in_line:
                    current_entities.extend(entities_in_line)

    # 保存最后一个事件
    if current_event:
        events.append({
            "event": current_event,
            "entities": current_entities
        })

    # 3. 验证：检查是否为 "NO EVENTS"
    # 如果 events_section 明确写了 "NO EVENTS"，返回空列表
    if "NO EVENTS" in events_section.upper():
        return {
            "status": "success",
            "content": []
        }

    # 如果没有解析到任何事件，也返回空列表（宽松模式）
    if not events:
        return {
            "status": "success",
            "content": []
        }

    # 4. 成功
    return {
        "status": "success",
        "content": events
    }
