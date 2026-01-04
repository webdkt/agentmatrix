'''
这是一个为 BrowserAdapter 抽象层骨架。

它定义了**逻辑层（Logic Layer）与执行层（Execution Layer）**之间的契约。支持 DrissionPage 等库的后续实现。

InteractionReport (互动报告)：

    它允许 Adapter 告诉逻辑层：“我点了一下，结果弹出了一个新窗口，并且当前页面也刷新了”。逻辑层收到报告后，可以先去递归处理 new_tab_handles，回来后再根据 is_dom_changed 决定是否 Soft Restart。

scan_elements (侦察)：

    我们将“寻找链接”和“寻找按钮”合并为一个扫描动作。这更高效，避免遍历两次 DOM。


PageContentType：

    明确区分 HTML 和 PDF。因为如果浏览器直接打开了 PDF，我们不需要做“小脑总结”，而是直接由 Adapter 提供的 save_view_as_file 存下来。
'''
from abc import ABC, abstractmethod
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict, Union

# ==========================================
# 1. 通用类型定义 (Type Definitions)
# ==========================================

# TabHandle: 一个标记，代表浏览器的一个具体标签页。
# 在 DrissionPage 中这可能是 ChromiumTab 对象，在 Playwright 中是 Page 对象。
# 逻辑层不需要知道它具体是什么，只需要拿着它传回给 Adapter。
TabHandle = Any 

class KeyAction(Enum):
    """常用的键盘操作"""
    ENTER = "enter"
    ESC = "esc"
    TAB = "tab"
    PAGE_DOWN = "page_down"
    SPACE = "space"

class PageType(Enum):
    """当前页面的内容类型"""
    NAVIGABLE = auto()   # HTML 网页 (值得 Scout 和 Click)
    STATIC_ASSET = auto() # PDF, JSON, TXT, Image (只值得 Save 或 Read)
    ERRO_PAGE = auto()

class ElementType(Enum):
    """可交互元素的类型"""
    LINK = auto()          # <a href="..."> 导航链接
    BUTTON = auto()        # <button>, <div role="button"> 交互按钮
    INPUT = auto()         # 输入框 (虽然目前流程主要只读/点，保留扩展性)

# ==========================================
# 2. 数据载体 (Data Carriers)
# ==========================================


class PageElement:
    """
    [Input] 逻辑层看到的“可点击对象”。
    Adapter 在 Phase 4 (Scout) 扫描页面时生成此对象。
    """
    @abstractmethod
    def get_text(self) -> str:
        """获取元素的可见文本 (用于小脑判断)"""
        pass

    @abstractmethod
    def get_tag_name(self) -> str:
        """获取元素的标签名 (a, button, div)"""
        pass

    @abstractmethod
    def get_element(self) -> Any:
        """获取元素对象 (如 DrissionPageElement)"""
        pass

    @abstractmethod
    def is_visible(self) -> bool:
        """元素是否可见"""
        pass
    

@dataclass
class InteractionReport:
    """
    [Output] 点击/操作后的“后果报告单”。
    对应 Phase 5 的串行处理逻辑。非互斥，包含所有观测到的现象。
    """
    # 1. 外部后果 (External Consequences)
    new_tabs: List[TabHandle] = field(default_factory=list) # 弹出的新标签页句柄
    downloaded_files: List[str] = field(default_factory=list)      # 触发下载的文件本地路径

    # 2. 内部后果 (Internal Consequences)
    is_url_changed: bool = False   # URL 是否改变
    is_dom_changed: bool = False   # DOM 结构是否显著改变 (用于 Soft Restart 判断)
    
    # 3. 错误信息
    error: Optional[str] = None    # 如果操作失败 (如元素被遮挡/超时)

@dataclass
class PageSnapshot:
    """
    [Output] 页面的静态快照。
    用于 Phase 2/3 (Assess) 小脑阅读。
    """
    url: str
    title: str
    content_type: PageType
    main_text: str         # 清洗后的正文 (Markdown 或 纯文本)
    raw_html: str          # 原始 HTML (备用)

# ==========================================
# 3. 浏览器适配器接口 (The Interface)
# ==========================================

