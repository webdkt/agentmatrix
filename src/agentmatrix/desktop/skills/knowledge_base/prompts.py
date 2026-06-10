"""
Knowledge Base — LLM Prompt 模板
"""


class KnowledgePrompts:

    SCHEMA_GENERATION_PROMPT = """\
你是一个知识库架构师。用户要创建一个新知识库，请根据以下描述生成初始 Schema。

【知识库名称】
{name}

【用户描述】
{description}

Schema 只包含三个部分：

1. 关注的信息类型
   每个类型有：
   - 名称：类型标识
   - 描述：什么属于这个类型
   - 关注维度：提取这个类型时应该注意什么

2. 类型之间的关系
   - A 包含 B：B 是 A 的子组成部分
   - A 引用 B：A 和 B 之间存在交叉引用

3. 目录结构及用途
   每个目录的用途，以及什么类型的信息放入哪个目录

5-8个信息类型通常就够了。保持简洁实用。

不要包含页面格式规范、命名规范等系统行为说明。Schema 只描述领域结构。

直接输出 Markdown 格式，以 # 标题开头。不要包含任何解释性文字。
"""

    EXTRACT_KNOWLEDGE = """\
你是一个知识提取专家。请从以下原始资料中提取关键知识点。

【知识库 Schema】
{schema_section}

【原始资料】
{source_content}

{instructions_section}

【提取要求】
1. 根据 Schema 中定义的信息类型，识别资料中涉及的所有知识点
2. 每个知识点应该简洁明确
3. 判断每个知识点应该属于哪个已有的 wiki 页面（如果有的话），或者应该创建新页面
4. 一个资料可能涉及多个信息类型，需要创建或更新多个页面

【输出格式】
返回 JSON：
{{
  "knowledge_points": [
    {{
      "content": "知识点内容",
      "suggested_category": "根据 Schema 目录结构定义的分类",
      "suggested_page": "根据 Schema 目录结构建议的页面文件名",
      "summary": "一句话摘要",
      "source_ref": "来源标注"
    }}
  ]
}}
"""

    QUERY_KNOWLEDGE = """\
你是一个知识库查询助手。请基于以下知识库页面内容回答用户的问题。

【知识库 Schema】
{schema_section}

【用户问题】
{question}

{context_section}

【回答要求】
1. 根据 Schema 中定义的信息类型和关系，综合多个相关页面的信息
2. 引用具体页面作为来源
3. 如果知识库中没有相关信息，明确说明
4. 如果回答有价值，建议是否可以沉淀为新的页面
5. 使用中文回答

【回答格式】
先给出直接回答，然后在末尾标注来源页面：
> 来源: [页面路径列表]
"""

    LINT_WIKI = """\
你是一个知识库质量检查员。请对以下知识库进行全面检查。

【知识库统计】
{stats}

【页面列表】
{page_list}

【Schema】
{schema_section}

【页面内容】
{pages_content}

【检查项】
1. **矛盾检测**：不同页面间是否存在互相矛盾的信息
2. **孤立页面**：没有被其他页面引用或链接的页面
3. **缺失概念**：被多个页面提及但仍没有独立页面的概念或实体
4. **过时信息**：内容中是否有明显过时的信息
5. **结构优化**：当前分类体系和 Schema 是否匹配，是否需要调整
6. **交叉引用**：页面间的链接是否充分

【输出格式】
返回 JSON：
{{
  "contradictions": ["矛盾1", "矛盾2"],
  "orphan_pages": ["页面路径"],
  "missing_concepts": ["概念名"],
  "outdated_info": ["过时信息描述"],
  "structure_suggestions": ["结构优化建议"],
  "cross_reference_suggestions": ["交叉引用建议"],
  "schema_alignment_issues": ["Schema 与实际内容不匹配的地方"],
  "overall_health": "good/fair/poor",
  "summary": "一句话总结"
}}
"""

    EVOLVE_SCHEMA = """\
你是一个知识库架构师。请审视当前的知识库内容和 Schema，提出结构演进建议。

Schema 只包含三个部分：
1. 关注的信息类型（名称、描述、关注维度）
2. 类型之间的关系（包含、引用）
3. 目录结构及用途

【当前 Schema】
{current_schema}

【页面分布统计】
{stats}

【最近的变更】
{recent_changes}

{direction_section}

【演进要求】
1. 当前关注的信息类型是否需要调整？是否需要增减类型？
2. 类型之间的关系是否需要修改？
3. 目录结构是否需要调整以更好地映射信息类型？
4. 是否有类型膨胀（某个类型下页面过多）需要拆分？
5. 提供改进后的完整 Schema 文档

【输出格式】
返回完整的新 Schema 文档（Markdown 格式），只包含三个部分：信息类型、类型关系、目录结构。
不要包含页面格式规范、命名规范等内容——这些是系统默认行为，不属于 Schema。
    如果不需要修改，返回原 Schema 不变。
"""