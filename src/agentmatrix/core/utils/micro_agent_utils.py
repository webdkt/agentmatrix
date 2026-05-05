"""
MicroAgent 的纯工具函数

从 micro_agent.py 中拆分出来的、不依赖 MicroAgent 实例状态的纯函数。
按类别分组：parsers、prompt builders、formatters、misc utils。
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple


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
            "content": {"should_exit": False}
        }
    elif "NO" in cleaned and "YES" not in cleaned:
        return {
            "status": "success",
            "content": {"should_exit": True}
        }
    else:
        return {
            "status": "error",
            "feedback": "请只回答 YES 或 NO"
        }


def parse_actions_from_thought(raw_reply: str) -> dict:
    """
    Parser for think_with_retry — 提取 <action_script> 块内容。

    Args:
        raw_reply: LLM 的原始输出

    Returns:
        {"status": "success", "content": {"[ACTION]": str, "[RAW_REPLY]": str}}
        [ACTION] 为 <action_script> 块内的文本（不含标签）
    """
    action_text = extract_action_script_block(raw_reply)

    content = {"[ACTION]": action_text, "[RAW_REPLY]": raw_reply}
    return {"status": "success", "content": content}


def extract_action_script_block(text: str) -> str:
    """
    从 LLM 输出中提取 <action_script>...</action_script> 块的内容。

    Returns:
        块内的文本（不含标签），如果没有找到则返回空字符串
    """
    pattern = r'<action_script>(.*?)</action_script>'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def parse_function_calls(
    text: str, action_registry_flat: dict
) -> Tuple[List[Tuple[str, str]], List[str]]:
    """
    Step 2: 解析文本中的函数式调用 action_name(params)。

    支持：
    - action_name(params) — 短名
    - skill.action_name(params) — 命名空间
    - 多行 params（括号配对匹配）
    - 嵌套括号

    Args:
        text: LLM 输出文本
        action_registry_flat: action_registry["_flat"] 字典

    Returns:
        (valid_calls, hallucination_names)
        - valid_calls: [(action_name, params_text), ...] — 在 registry 中的
        - hallucination_names: [name, ...] — 函数格式正确但 name 不存在
    """
    valid_calls = []
    hallucinations = []

    # 匹配行首的 func_name( 或 skill.func_name(
    # 支持前导空白
    func_pattern = re.compile(
        r'^[ \t]*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\s*\(',
        re.MULTILINE,
    )

    for match in func_pattern.finditer(text):
        func_name = match.group(1).lower()
        start_paren = match.end() - 1  # '(' 的位置

        # 括号配对，支持多行和嵌套
        depth = 1
        pos = start_paren + 1
        while pos < len(text) and depth > 0:
            ch = text[pos]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            pos += 1

        if depth != 0:
            # 括号未闭合，跳过
            continue

        # params_text 是括号内的内容（不含外层括号）
        params_text = text[start_paren + 1 : pos - 1].strip()

        if func_name in action_registry_flat:
            valid_calls.append((func_name, params_text))
        else:
            hallucinations.append(func_name)

    return valid_calls, hallucinations


def parse_params_from_call(params_text: str) -> Dict[str, Any]:
    """
    解析函数式调用中的参数文本为字典。

    支持格式：key=value, key2=value2
    值类型：带引号字符串、数字、布尔值、None、无引号字符串

    Args:
        params_text: 括号内的参数文本

    Returns:
        参数字典 {"key": value, ...}
    """
    if not params_text:
        return {}

    result = {}

    # 按逗号分割，但要忽略引号内的逗号
    parts = _split_params(params_text)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 找第一个 = 分割 key=value
        eq_pos = part.find('=')
        if eq_pos < 0:
            # 没有 =，可能是位置参数，跳过
            continue

        key = part[:eq_pos].strip()
        value_str = part[eq_pos + 1:].strip()

        if not key:
            continue

        result[key] = _parse_value(value_str)

    return result


def _split_params(text: str) -> List[str]:
    """按逗号分割参数，忽略引号内的逗号和嵌套括号内的逗号。"""
    parts = []
    current = []
    depth = 0
    in_quote = None

    for ch in text:
        if in_quote:
            current.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
            current.append(ch)
        elif ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)

    if current:
        parts.append(''.join(current))

    return parts


def _parse_value(value_str: str) -> Any:
    """解析单个参数值字符串为 Python 值。"""
    import ast

    # 去掉首尾空白
    value_str = value_str.strip()

    # 空字符串
    if not value_str:
        return ""

    # 带引号字符串：用 ast.literal_eval 解释转义序列（\n → 换行等）
    if (value_str.startswith('"') and value_str.endswith('"')) or \
       (value_str.startswith("'") and value_str.endswith("'")):
        try:
            return ast.literal_eval(value_str)
        except (ValueError, SyntaxError):
            # LLM 长文本可能在引号内换行（ast.literal_eval 不允许裸换行）
            # 将实际换行替换为 \n 转义序列后重试
            try:
                sanitized = value_str.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\n')
                return ast.literal_eval(sanitized)
            except (ValueError, SyntaxError):
                return value_str[1:-1]

    # 布尔值
    if value_str.lower() == 'true':
        return True
    if value_str.lower() == 'false':
        return False

    # None
    if value_str.lower() == 'none' or value_str.lower() == 'null':
        return None

    # 数字
    try:
        if '.' in value_str:
            return float(value_str)
        return int(value_str)
    except ValueError:
        pass

    # 无引号字符串（原样返回）
    return value_str


def parse_positional_args(params_text: str) -> List[Any]:
    """
    解析纯位置参数列表（无 key= 前缀的值）。

    与 parse_params_from_call 互补：那个只处理 key=value，这个处理纯值。
    复用 _split_params（逗号分割，尊重引号和括号）和 _parse_value。

    Args:
        params_text: 括号内的参数文本

    Returns:
        解析后的值列表，如 ["May 1 news", 10]
    """
    if not params_text:
        return []
    parts = _split_params(params_text)
    return [_parse_value(part.strip()) for part in parts if part.strip()]


def validate_params(
    params: dict, param_schema: dict
) -> Tuple[bool, str]:
    """
    校验解析出的参数：参数名是否合法、必要参数是否齐全。

    Args:
        params: 解析出的参数字典
        param_schema: action 的参数 schema（{name: {required: bool, ...}, ...}）

    Returns:
        (is_valid, error_message)
    """
    if not param_schema:
        return True, ""

    # 检查未知参数名
    unknown = [k for k in params if k not in param_schema]
    if unknown:
        return False, f"未知参数: {unknown}，可用参数: {list(param_schema.keys())}"

    # 检查必要参数
    required = [
        name for name, meta in param_schema.items()
        if isinstance(meta, dict) and meta.get("required", False)
    ]
    missing = [name for name in required if name not in params]
    if missing:
        return False, f"缺少必要参数: {missing}"

    return True, ""


# ==================== Prompt Builders ====================


def build_exit_verification_prompt(raw_reply: str) -> str:
    """构建退出验证 prompt"""
    return f"""以下是大模型Agent对用户的回答，判断它的意思是（1）决定了做什么新动作（接下来要做）。（2）没有决定做什么