class BrowserAdapter(ABC):
    """
    浏览器自动化层的统一接口。
    负责屏蔽具体库 (DrissionPage/Selenium) 的实现细节。
    """

    # --- Lifecycle (生命周期管理) ---

    @abstractmethod
    async def start(self, headless: bool = False):
        """启动浏览器进程"""
        pass

    @abstractmethod
    async def close(self):
        """关闭浏览器进程并清理资源"""
        pass

    # --- Tab Management (标签页管理) ---

    @abstractmethod
    async def create_tab(self, url: Optional[str] = None) -> TabHandle:
        """打开一个新的标签页，返回句柄"""
        pass

    @abstractmethod
    async def close_tab(self, tab: TabHandle):
        """关闭指定的标签页"""
        pass

    @abstractmethod
    async def get_tab(self) -> TabHandle:
        """获取当前焦点标签页的句柄"""
        pass

    @abstractmethod
    def get_tab_url(self, tab: TabHandle) -> str:
        """获取指定标签页的 URL"""
        pass

    

    @abstractmethod
    async def switch_to_tab(self, tab: TabHandle):
        """将浏览器焦点切换到指定标签页 (模拟人类视线)"""
        pass

    # --- Navigation & Content (导航与内容获取) ---

    @abstractmethod
    async def navigate(self, tab: TabHandle, url: str) -> InteractionReport:
        """
        在指定 Tab 访问 URL。
        注意：Navigate 也可能触发下载 (如直接访问 pdf 链接)，因此返回 InteractionReport。
        """
        pass

    @abstractmethod
    async def stabilize(self, tab: TabHandle):
        """
        [Phase 2] 页面稳定化。
        等待 DOM Ready，处理弹窗 (Alert/Cookie Consent)，滚动加载。
        """
        pass

    @abstractmethod
    async def analyze_page_type(self, tab: TabHandle) -> PageType:
        """
        判断当前页面是什么类型 (HTML, PDF Viewer, etc.)
        """
        pass

    @abstractmethod
    async def get_page_snapshot(self, tab: TabHandle) -> PageSnapshot:
        """
        [Phase 3] 获取页面内容供小脑阅读。
        应包含提取好的正文。
        """
        pass
    
    @abstractmethod
    async def save_view_as_file(self, tab: TabHandle, save_dir: str) -> Optional[str]:
        """
        如果当前页面是 PDF 预览或纯文本，将其保存为本地文件。
        """
        pass

    # --- Scouting & Interaction (侦察与交互) ---

    @abstractmethod
    async def scan_elements(self, tab: TabHandle):
        """
        [Phase 4] 扫描页面。
        返回所有可见的、有意义的交互元素 (链接 + 按钮)。
        需要过滤掉不可见元素、空链接等。
        """
        pass

    
    

    @abstractmethod
    async def click_and_observe(self, tab: TabHandle, element: Union[str, PageElement]) -> InteractionReport:
        """
        [Phase 5] 核心交互函数。
        点击元素，并智能等待，捕捉所有可能的后果 (新Tab、下载、页面变动)。
        必须能够处理 SPA (单页应用) 的 DOM 变动检测。
        """
        pass

    # ==========================================
    # Input & Control (精确输入与控制)
    #    用于 Phase 0 (搜索) 或特定表单交互
    # ==========================================

    @abstractmethod
    async def type_text(self, tab: TabHandle, selector: str, text: str, clear_existing: bool = True) -> bool:
        """
        在指定元素中输入文本。
        
        Args:
            selector: 定位符 (CSS/XPath/DrissionPage语法)。例如: 'input[name="q"]'
            text: 要输入的文本。
            clear_existing: 输入前是否清空原有内容。
            
        Returns:
            bool: 操作是否成功 (元素找到且输入完成)。
        """
        pass

    @abstractmethod
    async def press_key(self, tab: TabHandle, key: Union[KeyAction, str]) -> InteractionReport:
        """
        在当前页面模拟按键。
        通常用于输入搜索词后按回车。
        
        Returns:
            InteractionReport: 按键可能会导致页面刷新或跳转 (如按回车提交表单)，
            所以必须返回后果报告，供逻辑层判断是否需要 Soft Restart。
        """
        pass

    @abstractmethod
    async def click_by_selector(self, tab: TabHandle, selector: str) -> InteractionReport:
        """
        [精确点击] 通过选择器点击特定元素。
        区别于 click_and_observe (那个是基于侦察出的 PageElement 对象)，
        这个方法用于已知页面结构的场景 (如点击搜索按钮)。
        """
        pass

    @abstractmethod
    async def scroll(self, tab: TabHandle, direction: str = "bottom", distance: int = 0):
        """
        手动控制滚动。
        Args:
            direction: 'bottom', 'top', 'down', 'up'
            distance: 像素值 (如果 direction 是 down/up)
        """
        pass

    @abstractmethod
    async def find_element(self, tab: TabHandle, selector: str) -> PageElement:
        """
        检查某个特定元素是否存在。
        用于验证页面是否加载正确 (例如：检查是否存在 'input[name="q"]' 来确认是否在 Google 首页)。
        如果存在就返回这个element, 不存在返回None
        """
        pass

    @abstractmethod
    async def save_static_asset(self, tab: TabHandle) -> Optional[str]:
        """
        [针对 STATIC_ASSET]
        保存当前 Tab 显示的内容为文件。
        DrissionPage/Chrome 的下载机制通常是针对 Click 触发的。
        对于已经打开在 Tab 里的资源，我们需要用 CDP 或 requests 把它“捞”下来。
        """
        # 简单实现策略：
        # 1. 如果是 PDF/Image，DrissionPage 有 download 方法，或者用 wget/requests 再请求一次 URL
        # 2. 如果是 JSON/TXT，直接 f.write(tab.ele("tag:body").text)
        pass