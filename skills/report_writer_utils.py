PERSONA_DESIGNER="""
    你是一个见多识广的跨领域专家。现在公司打算编写一个研究报告（主题是关于：{{main_subject}}),主要目的包括：{{main_purpose}}。
    现在我们需要雇佣一个最适合的专家来主持完成这项工作，你来负责考虑一下应该选择什么样的专家，需要具备什么样的
    能力特质和工作习惯。写一个简短的人员需求。我们会把这个内容作为招聘广告的一部份。必须用第二人称的方式来描述需求，仿佛直接对潜在应聘者说话，用“你是”开头，用“。”结尾，不要使用“我们”。
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
import os

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
import fitz  # PyMuPDF，用于获取PDF信息和提取页面
import tempfile



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




def pdf_to_markdown(pdf_path, start_page=None, end_page=None, lang=None):
    """
    将PDF的指定页范围转换为Markdown格式

    参数:
        pdf_path (str): PDF文件路径
        start_page (int, optional): 起始页码（从1开始），默认None表示从第1页开始
        end_page (int, optional): 结束页码，默认None表示到最后页
        lang (str, optional): 语言代码，如'zh'、'en'等，默认None使用自动检测

    返回:
        str: 转换后的Markdown文本
    """
    
    # 获取PDF总页数
    with fitz.open(pdf_path) as doc:
        total_pages = len(doc)
    
    # 确定页面范围
    if start_page is None:
        start_page = 1
    if end_page is None:
        end_page = total_pages
    
    # 验证页面范围
    start_page = max(1, start_page)
    end_page = min(total_pages, end_page)
    
    if start_page > end_page:
        raise ValueError(f"起始页({start_page})不能大于结束页({end_page})")
    
    print(f"PDF总页数: {total_pages}")
    print(f"转换页范围: {start_page}-{end_page}")
    
    # 如果只需要部分页面，创建临时PDF文件
    if start_page > 1 or end_page < total_pages:
        print(f"提取页面 {start_page}-{end_page}...")
        temp_pdf_path = extract_pages(pdf_path, start_page, end_page)
        pdf_to_convert = temp_pdf_path
    else:
        pdf_to_convert = pdf_path
    
    # 初始化marker模型和转换器
    try:
        # 加载模型
        print("加载marker模型...")

        # 创建PDF转换器（使用新的API）
        converter = PdfConverter(
            artifact_dict=create_model_dict(),
        )

        # 执行转换
        print("正在转换PDF到Markdown...")
        rendered = converter(pdf_to_convert)

        # 从渲染结果中提取文本
        text, _, images = text_from_rendered(rendered)

        print(f"转换完成! 共 {len(text)} 个字符")

        # 清理临时文件（如果存在）
        if 'temp_pdf_path' in locals():
            os.unlink(temp_pdf_path)

        return text
    
    except Exception as e:
        print(f"转换过程中发生错误: {e}")
        # 确保清理临时文件
        if 'temp_pdf_path' in locals():
            os.unlink(temp_pdf_path)
        raise




def extract_pages(pdf_path, start_page, end_page):
    """
    提取PDF的指定页面范围到临时文件
    
    参数:
        pdf_path (str): 原始PDF文件路径
        start_page (int): 起始页码（从1开始）
        end_page (int): 结束页码
    
    返回:
        str: 临时PDF文件路径
    """
    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    temp_pdf_path = os.path.join(temp_dir, "temp_pages.pdf")
    
    # 打开原始PDF
    doc = fitz.open(pdf_path)
    
    # 创建新PDF
    new_doc = fitz.open()
    
    # 提取指定页面（注意：fitz的页面索引从0开始）
    for page_num in range(start_page - 1, end_page):
        new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
    
    # 保存临时PDF
    new_doc.save(temp_pdf_path)
    new_doc.close()
    doc.close()
    
    return temp_pdf_path
def batch_convert_pdfs(pdf_folder, start_page=None, end_page=None, output_dir=None, lang=None):
    """
    批量转换文件夹中的所有PDF文件

    参数:
        pdf_folder (str): 包含PDF文件的文件夹路径
        start_page (int, optional): 起始页码
        end_page (int, optional): 结束页码
        output_dir (str, optional): 输出目录
        lang (str, optional): 语言代码
    """
    if not os.path.exists(pdf_folder):
        print(f"文件夹不存在: {pdf_folder}")
        return

    if output_dir is None:
        output_dir = os.path.join(pdf_folder, "markdown_output")

    os.makedirs(output_dir, exist_ok=True)

    # 获取所有PDF文件
    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith('.pdf')]

    if not pdf_files:
        print(f"在 {pdf_folder} 中未找到PDF文件")
        return

    print(f"找到 {len(pdf_files)} 个PDF文件，开始批量转换...")

    success_count = 0
    for pdf_file in pdf_files:
        try:
            pdf_path = os.path.join(pdf_folder, pdf_file)
            print(f"\n处理: {pdf_file}")

            # 调用 pdf_to_markdown 获取文本
            markdown_text = pdf_to_markdown(
                pdf_path=pdf_path,
                start_page=start_page,
                end_page=end_page,
                lang=lang
            )

            # 手动保存到文件
            base_name = os.path.splitext(pdf_file)[0]
            if start_page or end_page:
                page_info = f"_pages_{start_page or 1}-{end_page or 'all'}"
                output_filename = f"{base_name}{page_info}.md"
            else:
                output_filename = f"{base_name}.md"

            output_path = os.path.join(output_dir, output_filename)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_text)

            print(f"  ✅ 已保存: {output_path}")
            success_count += 1

        except Exception as e:
            print(f"  ❌ 转换失败: {e}")

    print(f"\n批量转换完成! 成功: {success_count}/{len(pdf_files)}")

if __name__ == '__main__':
    # ==================== 使用示例 ====================
    
    # 定义你的 PDF 文件路径和输出目录
    my_pdf = 'path/to/your/document.pdf'
    output_directory = 'output_markdown'
    
    # 检查示例文件是否存在
    if not Path(my_pdf).exists():
        print(f"错误：示例文件 '{my_pdf}' 不存在，请修改路径后重试。")
    else:
        # 示例1：转换整个 PDF 文档
        print("--- 任务1: 转换整个 PDF ---")
        convert_pdf_to_markdown(my_pdf, output_directory)
        
        # 示例2：只转换 PDF 的第 2 到 3 页
        print("\n--- 任务2: 转换 PDF 的第 2-3 页 ---")
        convert_pdf_to_markdown(my_pdf, output_directory, start_page=2, end_page=3)

        # 示例3：只转换第 5 页
        print("\n--- 任务3: 只转换 PDF 的第 5 页 ---")
        convert_pdf_to_markdown(my_pdf, output_directory, start_page=5, end_page=5)