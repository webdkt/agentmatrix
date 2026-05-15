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
    解析退出验证的三分类响应：code / intent / other

    Parser Contract for think_with_retry:
    - Returns {"status": "success", "content": dict} on success
    - Returns {"status": "error", "feedback": str} on error

    Args:
        raw_reply: LLM 的原始输出

    Returns:
        dict: {"result": "code"|"intent"|"other"}
              - code: LLM 输出了调用工具的代码，格式可能有误
              - intent: LLM 表达了操作意图但没有给出具体命令
              - other: 都不是，确认可以退出
    """
    cleaned = raw_reply.strip()

    has_1 = bool(re.search(r'\b1\b', cleaned))
    has_2 = bool(re.search(r'\b2\b', cleaned))
    has_3 = bool(re.search(r'\b3\b', cleaned))

    if has_1 and not has_2 and not has_3:
        return {"status": "success", "content": {"result": "code"}}
    elif has_2 and not has_1 and not has_3:
        return {"status": "success", "content": {"result": "intent"}}
    elif has_3 and not has_1 and not has_2:
        return {"status": "success", "content": {"result": "other"}}
    else:
        return {"status": "error", "feedback": "请只回答 1、2 或 3"}


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

    # 跟踪已消费的字符范围，避免将函数参数内部的代码误识别为 action
    # 例如 file.write(content=r"""...os.makedirs(...)...""") 不应把 os.makedirs 当成独立 action
    consumed_end = 0

    for match in func_pattern.finditer(text):
        # 跳过落在已消费范围内的匹配（属于某个上层函数调用的参数内容）
        if match.start() < consumed_end:
            continue

        func_name = match.group(1).lower()
        start_paren = match.end() - 1  # '(' 的位置

        # 括号配对，支持多行和嵌套（通过 _skip_string_literal 跳过字符串）
        depth = 1
        pos = start_paren + 1
        while pos < len(text) and depth > 0:
            ch = text[pos]
            if ch in ('"', "'") or (ch in ('r', 'b', 'f', 'R', 'B', 'F') and pos + 1 < len(text) and text[pos + 1] in ('"', "'")):
                pos = _skip_string_literal(text, pos)
                continue
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            pos += 1

        if depth != 0:
            # 括号未闭合，跳过
            continue

        # 标记消费范围：从本调用的开头到闭合括号
        consumed_end = pos

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


def _skip_string_literal(text: str, i: int) -> int:
    """
    如果 text[i] 位于字符串字面量起始处，跳过整个字符串并返回结束位置。
    如果不是字符串起始，返回 i 原值。

    支持所有 Python 字符串形式：
    - 单引号、双引号
    - 三引号（三个连续相同引号字符）
    - r/b/f 前缀
    正确处理转义序列（反斜杠）。
    """
    if i >= len(text):
        return i

    # 跳过原始前缀 r/b/f
    start = i
    if text[i] in ('r', 'b', 'f', 'R', 'B', 'F') and i + 1 < len(text) and text[i + 1] in ('"', "'"):
        i += 1

    ch = text[i]
    if ch not in ('"', "'"):
        return start  # 不是字符串

    # 检测三引号
    is_triple = (i + 2 < len(text) and text[i + 1] == ch and text[i + 2] == ch)

    if is_triple:
        close_seq = ch * 3
        j = i + 3
        escape = False
        while j <= len(text) - 3:
            if escape:
                escape = False
                j += 1
                continue
            if text[j] == '\\':
                escape = True
                j += 1
                continue
            if text[j:j + 3] == close_seq:
                return j + 3
            j += 1
        return len(text)  # 未闭合 → 跳到末尾
    else:
        j = i + 1
        escape = False
        while j < len(text):
            if escape:
                escape = False
                j += 1
                continue
            if text[j] == '\\':
                escape = True
                j += 1
                continue
            if text[j] == ch:
                return j + 1
            j += 1
        return len(text)  # 未闭合 → 跳到末尾


def _split_params(text: str) -> List[str]:
    """按逗号分割参数，忽略引号内和嵌套 ()/{}/[] 内的逗号。

    通过 _skip_string_literal 跳过所有字符串字面量（含三引号），
    确保字符串内部的逗号和括号不影响分割。
    """
    parts = []
    segment_start = 0
    depth = 0
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # 遇到引号 → 跳过整个字符串字面量
        if ch in ('"', "'") or (ch in ('r', 'b', 'f', 'R', 'B', 'F') and i + 1 < n and text[i + 1] in ('"', "'")):
            i = _skip_string_literal(text, i)
            continue

        if ch in ('(', '{', '['):
            depth += 1
        elif ch in (')', '}', ']'):
            depth -= 1
        elif ch == ',' and depth == 0:
            parts.append(text[segment_start:i])
            segment_start = i + 1

        i += 1

    parts.append(text[segment_start:])
    return parts


def _parse_value(value_str: str) -> Any:
    """解析单个参数值字符串为 Python 值。"""
    import ast

    # 去掉首尾空白
    value_str = value_str.strip()

    # 空字符串
    if not value_str:
        return ""

    # 原始字符串：r"""...""" / r'''...''' — 内部内容原样保留，不解释转义
    if value_str.startswith('r"""') and value_str.endswith('"""'):
        return value_str[4:-3]
    if value_str.startswith("r'''") and value_str.endswith("'''"):
        return value_str[4:-3]

    # 三引号字符串：'''...''' / """..."""
    # 必须在单引号检查之前，否则 startswith("'") 会误匹配
    if ((value_str.startswith("'''") and value_str.endswith("'''") and len(value_str) >= 6)
        or (value_str.startswith('"""') and value_str.endswith('"""') and len(value_str) >= 6)):
        try:
            return ast.literal_eval(value_str)
        except (ValueError, SyntaxError):
            # ast 解析失败（含非法转义等），直接剥掉三引号返回原样内容
            return value_str[3:-3]

    # 带引号字符串：用 ast.literal_eval 解释转义序列（\n → 换行等）
    if (value_str.startswith('"') and value_str.endswith('"')) or \
       (value_str.startswith("'") and value_str.endswith("'")):
        try:
            return ast.literal_eval(value_str)
        except (ValueError, SyntaxError):
            # ast.literal_eval 失败（通常因为裸换行），直接手动去引号保留原始内容
            inner = value_str[1:-1]
            inner = inner.replace('\\"', '"').replace("\\'", "'")
            inner = inner.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
            inner = inner.replace('\\\\', '\\')
            return inner

    # dict/list 字面量：先尝试 ast.literal_eval，再尝试 json.loads
    if value_str.startswith('{') or value_str.startswith('['):
        try:
            return ast.literal_eval(value_str)
        except (ValueError, SyntaxError):
            try:
                import json
                return json.loads(value_str)
            except (ValueError, SyntaxError):
                pass

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
    """构建退出验证 prompt：判断 LLM 输出是否包含未正确格式化的工具调用意图"""
    return f"""以下是 Agent 的一段输出文本, 请判断它属于哪种情况:

