"!!! 过时待删除或者重做 !!!"
import re
import os
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

        # Research Blueprint - 研究蓝图（Planning Stage 产出）
        self.blueprint_overview = None  # 自由文本，记录研究想法和思路
        self.research_plan = None  # 任务列表 (task/todo list)
        self.chapter_outline = None  # 章节大纲 (heading one 列表)
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


# ==========================================
# Prompt格式化工具函数
# ==========================================

def format_prompt(prompt: str, context: Any, **kwargs) -> str:
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
        # 改进：同时支持对象和字典
        elif isinstance(context, dict) and placeholder in context:
            format_dict[placeholder] = context[placeholder]
        elif hasattr(context, placeholder):
            format_dict[placeholder] = getattr(context, placeholder)
        else:
            missing_attrs.append(placeholder)

    if missing_attrs:
        raise KeyError(f"Context 和参数中缺少以下属性: {', '.join(missing_attrs)}")

    # 执行格式化
    return prompt.format(**format_dict)


# ==========================================
# Deep Research 特有的解析器
# ==========================================

def persona_parser(raw_reply: str, header= "[正式文稿]") -> dict:
    """
    解析人设生成（PERSONA_DESIGNER）的输出，提取 [正式文稿] 之后的内容。

    这是 deep research 特有的parser，用于验证人设格式。

    Args:
        raw_reply: LLM 返回的原始回复
    Returns:
        { "status": "success" | "error", "content" or "feedback": 提取的内容或错误信息}
    """
    from .parser_utils import simple_section_parser

    result = simple_section_parser(raw_reply, header)
    if result['status'] == 'success':
        # 处理返回值：可能是字符串（单section模式）或字典（多section模式）
        content = result['content']
        if isinstance(content, dict):
            content = content.get(header, "")

        if not content.startswith("你是"):
            return {"status": "error", "feedback": "正式文稿必须以'你是'开头"}

        #content里去掉开头的的“你是”以外的其他“你是”
        content = content.replace("你是","")

        # 返回字符串格式的内容
        return {"status": "success", "content": content}

    return result


def research_plan_parser(raw_reply: str) -> dict:
    """
    解析研究计划输出，验证格式并提取内容。

    这是 deep research 特有的parser，用于验证研究计划格式。

    Args:
        raw_reply: LLM 返回的原始回复
    Returns:
        { "status": "success" | "error", "content" or "feedback": 提取的内容或错误信息}
    """
    from .parser_utils import multi_section_parser

    plan = multi_section_parser(
        raw_reply,
        section_headers=["[研究计划]", "[章节大纲]", "[关键问题清单]"]
    )

    if plan['status'] == 'error':
        return plan

    chapter_outline = plan['content'].get("[章节大纲]", "").strip()
    research_plan = plan["content"].get("[研究计划]","").strip()
    if not research_plan:
        return {
                "status": "error",
                "feedback": "研究计划不能为空"
            }

    # 验证章节大纲格式
    for line in chapter_outline.split('\n'):
        line = line.strip()
        if line and not line.startswith('# '):
            return {
                "status": "error",
                "feedback": "章节大纲格式错误，每行必须以 '# ' 开头表示一级标题"
            }

    return plan


def director_approval_parser(raw_reply: str) -> dict:
    """
    解析director的输出，判断是否批准研究计划。

    这是dialog_with_retry模式中B（Verifier/director）使用的parser。

    期望的director输出格式：
    [决策]
    Approve / Need Improvement
    [理由]
    评估理由
    [反馈]
    （如果不批准，提供具体的改进建议）

    Args:
        raw_reply: director的输出

    Returns:
        批准时: {"status": "success", "decision": "approved", "reason": "..."}
        不批准时: {"status": "error", "decision": "rejected", "reason": "...", "feedback": "..."}
    """
    from .parser_utils import multi_section_parser

    sections = multi_section_parser(
        raw_reply,
        section_headers=["[决策]", "[理由]", "[反馈]"],
        match_mode="ANY"
    )

    if sections['status'] != 'success':
        return {"status": "error", "feedback": "格式错误，请使用指定的section格式"}

    decision_section = sections['content'].get("[决策]", "").strip()
    reason_section = sections['content'].get("[理由]", "")
    feedback_section = sections['content'].get("[反馈]", "")

    # 判断决策
    decision = decision_section.lower()
    approved_keywords = ["批准", "同意", "通过", "approved", "accept", "approve", "ok", "可以"]

    is_approved = any(keyword in decision for keyword in approved_keywords)

    if is_approved:
        return {
            "status": "success",  # ← 表示批准
            "decision": "approved",
            "reason": reason_section
        }
    else:
        # 不批准，必须提供反馈
        feedback = feedback_section if feedback_section else decision_section
        return {
            "status": "error",  # ← 表示不批准
            "decision": "rejected",
            "reason": reason_section,
            "feedback": f"请根据以下建议改进研究计划：\n\n{feedback}"
        }


