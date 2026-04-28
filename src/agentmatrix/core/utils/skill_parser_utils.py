"""
通用的 LLM 输出解析工具
包含可复用的 parser 函数，用于 think_with_retry
"""

import json
import re
from typing import Any, Dict, List


# ==========================================
# JSON 解析工具
# ==========================================


def extract_json(raw_reply: str):
    """
    从 LLM 输出中提取 JSON 对象

    自动处理 markdown code block 包裹。
    返回 (data_dict, error_feedback_str)，成功时 error 为 None。
    """
    json_str = raw_reply.strip()

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
        return None, f"无效的 JSON 格式：{str(e)}。请输出纯 JSON。"

    if not isinstance(data, dict):
        return None, "输出必须是一个 JSON 对象"

    return data, None


def validate_json_fields(data: dict, required: dict) -> str | None:
    """
    校验 JSON 字段类型

    required 格式：{"field_name": (type_or_types, "error message")}
    例：{"duplicate": (bool, "'duplicate' 必须是 true/false")}

    返回 None 表示通过，否则返回错误 feedback 字符串。
    """
    for field_name, (expected_type, error_msg) in required.items():
        if field_name not in data:
            return f"JSON 必须包含 '{field_name}' 字段"
        value = data[field_name]
        if expected_type is not None and not isinstance(value, expected_type):
            return error_msg
    return None


def multi_section_parser(
    raw_reply: str,
    section_headers: List[str] = None,
    regex_mode: bool = False,
    match_mode: str = "ALL",
    return_list: bool = False,
    allow_empty: bool = False
) -> dict:
    """
    多 section 文本解析器，根据指定的 section headers 提取多个 section 的内容。

    支持两种模式：
    1. 多 section 模式：section_headers 为字符串列表
       - 根据提供的 section headers 识别多个 section
       - 如果一行完全等于某个 header（regex_mode=False）或匹配某个正则表达式（regex_mode=True），则该行是 section header
       - 返回 {"status": "...", "content": {"header1": "content1", ...}}

    2. 单 section 模式：section_headers 为 None 或空列表
       - 自动查找形如 "=====" 或 "=====text=====" 的分隔行
       - 返回 {"status": "...", "content": "..."}

    Args:
        raw_reply: LLM 返回的原始回复
        section_headers: 可选的 section header 列表
                         - 如果为 None 或空列表：使用单 section 模式，自动查找 "=====" 分隔符
                         - 如果是字符串列表：使用多 section 模式，按 headers 切分内容
        regex_mode: 匹配模式开关（仅对多 section 模式有效）
                   - False（默认）：精确匹配，一行必须完全等于某个 header
                   - True：正则表达式匹配，使用 re.match() 进行模式匹配
        match_mode: 匹配完整性要求（仅对多 section 模式有效）
                   - "ALL"（默认）：所有指定的 section headers 都必须存在，否则返回错误
                   - "ANY"：只要匹配到即可，有多少匹配就返回多少 sections
        return_list: 是否将内容拆分为行列表（默认 False）
                   - False：返回字符串（默认行为）
                   - True：返回行列表 [line.strip() for line in content.split('\n') if line.strip()]
        allow_empty: 是否允许空的 section 内容（默认 False）
                   - False（默认）：如果 section 内容为空，返回错误
                   - True：允许空的 section 内容

    Returns:
        单 section 模式：
        {
            "status": "success" | "error",
            "content": 提取的内容 (成功时),
            "feedback": 错误信息 (失败时)
        }

        多 section 模式：
        {
            "status": "success" | "error",
            "content": {section_name: content, ...} (成功时),
            "feedback": 错误信息 (失败时)
        }

    Example:
        >>> # 精确匹配模式（默认）- ALL 模式
        >>> text = '''
        ... [研究计划]
        ... 研究计划内容
        ... [章节大纲]
        ... # 章节1
        ... '''
        >>> result = multi_section_parser(
        ...     text,
        ...     section_headers=['[研究计划]', '[章节大纲]'],
        ...     match_mode="ALL"
        ... )
        >>> # 如果缺少任何一个 header，返回 error

        >>> # ANY 模式
        >>> result = multi_section_parser(
        ...     text,
        ...     section_headers=['[研究计划]', '[章节大纲]', '[关键问题]'],
        ...     match_mode="ANY"
        ... )
        >>> # 只返回找到的 [研究计划] 和 [章节大纲]，不报错
    """
    # 内部辅助函数：后处理 section 内容
    def _post_process(content: str):
        """根据参数处理内容"""
        # 如果不允许空且内容为空
        if not allow_empty and not content.strip():
            return None  # 标记为无效

        # 如果需要返回列表
        if return_list:
            return [line.strip() for line in content.split('\n') if line.strip()]

        # 否则返回字符串
        return content.strip()

    try:
        if not raw_reply or not isinstance(raw_reply, str):
            return {"status": "error", "feedback": "输入内容无效"}

        lines = raw_reply.split('\n')

        # ========== 模式1: 多 section 解析（优化版：倒序遍历 + 提前终止）==========
        if section_headers and isinstance(section_headers, list) and len(section_headers) > 0:

            # ========== 优化1: ALL 模式的快速预检查 ==========
            # 使用 C 语言的 in 操作快速检查所有 headers 是否存在
            if match_mode == "ALL" and not regex_mode:
                missing = [h for h in section_headers if h not in raw_reply]
                if missing:
                    # 🔥 Feedback 应该是格式强调，而不是错误描述
                    headers_str = "、".join(missing)
                    return {"status": "error",
                           "feedback": f"【必须包含】输出必须包含以下 section：{headers_str}\n请确保每个 section 都有明确的标题，格式如：{missing[0]}"}

            # ========== 优化2: 倒序遍历 + 提前终止 ==========
            sections = {}
            needed = set(section_headers)  # 用于快速查找
            found = set()  # 记录已找到的 headers

            i = len(lines) - 1
            last_section_end = len(lines)  # 记录当前 section 的结束位置

            while i >= 0:
                line = lines[i].strip()

                # 检查是否是 section header
                is_header = False
                if regex_mode:
                    # 正则表达式模式
                    for pattern in section_headers:
                        if re.match(pattern, line):
                            is_header = True
                            break
                else:
                    # 精确匹配模式（默认）
                    is_header = line in section_headers

                # 找到一个新的 section header（且未记录过）
                if is_header and line not in found:
                    # 提取 section 内容：从 i+1 到 last_section_end
                    raw_content = '\n'.join(lines[i + 1:last_section_end])
                    processed_content = _post_process(raw_content)

                    # 如果处理后的内容为 None（不允许空），返回错误
                    if processed_content is None:
                        return {"status": "error",
                               "feedback": f"Section '{line}' 的内容为空"}

                    sections[line] = processed_content
                    found.add(line)

                    # 更新下一个 section 的结束位置
                    last_section_end = i

                    # ========== 优化3: 提前终止 ==========
                    if found == needed:
                        # ALL 模式：找到所有需要的 headers，提前返回
                        break


                i -= 1

            # ========== 验证结果 ==========
            if not sections:
                mode_desc = "正则表达式" if regex_mode else "精确匹配"
                headers_str = "、".join(section_headers)
                return {"status": "error",
                       "feedback": f"【必须包含】输出必须包含以下 section：{headers_str}\n请确保每个 section 都有明确的标题"}

            if match_mode == "ALL" and not regex_mode:
                # 精确模式：再次验证（in 操作可能误报，比如在注释中）
                missing = [h for h in section_headers if h not in sections]
                if missing:
                    headers_str = "、".join(missing)
                    return {"status": "error",
                           "feedback": f"【必须包含】输出必须包含以下 section：{headers_str}\n请确保每个 section 都有明确的标题，格式如：{missing[0]}"}

            if match_mode == "ALL" and regex_mode:
                # 正则模式：检查每个正则是否至少匹配到一个 header
                for pattern in section_headers:
                    pattern_matched = any(re.match(pattern, h) for h in sections.keys())
                    if not pattern_matched:
                        return {"status": "error",
                               "feedback": f"【必须包含】输出必须包含匹配 '{pattern}' 的 section 标题"}

            return {"status": "success", "content": sections}

        # ========== 模式2: 单 section 解析（向后兼容）==========
        else:
            # 匹配模式: 开头至少2个=，结尾至少2个=，中间可有任意内容
            pattern = r'^={2,}.*={2,}$'
            divider_line_idx = None

            # 查找最后一个匹配的分隔行
            for idx in range(len(lines) - 1, -1, -1):  # 从后往前遍历
                if re.match(pattern, lines[idx].strip()):
                    divider_line_idx = idx
                    break

            if divider_line_idx is None:
                return {"status": "error",
                       "feedback": "【格式要求】输出必须包含分隔行，格式如：======"}

            # 提取最后一个分隔行之后的所有内容
            raw_content = '\n'.join(lines[divider_line_idx + 1:])
            processed_content = _post_process(raw_content)

            # 如果处理后的内容为 None（不允许空），返回错误
            if processed_content is None:
                return {"status": "error",
                       "feedback": "【格式要求】分隔符后必须有内容"}

            return {"status": "success", "content": processed_content}

    except Exception as e:
        return {"status": "error", "feedback": f"解析失败: {str(e)}"}


