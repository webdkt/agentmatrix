import re
from ..core.browser.browser_common import BaseCrawlerContext
from .utils import sanitize_filename
from typing import Any, Dict

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
        result = self._generic_txt_parser(raw_reply, "[正式文稿]")
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




    def _generic_txt_parser(self, raw_reply: str, divider=None) -> dict:
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
        try:
            if not raw_reply or not isinstance(raw_reply, str):
                return {"status": "error", "feedback": "输入内容无效"}
                
            # 情况1: 使用指定的分隔符
            if divider:
                if divider not in raw_reply:
                    return {"status": "error", "feedback": f"未找到分隔行 '{divider}'，请确保输出格式正确"}
                parts = raw_reply.split(divider, 1)
                content = parts[1].strip()
                    
            # 情况2: 自动查找分隔行
            else:
                # 匹配模式: 开头至少2个=，结尾至少2个=，中间可有任意内容
                pattern = r'^={2,}.*={2,}$'
                lines = raw_reply.split('\n')
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




    