class DeepResearcherPrompts:
    """Deep Researcher Prompt 集中管理"""

    # ==========================================
    # 1. 人设生成
    # ==========================================

    DIRECTOR_PERSONA_DESIGNER = """
    你是一个见多识广的跨领域专家。现在公司打算编写一个研究报告（主题是关于：{research_title}),主要目的包括：{research_purpose}。
    现在我们需要聘用一个最适合的专家导师来主持工作并带领高级研究员完成这项工作，你来负责考虑一下应该选择什么样的专家，需要具备什么样的
    能力特质和工作习惯。写一个简短的人员需求。我们会把这个内容作为招聘广告的一部份。
    你输出的时候可以简短描述你的理由，然后用"[正式文稿]"作为分隔符，开始输出正式的人员需求文稿。正式需求文稿必须用第二人称的方式来描述需求，仿佛直接对潜在应聘者说话，人员需求说明用"你是"开头，用"。"结尾，不要使用"我们"。'

    输出示范：

    ```
    你简短的思考理由

    [正式文稿]
    你是blablabla(你草拟的具体要求)。
    ```
    """

    RESEARCHER_PERSONA_DESIGNER = """
    你是{director_persona}。现在公司打算编写一个研究报告（主题是关于：{research_title}),主要目的包括：{research_purpose}。
    由你来主持工作并带领资深研究员完成这项工作，你来负责考虑一下应该选择什么样的高级研究员，需要具备什么样的资质、
    能力特质和工作习惯。写一个简短的人员需求。我们会把这个内容作为招聘广告的一部份。
    你输出的时候可以简短描述你的理由，然后用"[正式文稿]"作为分隔符，开始输出正式的人员需求文稿。正式需求文稿必须用第二人称的方式来描述需求，仿佛直接对潜在应聘者说话，人员需求说明用"你是"开头，用"。"结尾，不要使用"我们"。'

    输出示范：

    ```
    你简短的思考理由

    [正式文稿]
    你是blablabla(你草拟的具体要求)。
    ```
    """

    # ==========================================
    # 2. 研究计划制定
    # ==========================================

    START_PLAN_PROMPT = '''
    {researcher_persona}

    新的研究任务：
    {research_title}，

    研究目的和需求：
    {research_purpose}。

    请根据这个任务，制定一个详细的研究思路和计划，列出大致的目录结构大纲，先从IMRaD 结构（背景痛点/Why, 方法工具/How，结果数据/What，观点洞察/So What)开始设计。

    '''

    DIRECTOR_REVIEW_PROMPT = '''
    {director_persona}，负责指导研究员利用网络进行{research_title} 研究项目。目的是: {research_purpose}。现在请你根据研究员提交的研究计划，
    给出你的建议和反馈，帮助他做好计划，避免过于简单和过于复杂（研究计划和目标要匹配）。重点考察
    1. 核心逻辑链闭环（The "Fatal Flaw" Check）
    这是唯一的**"一票否决项"**。如果这里有问题，必须打回去改；如果这里没问题，其他都可以妥协。
    标准：目的是否明确？方法是否真的能回答这个目的？
    2. 第一步极其具体（The "Tomorrow" Test）
    很多学生计划书写得宏大，但不知道明天进实验室该干嘛。
    标准：计划第一个步骤是否具备极高的可操作性？
    3. 区分"必要性修改"与"偏好性修改"
    这是控制你完美主义强迫症的关键。在Review时，你要在心里把意见分为两类：
    必要性修改（Must fix）：逻辑错误、安全隐患、方法不可行。（必须指出来，严厉要求）
    偏好性修改（Nice to have）：我觉得这样写更好。（忍住不说，或者只提建议不强制）

    [研究员的计划草稿]：
    {plan_draft}

    ==== END OF DRAFT====

    简短扼要的给出你精炼的建议，如果计划大体可行，就鼓励研究员尽快开始
    '''

    

    

    

    

    # ==========================================
    # 4. 报告撰写
    # ==========================================

    WRITE_CHAPTER_DRAFT = """
    {researcher_persona}

    请根据收集的研究笔记撰写 [{chapter_name}] 章节的草稿。

    研究主题：{research_title}
    本章相关笔记：
    {chapter_notes}

    本章相关页面摘要：
    {chapter_summaries}

    请撰写一份详细的章节草稿，要求：
    1. 基于笔记和摘要进行扩写
    2. 保持逻辑清晰、层次分明
    3. 如果发现数据缺失或需要补充，用 [待查] 标记
    4. 不要在撰写过程中停止去查找资料，写完统一标记

    输出格式为Markdown。
    """

    POLISH_REPORT = """
    请对以下研究报告草稿进行润色和优化。

    研究主题：{research_title}
    草稿内容：
    {draft_content}

    润色要求：
    1. 修正语法和表达错误
    2. 统一格式和风格
    3. 优化段落逻辑和过渡
    4. 确保专业术语使用准确
    5. 保持原有观点和数据不变

    输出润色后的完整报告。
    """


