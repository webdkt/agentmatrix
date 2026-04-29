"""
MicroAgent 的纯工具函数

从 micro_agent.py 中拆分出来的、不依赖 MicroAgent 实例状态的纯函数。
按类别分组：parsers、prompt builders、formatters、misc utils。
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Any


# ==================== Parsers ====================


def parse_simple_yes_no(raw_reply: str) -> dict:
    """
    解析简单的 YES/NO 响应

    Parser Contract for think_with_retry:
    - Returns {"status": "success", "content": dict} on success
    - Returns {"status": "error", "feedback": str} on error

    Args:
        raw_reply: LLM 的原始输出

    Returns:
        dict: 解析结果，{"should_exit": bool}
    """
    cleaned = raw_reply.strip().upper()

    if "YES" in cleaned and "NO" not in cleaned:
        return {
            "status": "success",
            "content": {"should_exit": True}
        }
    elif "NO" in cleaned and "YES" not in cleaned:
        return {
            "status": "success",
            "content": {"should_exit": False}
        }
    else:
        return {
            "status": "error",
            "feedback": "请只回答 YES 或 NO"
        }


def parse_and_validate_actions(
    raw_reply: str, mentioned_actions: List[str]
) -> Dict[str, Any]:
    """
    Parser: 提取并验证要执行的 actions

    流程：
    1. 使用 multi_section_parser 提取 [ACTION]
    2. 解析 action 列表（保留重复，支持多次执行同一个 action）
    3. 验证：防止幻觉（必须在 mentioned_actions 中）

    Args:
        raw_reply: LLM 的原始输出
        mentioned_actions: 阶段1提取到的"提到的actions"

    Returns:
        dict: {"status": "success", "content": [action_names]}
              或 {"status": "error", "feedback": str}
    """
    from .skill_parser_utils import multi_section_parser

    # 1. 提取 [ACTION] section
    result = multi_section_parser(
        raw_reply, section_headers=["[ACTION]"], match_mode="ALL"
    )

    if result["status"] == "error":
        return result

    # 2. 解析 actions 列表（保留重复，不去重）
    actions_text = result["content"]["[ACTION]"]
    # 先整体清理：去除换行符、回车符、代码块标记、各种引号括号
    for char in ["\n", "\r", "```", '"', "'", "`", "(", ")", "[", "]", "{", "}"]:
        actions_text = actions_text.replace(char, "")
    actions_text = actions_text.strip()
    # 再分割
    actions_list = [a.strip() for a in actions_text.split(",")]

    # 3. 验证：防止幻觉（必须在 mentioned_actions 中）
    invalid_actions = [a for a in actions_list if a not in mentioned_actions]
    if invalid_actions:
        return {
            "status": "error",
            "feedback": (
                f"你返回了未被提到的 actions: {invalid_actions}。\n"
                f"只能从用户提到的 actions 中选择: {mentioned_actions}\n\n"
                f"请重新判断，只选择用户**真正要执行**的 actions。"
            ),
        }

    return {"status": "success", "content": actions_list}


def parse_actions_from_thought(
    raw_reply: str, action_registry: dict
) -> dict:
    """
    Parser for think_with_retry - 验证 LLM 输出是否包含有效的 action 声明

    规则：
    1. 如果有 [ACTION] section → 检查下面是否有有效的 action name
       - 有 → 返回 raw_reply（验证通过）
       - 没有 → 返回 error（让 LLM 重试）
    2. 如果没有 [ACTION] section → 检查全文是否有 action name
       - 有 → 返回 raw_reply（验证通过，全文当作 [ACTION] 内容）
       - 0 个 → 也 OK（合法的"无 action"回复）

    Args:
        raw_reply: LLM 的原始输出
        action_registry: 可用的 actions 注册表

    Returns:
        {
            "status": "success" | "error",
            "content": raw_reply (success 时) | None (error 时),
            "feedback": str (error 时)
        }
    """
    # 规则1：检查是否有 [ACTION] section
    if "[ACTION]" in raw_reply:
        # ✅ 修复：清理 [ACTION] 之前的所有内容，避免干扰解析
        actions_index = raw_reply.find("[ACTION]")
        cleaned_reply = raw_reply[actions_index:].strip()

        # 提取 [ACTION] 下的内容
        from .skill_parser_utils import multi_section_parser

        result = multi_section_parser(
            cleaned_reply,
            section_headers=["[ACTION]"],
            match_mode="ANY",
        )

        if result["status"] == "success":
            actions_text = result["content"]["[ACTION]"]
        else:
            actions_text = ""

        # 检查是否包含有效的 action
        action_pattern = r"([a-zA-Z_][a-zA-Z0-9_]*)"
        matches = re.finditer(action_pattern, actions_text)

        detected_actions = set()
        for match in matches:
            action_name = match.group(1).lower()
            if action_name in action_registry:
                detected_actions.add(action_name)

        # 有 action 或无 action 都 OK
        content = {"[ACTION]": actions_text, "[RAW_REPLY]": raw_reply}
        return {"status": "success", "content": content}

    # 规则2：没有 [ACTION] section → 尝试从内容中提取 XML 或 JSON 块

    def clean_code_blocks(text: str) -> str:
        """去掉代码块包裹标记（如 ```json, ```xml, ```）"""
        text = text.strip()
        patterns = [
            r'```json\s*\n(.*?)\n```',
            r'```xml\s*\n(.*?)\n```',
            r'```\s*\n(.*?)\n```',
            r'```json\s+(.+?)\s*```',
            r'```xml\s+(.+?)\s*```',
            r'```\s+(.+?)\s*```',
        ]
        for pattern in patterns:
            match = re.match(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        return text

    # 清理代码块
    cleaned = clean_code_blocks(raw_reply)

    # 尝试提取 JSON 块
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    json_matches = re.findall(json_pattern, cleaned, re.DOTALL)
    for match in json_matches:
        try:
            json.loads(match)
            content = {"[ACTION]": match, "[RAW_REPLY]": raw_reply}
            return {"status": "success", "content": content}
        except (json.JSONDecodeError, ValueError):
            continue

    # 尝试提取 XML 块（<tag>...</tag> 或 <tag/>）
    xml_pattern = r'<[^>]+>.*?</[^>]+>|<[^>]+/>'
    xml_matches = re.findall(xml_pattern, cleaned, re.DOTALL)
    if xml_matches:
        extracted = "\n".join(xml_matches)
        content = {"[ACTION]": extracted, "[RAW_REPLY]": raw_reply}
        return {"status": "success", "content": content}

    # 都没有，当作无 action 回复
    content = {"[ACTION]": "", "[RAW_REPLY]": raw_reply}
    return {"status": "success", "content": content}


def extract_mentioned_actions(thought: str, action_registry_flat: dict) -> List[str]:
    """
    使用正则表达式提取用户**提到**的所有 action（完整单词匹配）

    注意：
    - 这个方法只是提取"提到的"actions，不是"要执行的"actions
    - 最终要执行哪些actions需要由小脑进一步判断
    - 保留重复出现的 action（支持多次执行同一个 action）

    Example:
        "我刚做完了web_search，现在准备file_operation" → ["web_search", "file_operation"]
        "使用send_email发送" → ["send_email"]
        "先搜索，然后完成" → ["web_search"]
        "write A, write B, write C" → ["write", "write", "write"]

    Args:
        thought: LLM 的思考内容
        action_registry_flat: action_registry["_flat"] 字典

    Returns:
        List[str]: 提到的 action 名称列表（保留重复和顺序）
    """
    # 正则：匹配连续的字母、下划线、数字（标识符格式）
    action_pattern = r"([a-zA-Z_][a-zA-Z0-9_]*)"

    # 提取所有匹配的字符串
    matches = re.finditer(action_pattern, thought)

    # 按出现顺序记录 (position, action_name)
    detected = []

    for match in matches:
        action_name = match.group(1)
        position = match.start()

        # 转小写（action names 通常是 snake_case）
        action_name_lower = action_name.lower()

        # 只保留有效的 action names（在 action_registry_flat 中）
        if action_name_lower in action_registry_flat:
            detected.append((position, action_name_lower))

    # 按出现位置排序
    detected.sort(key=lambda x: x[0])

    # 返回 action 名称列表（保留重复和顺序）
    return [action for _, action in detected]


# ==================== Prompt Builders ====================


def build_exit_verification_prompt(raw_reply: str) -> str:
    """构建退出验证 prompt"""
    return f"""判断以下文本的意思是否表明说话的人认为"目前没什么可做或者暂时不需要做什么，或者应该等待"。

文本：
```
{raw_reply}
```

你需要作出的回答：
- YES: 表示"目前没什么可做的"、"暂时不需要做什么"、"已完成"、"需要等待"这样的意思
- NO: 表示不是上述意思

只回答 YES 或 NO。"""


def build_no_action_reflect_message(
    action_section_text: str,
    raw_reply: str,
    action_registry_flat: dict,
) -> Optional[str]:
    """
    检查 [ACTION] 文本中是否有疑似幻觉的函数调用 pattern，构造 reflect 消息。

    如果 [ACTION] 文本匹配 func_name(...) 或 func.name(...) 格式，
    但没有匹配到任何注册的 action，说明 LLM 幻觉了函数名。

    同时检查 raw_reply：当 [ACTION] 为空但 raw_reply 中包含 JSON/XML action 格式
    或函数调用 pattern 时，说明 LLM 试图输出 action 但格式不对（缺少 [ACTION] 标记）。

    Args:
        action_section_text: [ACTION] 区块的文本
        raw_reply: LLM 的完整原始回复
        action_registry_flat: action_registry["_flat"] 字典

    Returns:
        reflect 消息字符串，如果没有疑似幻觉则返回 None
    """
    if not action_section_text or not action_section_text.strip():
        # [ACTION] 区为空，但检查 raw_reply 中是否有疑似 action 的内容
        if raw_reply:
            # 检查 JSON 格式的 action: "action": "xxx"
            json_action_pattern = r'"action"\s*:\s*"([a-zA-Z_.]*)"'
            json_matches = re.findall(json_action_pattern, raw_reply)

            # 检查 XML 格式的 action: <function*> 标签
            xml_action_pattern = r'<function[\w-]*\s*(?:name\s*=\s*["\']([^"\']+)["\'])?[^>]*>(?:\s*(\w+(?:\.\w+)*)\s*</[\w-]+>)?'
            xml_matches = re.findall(xml_action_pattern, raw_reply)
            # 展平结果：findall 返回 [(name_from_attr, content), ...]
            xml_function_names = []
            for match in xml_matches:
                name_from_attr, content = match
                if name_from_attr:
                    xml_function_names.append(name_from_attr)
                elif content:
                    xml_function_names.append(content)

            # 检查函数调用 pattern
            call_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\s*\('
            call_matches = re.findall(call_pattern, raw_reply)

            # 验证是否包含有效的 action（忽略大小写）
            valid_actions = []
            for name in (json_matches + xml_function_names + call_matches):
                if name.lower() in action_registry_flat:
                    valid_actions.append(name)

            if valid_actions:
                return "没有发现要执行的action。如果要执行action，需要使用 [ACTION] 块格式来声明。确认没什么要执行的可以回复'确定'。"

        # 确实没有疑似 action 的内容
        return None

    # 匹配 func_name(...) 或 func.name(...) 格式
    call_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\s*\('
    matches = re.findall(call_pattern, action_section_text)

    if not matches:
        return None

    # 找到不在 registry 中的函数名
    invalid_names = []
    valid_names = []
    for name in matches:
        name_lower = name.lower()
        if name_lower not in action_registry_flat:
            invalid_names.append(name)
        else:
            valid_names.append(name)

    if not invalid_names:
        # 所有提到的函数名都在 registry 中，不是幻觉问题
        return None

    # 构建更具体的提示，包含无效名称和可用的 action 列表
    invalid_list = ", ".join(invalid_names)
    hint = f"没有发现要执行的action。你在 [ACTION] 中使用了未注册的名称：{invalid_list}。"
    if valid_names:
        hint += f"其中 {', '.join(valid_names)} 是有效的。"
    hint += "请检查action名称是否正确（可用的action名称请参考系统提示中的action列表）。确认没什么要执行的可以回复'确定'。"
    return hint


# ==================== Formatters ====================


def format_messages_for_debug(messages: List[Dict]) -> str:
    """
    格式化 messages 列表为人类友好的调试输出

    Args:
        messages: 消息列表，每条消息包含 role 和 content

    Returns:
        格式化后的字符串
    """
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        # 截取前 3000 字符，避免输出过长
        preview = content[:3000] + "..." if len(content) > 3000 else content

        lines.append(f"{role}: {preview}")

    return "\n".join(lines)


def format_email_history(emails, agent_name: str) -> str:
    """
    格式化邮件历史为紧凑聊天风格

    格式：
    - 收到的邮件:   sender_name:
    - 发出的邮件:   -> recipient_name:
    - 仅最后一封保留时间戳
    - 有附件时列出文件名

    Args:
        emails: 邮件列表（已按时间排序）
        agent_name: 当前 agent 的名字（用于判断邮件方向）

    Returns:
        str: 格式化的邮件历史字符串
    """
    if not emails:
        return "[EMAIL HISTORY]\n暂无邮件历史\n"

    lines = ["[EMAIL HISTORY]"]
    lines.append("注：你发出的邮件会用 `-> 收件人名字` 的方式标出")

    today = datetime.now().date()

    for i, email in enumerate(emails):
        # 判断邮件方向：发件人是否是自己
        sender_raw = (
            email.sender.split("@")[0] if "@" in email.sender else email.sender
        )
        recipient_raw = (
            email.recipient.split("@")[0]
            if "@" in email.recipient
            else email.recipient
        )

        if sender_raw == agent_name:
            header = f"-> {recipient_raw}:"
        else:
            header = f"{sender_raw}:"

        # 智能时间戳：今天只显示 hh:mm，更早的显示 yyyy/mm/dd
        ts = email.timestamp
        if ts.date() == today:
            time_str = ts.strftime("%H:%M")
        else:
            time_str = ts.strftime("%Y/%m/%d")
        header += f"  ({time_str})"

        # 正文：去掉内部空行，确保空行只作为邮件间的分隔
        body_lines = [
            line for line in email.body.strip().split("\n") if line.strip()
        ]

        lines.append("")
        lines.append(header)
        lines.extend(body_lines)

        # 附件
        if email.attachments:
            filenames = [att.get("filename", "?") for att in email.attachments]
            lines.append(f"[attachments: {', '.join(filenames)}]")

    lines.append("")
    lines.append("[END OF EMAIL HISTORY]")

    return "\n".join(lines)


def format_skills_overview(action_registry: dict) -> str:
    """
    格式化 skills 概览（按 skill 分组）

    格式：
    **skill_name**: skill 描述
      • action1: action1_short_desc
      • action2: action2_short_desc
      • action3: action3_short_desc

    Args:
        action_registry: MicroAgent 的 action_registry 字典
    """
    lines = []

    for skill_name, actions in action_registry["_by_skill"].items():
        lines.append(f"**{skill_name}**:")

        # 添加 actions 列表
        for action_name, method in actions.items():
            short_desc = getattr(method, "_action_short_desc", None)
            if short_desc:
                lines.append(f"  • {action_name}: {short_desc}")
            else:
                lines.append(f"  • {action_name}")

        lines.append("")  # 空行分隔

    return "\n".join(lines)


# ==================== Misc Utils ====================


def infer_skill_name(class_name: str) -> str:
    """
    从类名推断 skill 名称

    Examples:
        FileSkillMixin → file
        Simple_web_searchSkillMixin → simple_web_search
        EmailSkillMixin → email
    """
    # 移除 SkillMixin 后缀
    if class_name.endswith("SkillMixin"):
        base_name = class_name[:-10]  # 移除 "SkillMixin"
    elif class_name.endswith("Mixin"):
        base_name = class_name[:-5]  # 移除 "Mixin"
    else:
        base_name = class_name

    # 转换为小写
    return base_name.lower()


def read_skill_description(skill_md_path) -> str:
    """
    从 skill.md 的 frontmatter 中提取 description

    容错：无 frontmatter 或无 description 字段时返回提示文本
    """
    try:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 查找 frontmatter（--- 包裹）
        parts = content.split("---", 2)
        if len(parts) < 3:
            return "（请打开 skill 文件查看详细介绍）"

        frontmatter_text = parts[1]

        # 在 frontmatter 中查找 description 行
        for line in frontmatter_text.split("\n"):
            stripped = line.strip()
            if stripped.lower().startswith("description:"):
                desc = stripped[len("description:"):].strip()
                # 去除引号
                if (desc.startswith('"') and desc.endswith('"')) or \
                   (desc.startswith("'") and desc.endswith("'")):
                    desc = desc[1:-1]
                if desc:
                    # 限制长度
                    if len(desc) > 120:
                        desc = desc[:117] + "..."
                    return desc

        return "（请打开 skill 文件查看详细介绍）"

    except Exception:
        return "（请打开 skill 文件查看详细介绍）"
