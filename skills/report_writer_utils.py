PERSONA_DESIGNER="""
    你是一个见多识广的跨领域专家。现在公司打算编写一个研究报告（主题是关于：{{main_subject}}),主要目的包括：{{main_purpose}}。
    现在我们需要雇佣一个最适合的专家来主持完成这项工作，你来负责考虑一下应该选择什么样的专家，需要具备什么样的
    能力特质和工作习惯。我们会把你的建议作为招聘广告的一部份，用第二人称的方式来描述需求。请用“你是”开头，用“。”结尾，不要使用“我们”。
"""

BLUEPRINT_DESIGNER="""
    {{persona}}

    现在的任务是根据用户要求设计一个全面的 "Research Blueprint"。

    这份蓝图**并非最终报告**，而将作为自动化AI执行器（"执行者"）的严格操作手册。该执行器将阅读数百份多语言文件，并逐步完成报告的撰写。

    您的输出必须结构清晰、表述精确，并严格遵循信息提取与整合的导向原则。

    **核心理念**：

    1. **结构即检索指令**：蓝图中每个章节本质上都是为执行器设定的"检索指令"或"信息容器"，用于归集相关事实依据。2. **逻辑流设计**：章节排列必须构成连贯的论述脉络（例如：背景→问题→分析→解决方案→结论）。
    3. **语言无关性**：尽管源文件可能包含英语、日语等多语种内容，但蓝图本身必须以简体中文撰写，以确保最终报告的中文语言属性。

    **蓝图输出结构**：
    Research Blueprint 应该输出如下的Markdown结构，最后一个`特别提示`是可选的，其他章节必须要有：
    ```
    # 研究目标

        简要的研究目标描述。

    # 核心问题

        研究的核心问题或假设清单

    # 章节结构大纲

        根据研究目标，预设一个章节结构，包括具体的标题。

    # 特别提示

        可选，适合本研究目的的方法指引或者特别需要注意的点，不要写常识性内容
    ```
    """

BLUEPRINT_USER="""


"""

import re
from typing import Optional, Dict, List, Union


def markdown_to_json(text: str) -> Optional[Dict[str, Union[str, List[Dict]]]]:
    """
    将 Markdown 文本转换为 JSON 结构，按 # section 标题组织。

    参数:
        text: 输入的文本

    返回:
        dict: 解析后的 JSON 结构
        - 一级标题作为 key
        - 如果内容包含多个二级标题，value 是 list
        - 其他情况 value 是字符串（原样保留内容）
        如果解析失败或找不到 markdown 内容，返回 None
    """
    if not text or not isinstance(text, str):
        return None

    try:
        # 1. 截取符合 markdown 语法的部分（从第一个标题开始）
        match = re.search(r'^#+\s', text, re.MULTILINE)
        if not match:
            return None

        markdown_text = text[match.start():]

        # 2. 解析 markdown 标题和内容
        result = {}
        lines = markdown_text.split('\n')

        current_section = None
        current_content_lines = []
        subsections = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # 检查是否是标题
            header_match = re.match(r'^(#+)\s+(.+)$', line)
            if header_match:
                level = len(header_match.group(1))
                title = header_match.group(2).strip()

                if level == 1:
                    # 一级标题：保存前一个 section
                    if current_section:
                        if subsections:
                            # 如果有二级标题，使用 list
                            result[current_section] = subsections
                        else:
                            # 否则使用字符串内容
                            content = '\n'.join(current_content_lines).strip()
                            result[current_section] = content

                    # 开始新的 section
                    current_section = title
                    current_content_lines = []
                    subsections = []

                elif level == 2:
                    # 二级标题：先保存之前的普通内容
                    if current_content_lines:
                        content = '\n'.join(current_content_lines).strip()
                        if content and subsections:
                            # 如果 subsections 中最后一个条目没有 content，则添加
                            if subsections and 'content' not in subsections[-1]:
                                subsections[-1]['content'] = content
                            else:
                                subsections.append({'content': content})
                        current_content_lines = []

                    # 添加新的 subsection
                    subsections.append({title: []})

            else:
                # 普通内容行
                if subsections:
                    # 如果有 subsections，添加到最后一个 subsection 的内容中
                    last_subsection = subsections[-1]
                    # 找到 subsection 中的 key（标题）
                    subsection_key = [k for k in last_subsection.keys() if k != 'content'][0]
                    if isinstance(last_subsection[subsection_key], list):
                        last_subsection[subsection_key].append(line)
                    else:
                        # 如果已经不是 list 了，说明之前有普通内容，需要转换
                        last_subsection[subsection_key] = [last_subsection[subsection_key], line]
                else:
                    current_content_lines.append(line)

            i += 1

        # 3. 保存最后一个 section
        if current_section:
            if subsections:
                # 合并 subsections 中的 list 内容为字符串
                processed_subsections = []
                for subsection in subsections:
                    processed = {}
                    for key, value in subsection.items():
                        if isinstance(value, list):
                            processed[key] = '\n'.join(value).strip()
                        else:
                            processed[key] = value
                    if processed:  # 只添加非空的 subsection
                        processed_subsections.append(processed)

                # 处理剩余的普通内容
                if current_content_lines:
                    content = '\n'.join(current_content_lines).strip()
                    if content:
                        processed_subsections.append({'content': content})

                result[current_section] = processed_subsections if processed_subsections else []
            else:
                content = '\n'.join(current_content_lines).strip()
                result[current_section] = content

        return result if result else None

    except Exception:
        # 解析失败返回 None
        return None