@dataclass
class Note:
    """单条笔记"""
    content: str
    chapter_name: str
    url: Optional[str] = None

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
    def chapter_names(self) -> Set[str]:
        return {note.chapter_name for note in self.notes}

    def add_note(self, note: Note):
        self.notes.append(note)


class Notebook:
    """笔记本 - 番茄笔记法（带文件持久化）"""

    UNCATEGORIZED_NAME = "未分类"

    def __init__(self, file_path: str, page_size_limit: int = 2000):
        """
        初始化笔记本

        Args:
            file_path: 笔记本文件路径（JSON格式，必需）
            page_size_limit: 每页最大字符数

        Raises:
            ValueError: 如果 file_path 为 None 或空字符串
        """
        if not file_path:
            raise ValueError("file_path is required for Notebook")

        self.file_path = file_path
        self.pages: List[Page] = []
        self.page_size_limit = page_size_limit
        self._current_page: Optional[Page] = None

        # 简化：章节名集合
        self._chapters: set[str] = set()

        # 创建默认的"未分类"章节
        self._chapters.add(self.UNCATEGORIZED_NAME)

        # 从文件加载（如果文件存在）或创建新文件
        self._load_from_file()

    def _load_from_file(self):
        """从文件加载笔记本数据

        如果文件不存在，自动创建空文件
        如果文件存在，加载已有内容
        如果加载失败，使用空笔记本（但会尝试创建文件）
        """
        try:
            from pathlib import Path
            file_path = Path(self.file_path)

            if not file_path.exists():
                # 文件不存在，创建空文件
                self._save_to_file()
                return

            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 恢复 chapters（现在是 set）
            self._chapters = set(data.get("chapters", []))

            # 恢复 pages
            self.pages = []
            for page_data in data.get("pages", []):
                page = Page(
                    page_number=page_data["page_number"],
                    notes=[
                        Note(
                            content=n["content"],
                            chapter_name=n["chapter_name"],
                            url=n.get("url")  # 兼容旧数据，url 可能为 None
                        )
                        for n in page_data.get("notes", [])
                    ],
                    summary=page_data.get("summary", "")
                )
                self.pages.append(page)

            # 恢复当前页
            if self.pages:
                last_page_num = data.get("current_page_number", len(self.pages) - 1)
                if 0 <= last_page_num < len(self.pages):
                    self._current_page = self.pages[last_page_num]

        except Exception as e:
            print(f"Warning: Failed to load notebook from {self.file_path}: {e}")
            # 加载失败，尝试创建新文件
            try:
                self._save_to_file()
            except:
                pass  # 如果创建也失败，就使用内存中的空笔记本

    def _save_to_file(self):
        """保存笔记本到文件"""
        try:
            from pathlib import Path
            import json

            file_path = Path(self.file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 序列化数据（简化结构）
            data = {
                "chapters": list(self._chapters),  # set -> list
                "pages": [
                    {
                        "page_number": page.page_number,
                        "notes": [
                            {
                                "content": note.content,
                                "chapter_name": note.chapter_name,
                                "url": note.url
                            }
                            for note in page.notes
                        ],
                        "summary": page.summary
                    }
                    for page in self.pages
                ],
                "current_page_number": self._current_page.page_number if self._current_page else -1
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Warning: Failed to save notebook to {self.file_path}: {e}")

    def create_chapter(self, name: str) -> None:
        """创建新章节"""
        if name in self._chapters:
            raise ValueError(f"Chapter '{name}' already exists")
        self._chapters.add(name)
        # 自动保存
        self._save_to_file()

    def rename_chapter(self, old_name: str, new_name: str) -> bool:
        """
        重命名章节（使用文件级字符串替换）

        Args:
            old_name: 旧章节名
            new_name: 新章节名

        Returns:
            bool: 是否重命名成功
        """
        if old_name not in self._chapters or new_name in self._chapters:
            return False

        try:
            from pathlib import Path

            # 1. 直接对文件做字符串替换（带着双引号）
            file_path = Path(self.file_path)
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 替换所有出现的地方
                content = content.replace(f'"{old_name}"', f'"{new_name}"')

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

            # 2. 重新加载整个 notebook
            self._load_from_file()

            return True

        except Exception as e:
            print(f"Warning: Failed to rename chapter: {e}")
            return False

    def delete_chapter(self, name: str, cascade: bool = True) -> bool:
        """
        删除章节

        Args:
            name: 章节名
            cascade: True=删除章节和相关笔记, False=移到未分类

        Returns:
            bool: 是否删除成功
        """
        if name not in self._chapters or name == self.UNCATEGORIZED_NAME:
            return False

        self._chapters.remove(name)

        if cascade:
            # 删除相关笔记
            for page in self.pages:
                page.notes = [n for n in page.notes if n.chapter_name != name]
        else:
            # 移到未分类
            for page in self.pages:
                for note in page.notes:
                    if note.chapter_name == name:
                        note.chapter_name = self.UNCATEGORIZED_NAME

        # 自动保存
        self._save_to_file()
        return True

    def add_note(self, content: str, chapter_name: str, url: Optional[str] = None) -> tuple[Page, bool]:
        """
        添加笔记

        Args:
            content: 笔记内容
            chapter_name: 章节名称
            url: 来源 URL（可选）

        Returns:
            tuple[Page, bool]: (当前页, 是否为新创建的页)
        """
        # 如果章节不存在，自动创建
        if chapter_name not in self._chapters:
            self._chapters.add(chapter_name)

        note = Note(content=content, chapter_name=chapter_name, url=url)

        is_new_page = False
        if (self._current_page is not None and
            self._current_page.total_length + note.length > self.page_size_limit):
            self._add_new_page()
            is_new_page = True

        self.current_page.add_note(note)

        # 自动保存
        self._save_to_file()

        return self._current_page, is_new_page

    @property
    def current_page(self) -> Page:
        if self._current_page is None:
            self._add_new_page()
        return self._current_page

    def _add_new_page(self):
        """添加新页"""
        new_page = Page(page_number=len(self.pages))
        self.pages.append(new_page)
        self._current_page = new_page

    def get_notes_by_chapter(self, chapter_name: str) -> List[Note]:
        """获取指定章节的所有笔记"""
        if chapter_name not in self._chapters:
            return []

        return [
            note for page in self.pages
            for note in page.notes
            if note.chapter_name == chapter_name
        ]

    def get_pages_by_chapter(self, chapter_name: str) -> List[Page]:
        """获取包含指定章节笔记的所有页"""
        if chapter_name not in self._chapters:
            return []

        return [
            page for page in self.pages
            if chapter_name in page.chapter_names
        ]


    def list_chapters(self) -> List[str]:
        """列出所有章节名称"""
        return list(self._chapters)
