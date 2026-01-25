"""
通用的 LLM 输出解析工具
包含可复用的 parser 函数，用于 think_with_retry
"""

import re
from typing import Any, Dict, List


def multi_section_parser(
    raw_reply: str,
    section_headers: List[str] = None,
    regex_mode: bool = False,
    match_mode: str = "ALL"
) -> dict:
    """
    多 section 文本解析器，根据指定的 section headers 提取多个 section 的内容。

    支持两种模式：
    1. 多 section 模式：section_headers 为字符串列表
       - 根据提供的 section headers 识别多个 section
       - 如果一行完全等于某个 header（regex_mode=False）或匹配某个正则表达式（regex_mode=True），则该行是 section header
       - 返回 {"status": "...", "sections": {"header1": "content1", ...}}

    2. 单 section 模式（向后兼容）：section_headers 为 None 或空列表
       - 自动查找形如 "=====" 或 "=====text=====" 的分隔行
       - 返回 {"status": "...", "data": "..."}

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

    Returns:
        单 section 模式：
        {
            "status": "success" | "error",
            "data": 提取的内容 (成功时),
            "feedback": 错误信息 (失败时)
        }

        多 section 模式：
        {
            "status": "success" | "error",
            "sections": {section_name: content, ...} (成功时),
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
                    return {"status": "error",
                           "feedback": f"ALL 模式：缺少以下 section headers: {missing}"}

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
                    # 使用 join 拼装（已经 split 了，join 是最优选择）
                    section_content = '\n'.join(lines[i + 1:last_section_end]).strip()
                    sections[line] = section_content
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
                return {"status": "error",
                       "feedback": f"未找到任何指定的 section header ({mode_desc}模式): {section_headers}"}

            if match_mode == "ALL" and not regex_mode:
                # 精确模式：再次验证（in 操作可能误报，比如在注释中）
                missing = [h for h in section_headers if h not in sections]
                if missing:
                    return {"status": "error",
                           "feedback": f"ALL 模式：缺少以下 section headers: {missing}。找到的 sections: {list(sections.keys())}"}

            if match_mode == "ALL" and regex_mode:
                # 正则模式：检查每个正则是否至少匹配到一个 header
                for pattern in section_headers:
                    pattern_matched = any(re.match(pattern, h) for h in sections.keys())
                    if not pattern_matched:
                        return {"status": "error",
                               "feedback": f"ALL 模式：未找到匹配正则表达式 '{pattern}' 的 section header。找到的 sections: {list(sections.keys())}"}

            return {"status": "success", "sections": sections}

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
                return {"status": "error", "feedback": "未找到有效的分隔行，请确保输出格式正确"}

            # 提取最后一个分隔行之后的所有内容
            content = '\n'.join(lines[divider_line_idx + 1:]).strip()

            if not content:
                return {"status": "error", "feedback": "分隔符后没有内容"}

            return {"status": "success", "data": content}

    except Exception as e:
        return {"status": "error", "feedback": f"解析失败: {str(e)}"}