def simple_section_parser(raw_reply: str, section_header: str = None) -> dict:
    """
    通用文本解析器，根据分隔符提取内容（单section模式）。

    这是 multi_section_parser 的简化版，用于只需要提取一个section的场景。

    Args:
        raw_reply: LLM 返回的原始回复
        section_header: 可选分隔符/section标题。如果为 None，则自动查找形如 "=====" 或 "=====text=====" 的分隔行
                       分隔行前后都至少需要2个等号

    Returns:
        {
            "status": "success" | "error",
            "content": 提取的内容 (成功时，**直接是字符串**),
            "feedback": 错误信息 (失败时)
        }

    Example:
        >>> text = '''
        ... 一些介绍文本...
        ... ============
        ... 要提取的内容
        ... 更多内容...
        ... ============
        ... '''
        >>> result = simple_section_parser(text)
        >>> # 返回: {"status": "success", "content": "要提取的内容\\n\\n更多内容..."}

        >>> # 带section_header的情况
        >>> text2 = '''
        ... 思考过程...
        ... [新草稿]
        ... 实际内容
        ... '''
        >>> result2 = simple_section_parser(text2, section_header="[新草稿]")
        >>> # 返回: {"status": "success", "content": "实际内容"} （字符串，不是字典！）
    """
    if section_header:
        # 使用多section模式，但提取单个section的内容
        result = multi_section_parser(raw_reply, section_headers=[section_header])

        if result["status"] == "success":
            # 从字典中提取实际内容，返回字符串而不是字典
            content_dict = result["content"]
            if isinstance(content_dict, dict) and section_header in content_dict:
                return {"status": "success", "content": content_dict[section_header]}
            else:
                return {"status": "error", "feedback": f"未找到section: {section_header}"}

        return result
    else:
        # 没有section_header，使用单section模式（自动查找分隔符）
        return multi_section_parser(raw_reply, section_headers=None)