文本：
```
{raw_reply}
```

你需要作出的回答：
- YES: 表示"已经决定了做什么，接下来要做“
- NO: 表示没有决定做什么

只回答 YES 或 NO。
注意，如果是询问用户是否要做什么，或者表达了"我可以做什么"、"我能帮你做什么"、"你需要我做什么"这样的意思，请回答 NO，因为这说明它在在询问用户建议用户，并非他的决定"""


def build_no_action_reflect_message(
    action_section_text: str,
    raw_reply: str,
    action_registry_flat: dict,
) -> Optional[str]:
    """
    检查是否有疑似幻觉的函数调用 pattern，构造 reflect 消息。

    如果文本匹配 func_name(...) 或 func.name(...) 格式，
    但没有匹配到任何注册的 action，说明 LLM 幻觉了函数名。

    同时检查 raw_reply：当 <action_script> 块为空但 raw_reply 中包含 JSON/XML action 格式
    或函数调用 pattern 时，说明 LLM 试图输出 action 但格式不对。

    Args:
        action_section_text: <action_script> 块内的文本
        raw_reply: LLM 的完整原始回复
        action_registry_flat: action_registry["_flat"] 字典

    Returns:
        reflect 消息字符串，如果没有疑似幻觉则返回 None
    """
    if not action_section_text or not action_section_text.strip():
        # <action_script> 块为空，但检查 raw_reply 中是否有疑似 action 的内容
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
                return "没有发现要执行的action。如果要执行action，需要使用 <action_script> 块格式来声明。确认没什么要执行的可以回复'确定'。"

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

    invalid_list = ", ".join(invalid_names)
    hint = f"没有发现要执行的action。你使用了未注册的名称：{invalid_list}。请检查action名称是否正确。确认没什么要执行的可以回复'确定'。"
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