1. 试图调用工具操作的代码
2. 准备做某个操作但没有给出具体命令: 文本表达了要做某事的意图, 但没有给出具体的工具调用代码(比如"我来查一下"、"让我执行xx"、"接下来我会..."等)
3. 其他: 以上都不是, 比如纯文字回答、总结、询问用户、解释说明、确认完成等。如果文本是问一个问题，就肯定属于这个类别

文本:
```
{raw_reply}
```

只回答 1、2 或 3。"""


def build_no_action_reflect_message(
    action_section_text: str,
    raw_reply: str,
    action_registry_flat: dict,
) -> Optional[str]:
    """
    检查 action_script 块内是否有幻觉的函数调用名称。

    仅在 action_script 块有内容时检查（路径 A）：
    如果文本匹配 func_name(...) 格式但不在注册的 action 中，说明 LLM 幻觉了函数名。
    块为空时不做检查（交给退出验证的 LLM 判断）。

    Args:
        action_section_text: <action_script> 块内的文本
        raw_reply: LLM 的完整原始回复（未使用，保留参数兼容性）
        action_registry_flat: action_registry["_flat"] 字典

    Returns:
        reflect 消息字符串，如果没有疑似幻觉则返回 None
    """
    if not action_section_text or not action_section_text.strip():
        return None

    # 匹配 func_name(...) 或 func.name(...) 格式
    call_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\s*\('
    matches = re.findall(call_pattern, action_section_text)

    if not matches:
        return None

    # 找到不在 registry 中的函数名
    invalid_names = []
    for name in matches:
        name_lower = name.lower()
        if name_lower not in action_registry_flat:
            invalid_names.append(name)

    if not invalid_names:
        return None

    invalid_list = ", ".join(invalid_names)
    return f"没有发现要执行的action。你使用了未注册的名称：{invalid_list}。请检查action名称是否正确。确认没什么要执行的可以回复'确定'。"
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

    # 过滤：只保留 body 长度 > 10 或有附件的邮件
    filtered = [
        e for e in emails
        if len(e.body.strip()) > 10 or e.attachments
    ]

    # 最多保留最近 50 条
    max_emails = 50
    skipped = 0
    if len(filtered) > max_emails:
        skipped = len(filtered) - max_emails
        filtered = filtered[-max_emails:]

    if not filtered:
        return "[EMAIL HISTORY]\n暂无邮件历史\n"

    lines = ["[EMAIL HISTORY]"]
    lines.append("注：你发出的邮件会用 `-> 收件人名字` 的方式标出")
    if skipped > 0:
        lines.append(f"（还有 {skipped} 封旧邮件未加载）")

    today = datetime.now().date()

    for email in filtered:
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
