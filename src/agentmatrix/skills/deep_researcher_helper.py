import re
import os
import uuid
from ..core.browser.browser_common import BaseCrawlerContext
from .utils import sanitize_filename
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
from dataclasses import dataclass, field
import sqlite3
class ResearchContext(BaseCrawlerContext):
    """
    全局任务上下文 (Global Memory)
    跨越所有递归层级共享的数据。
    """

    def __init__(self,research_title, research_purpose: str):
        super().__init__(0)
        self.research_title = research_title
        self.research_purpose = research_purpose
        self.director_persona = None
        self.researcher_persona = None
        clean_title = sanitize_filename(research_title)
        
        self.research_dir = Path(self.private_workspace, clean_title)
        #检查self.research_dir 是否存在，如果不存在，创建它：
        self.research_dir.mkdir(parents=True, exist_ok=True)

        


        self.knowledge_base: List[Dict] = []
        self._db_conn: Optional[sqlite3.Connection] = None
        self._init_database()
        self._load_assessed_history()

        self.research_plan = None
        self.chapter_outline = None
        self.key_questions = None
        self.current_status = None

    def mark_link_assessed(self, url: str):
        """标记链接为已评估（内存 + 数据库）"""
        super().mark_link_assessed(url)
        if url not in self.assessed_links:
            self._db_conn.execute(
                "INSERT OR IGNORE INTO assessed_links (url) VALUES (?)",
                (url,)
            )
            self._db_conn.commit()

    def mark_buttons_assessed(self, url: str, button_texts: List[str]):
        """批量标记按钮为已评估（内存 + 数据库）"""
        super().mark_buttons_assessed(url, button_texts)
        for button_text in button_texts:
            key = f"{url}|{button_text}"
            if key not in self.assessed_buttons:
                self._db_conn.execute(
                    "INSERT OR IGNORE INTO assessed_buttons (button_key) VALUES (?)",
                    (key,)
                )
        self._db_conn.commit()

    def _init_database(self):
        """初始化 SQLite 数据库"""
        db_path = os.path.join(self.research_dir, ".crawler_assessment.db")
        self._db_conn = sqlite3.connect(db_path)
        self._db_conn.execute("PRAGMA journal_mode=WAL")  # 提升并发性能

        # 创建表
        self._db_conn.execute("""
            CREATE TABLE IF NOT EXISTS assessed_links (
                url TEXT PRIMARY KEY,
                assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self._db_conn.execute("""
            CREATE TABLE IF NOT EXISTS assessed_buttons (
                button_key TEXT PRIMARY KEY,
                assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self._db_conn.commit()

class DeepResearcherHelper:
    DIRECTOR_PERSONA_DESIGNER="""
        你是一个见多识广的跨领域专家。现在公司打算编写一个研究报告（主题是关于：{research_title}),主要目的包括：{research_purpose}。
        现在我们需要聘用一个最适合的专家导师来主持工作并带领高级研究员完成这项工作，你来负责考虑一下应该选择什么样的专家，需要具备什么样的
        能力特质和工作习惯。写一个简短的人员需求。我们会把这个内容作为招聘广告的一部份。
        你输出的时候可以简短描述你的理由，然后用"[正式文稿]"作为分隔符，开始输出正式的人员需求文稿。正式需求文稿必须用第二人称的方式来描述需求，仿佛直接对潜在应聘者说话，人员需求说明用“你是”开头，用“。”结尾，不要使用“我们”。‘
        
        输出范例：

        ```
        你简短的思考理由

        [正式文稿]
        你是blablabla(你草拟的具体要求)。
        ```
    """
    RESEARCHER_PERSONA_DESIGNER="""
        {director_persona}。现在公司打算编写一个研究报告（主题是关于：{research_title}),主要目的包括：{research_purpose}。
        由你来主持工作并带领资深研究员完成这项工作，你来负责考虑一下应该选择什么样的高级研究员，需要具备什么样的资质、
        能力特质和工作习惯。写一个简短的人员需求。我们会把这个内容作为招聘广告的一部份。
        你输出的时候可以简短描述你的理由，然后用"[正式文稿]"作为分隔符，开始输出正式的人员需求文稿。正式需求文稿必须用第二人称的方式来描述需求，仿佛直接对潜在应聘者说话，人员需求说明用“你是”开头，用“。”结尾，不要使用“我们”。‘
        
        输出范例：

        ```
        你简短的思考理由

        [正式文稿]
        你是blablabla(你草拟的具体要求)。
        ```
    """




    def _persona_parser(self, raw_reply: str) -> dict:
        """
        解析 PERSONA_DESIGNER 的输出，提取 [正式文稿] 之后的内容。
        Args:
            raw_reply: LLM 返回的原始回复
        Returns:
            { "status": "success" | "error", "data" or "feedback": 提取的内容或错误信息}
        """
        result = self._simple_section_parser(raw_reply, "[正式文稿]")
        if result['status'] == 'success':
            if not result['data'].startswith("你是"):
                return {"status": "error", "feedback": "正式文稿必须以'你是'开头"}
        return result


    START_PLAN_PROMPT = '''
    {researcher_persona}

    新的研究任务：
    {research_title}，
    
    研究目的和需求：
    {research_purpose}。
    
    请根据这个任务，制定一个详细的研究思路和计划，列出大致的目录结构大纲，先从IMRaD 结构（背景痛点/Why, 方法工具/How，结果数据/What，观点洞察/So What)开始设计。

    '''

    DIRECTOR_REVIEW_PROMPT='''
    {director_persona}，负责指导研究员利用网络进行{research_title} 研究项目。目的是: {research_purpose}。现在请你根据研究员提交的研究计划，
    给出你的建议和反馈，帮助他做好计划，避免过于简单和过于复杂（研究计划和目标要匹配）。重点考察
    1. 核心逻辑链闭环（The "Fatal Flaw" Check）
    这是唯一的**“一票否决项”**。如果这里有问题，必须打回去改；如果这里没问题，其他都可以妥协。
    标准：目的是否明确？方法是否真的能回答这个目的？
    2. 第一步极其具体（The "Tomorrow" Test）
    很多学生计划书写得宏大，但不知道明天进实验室该干嘛。
    标准：计划第一个步骤是否具备极高的可操作性？
    3. 区分“必要性修改”与“偏好性修改”
    这是控制你完美主义强迫症的关键。在Review时，你要在心里把意见分为两类：
    必要性修改（Must fix）：逻辑错误、安全隐患、方法不可行。（必须指出来，严厉要求）
    偏好性修改（Nice to have）：我觉得这样写更好。（忍住不说，或者只提建议不强制）

    [研究员的计划草稿]：
    {plan_draft}

    ==== END OF DRAFT====

    简短扼要的给出你精炼的建议，如果计划大体可行，就鼓励研究员尽快开始
    '''

    RESEARCHER_FINAL_PLAN_1 = '''
    {researcher_persona}
    
    为了[{research_title}]项目（目的：{reseaerch_purpose})
    你草拟了研究计划：
    {draft_plan}, 

    导师对计划的建议和反馈是：
    {director_suggestion}，
    
    现在综合考虑一下，制定出最终计划。可以先阐述一下你的理解，然后分段落说明[研究计划]，[章节大纲]，以及初步的[关键问题清单]，具体输出格式如下：

    ```
    你的理解和思考

    [研究计划]
    你的最终研究计划内容

    [章节大纲]
    你的章节目录大纲，用Markdown的一级标题表示，每行一个章节标题
    # 章节1
    # 章节2
    ...
    
    [关键问题清单]
    1. 关键问题1
    2. 关键问题2
    3. 每行一个关键问题
    ...
    ```
    '''

    def _research_plan_parser(self, raw_reply: str) -> dict:
        plan = self._multi_section_parser(
            raw_reply,
            section_headers=["[研究计划]", "[章节大纲]", "[关键问题清单]"]
        )
        if plan['status'] == 'error':
            return plan

        chapter_outline = plan['sections'].get("[章节大纲]", "").strip()
        #检查chapter_outline 是否符合要求：每行以 # 开头，并且只有一个#
        for line in chapter_outline.split('\n'):
            if not line.startswith('# '):
                return {"status": "error", "feedback": "章节大纲格式错误，每行必须以 '# ' 开头表示一级标题"}
        #都正确返回结果
        return plan



    def _format_prompt(prompt: str, context: Any, **kwargs) -> str:
        """
        自动根据 context 对象的属性和动态参数填充 prompt 中的占位符
        
        Args:
            prompt: 包含占位符的模板字符串，如 "{researcher_persona}"
            context: 包含属性的对象，如 ResearchContext 实例
            **kwargs: 额外的动态参数，优先级高于 context 属性
            
        Returns:
            格式化后的字符串
            
        Raises:
            KeyError: 当占位符在 context 和 kwargs 中都找不到对应属性时
        """
        # 提取所有占位符
        placeholders = re.findall(r'\{(\w+)\}', prompt)
        
        # 构建 format 所需的字典
        format_dict = {}
        missing_attrs = []
        
        for placeholder in placeholders:
            # 优先级: kwargs > context
            if placeholder in kwargs:
                format_dict[placeholder] = kwargs[placeholder]
            elif hasattr(context, placeholder):
                format_dict[placeholder] = getattr(context, placeholder)
            else:
                missing_attrs.append(placeholder)
        
        if missing_attrs:
            raise KeyError(f"Context 和参数中缺少以下属性: {', '.join(missing_attrs)}")
        
        # 执行格式化
        return prompt.format(**format_dict)



    async def _generate_personas(self, ctx):

        #生成研究导师人设
        director_prompt = self._format_prompt(self.DIRECTOR_PERSONA_DESIGNER, ctx)
        director_persona = await self.brain.think_with_retry(director_prompt, self._persona_parser)
        #生成研究员人设
        researcher_prompt = self._format_prompt(self.RESEARCHER_PERSONA_DESIGNER, ctx)        
        researcher_persona = await self.brain.think_with_retry(researcher_prompt, self._persona_parser)
        return director_persona, researcher_persona




    def _simple_section_parser(self, raw_reply: str, divider=None) -> dict:
        """
        通用文本解析器，根据分隔符提取内容。
        
        Args:
            raw_reply: LLM 返回的原始回复
            divider: 可选分隔符。如果为 None，则自动查找形如 "=====" 或 "=====text=====" 的分隔行
                    分隔行前后都至少需要2个等号
            
        Returns:
            {
                "status": "success" | "error",
                "data": 提取的内容 (成功时),
                "feedback": 错误信息 (失败时)
            }
        """
        return self._multi_section_parser(raw_reply, section_headers=[divider] if divider else None)
        

    def _multi_section_parser(self, raw_reply: str, section_headers=None, regex_mode=False, match_mode="ALL") -> dict:
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
            >>> result = helper._multi_section_parser(
            ...     text,
            ...     section_headers=['[研究计划]', '[章节大纲]'],
            ...     match_mode="ALL"
            ... )
            >>> # 如果缺少任何一个 header，返回 error

            >>> # ANY 模式
            >>> result = helper._multi_section_parser(
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

            # ========== 模式2: 单 section 解析（向后兼容，等同于 _generic_txt_parser）==========
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
            self.logger.exception(e)
            return {"status": "error", "feedback": f"解析失败: {str(e)}"}


@dataclass
class Note:
    """单条笔记"""
    content: str
    chapter_id: str

    @property
    def length(self) -> int:
        return len(self.content)


@dataclass
class Page:
    """笔记本的一页"""
    page_number: int
    notes: List[Note] = field(default_factory=list)
    summary: str = ""

    @property
    def total_length(self) -> int:
        return sum(note.length for note in self.notes)

    @property
    def chapter_ids(self) -> Set[str]:
        return {note.chapter_id for note in self.notes}

    def add_note(self, note: Note):
        self.notes.append(note)


class Notebook:
    """笔记本 - 番茄笔记法"""

    UNCATEGORIZED_NAME = "未分类"

    def __init__(self, page_size_limit: int = 2000):
        self.pages: List[Page] = []
        self.page_size_limit = page_size_limit
        self._current_page: Optional[Page] = None

        # 章节: id -> {"id": str, "name": str}
        self._chapters: Dict[str, Dict] = {}
        # 名称到ID的映射
        self._name_to_id: Dict[str, str] = {}

        # 创建默认的"未分类"章节
        self._create_chapter(self.UNCATEGORIZED_NAME)

    def _create_chapter(self, name: str) -> str:
        """内部方法：创建章节，返回id"""
        chapter_id = str(uuid.uuid4())
        self._chapters[chapter_id] = {"id": chapter_id, "name": name}
        self._name_to_id[name] = chapter_id
        return chapter_id

    def create_chapter(self, name: str) -> str:
        """创建新章节"""
        if name in self._name_to_id:
            raise ValueError(f"Chapter '{name}' already exists")
        return self._create_chapter(name)

    def _get_chapter_id(self, name: str) -> Optional[str]:
        """根据名称获取章节ID"""
        return self._name_to_id.get(name)

    def rename_chapter(self, old_name: str, new_name: str) -> bool:
        """重命名章节"""
        chapter_id = self._get_chapter_id(old_name)
        if not chapter_id or new_name in self._name_to_id:
            return False

        self._chapters[chapter_id]["name"] = new_name
        del self._name_to_id[old_name]
        self._name_to_id[new_name] = chapter_id
        return True

    def delete_chapter(self, name: str, cascade: bool = True) -> bool:
        """
        删除章节
        :param cascade: True=删除章节和相关笔记, False=移到未分类
        """
        chapter_id = self._get_chapter_id(name)
        if not chapter_id or name == self.UNCATEGORIZED_NAME:
            return False

        del self._chapters[chapter_id]
        del self._name_to_id[name]

        uncategorized_id = self._get_chapter_id(self.UNCATEGORIZED_NAME)

        if cascade:
            # 删除相关笔记
            for page in self.pages:
                page.notes = [n for n in page.notes if n.chapter_id != chapter_id]
        else:
            # 移到未分类
            for page in self.pages:
                for note in page.notes:
                    if note.chapter_id == chapter_id:
                        note.chapter_id = uncategorized_id

        return True

    def add_note(self, content: str, chapter_name: str) -> Page:
        """添加笔记"""
        chapter_id = self._get_chapter_id(chapter_name)
        if chapter_id is None:
            # 自动创建章节
            chapter_id = self._create_chapter(chapter_name)

        note = Note(content=content, chapter_id=chapter_id)

        if (self._current_page is not None and
            self._current_page.total_length + note.length > self.page_size_limit):
            self._add_new_page()

        self.current_page.add_note(note)
        return self._current_page

    @property
    def current_page(self) -> Page:
        if self._current_page is None:
            self._add_new_page()
        return self._current_page

    def get_notes_by_chapter(self, chapter_name: str) -> List[Note]:
        chapter_id = self._get_chapter_id(chapter_name)
        if not chapter_id:
            return []

        return [
            note for page in self.pages
            for note in page.notes
            if note.chapter_id == chapter_id
        ]

    def get_pages_by_chapter(self, chapter_name: str) -> List[Page]:
        chapter_id = self._get_chapter_id(chapter_name)
        if not chapter_id:
            return []

        return [
            page for page in self.pages
            if chapter_id in page.chapter_ids
        ]

    def get_summaries_by_chapter(self, chapter_name: str) -> List[str]:
        return [
            page.summary for page in self.get_pages_by_chapter(chapter_name)
            if page.summary
        ]

    def get_chapter_info(self, chapter_name: str) -> Dict:
        return {
            "notes": self.get_notes_by_chapter(chapter_name),
            "pages": self.get_pages_by_chapter(chapter_name),
            "summaries": self.get_summaries_by_chapter(chapter_name)
        }

    def _add_new_page(self):
        new_page = Page(page_number=len(self.pages))
        self.pages.append(new_page)
        self._current_page = new_page

    def set_page_summary(self, page_number: int, summary: str):
        if 0 <= page_number < len(self.pages):
            self.pages[page_number].summary = summary

    def list_chapters(self) -> List[str]:
        """列出所有章节名称"""
        return [ch["name"] for ch in self._chapters.values()]
