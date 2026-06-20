"""
Auto-config — 从入口 HTML 扫描出 baseline export.json。

设计原则（见 design review 讨论）：
- 确定的事（slide selector / canvas 尺寸 / Google Font 导入 / deck-stage reset
  selector / filename）→ 代码直接做，不依赖 LLM。
- 不确定的事（hideSelectors / showJs / delay / fontSwaps 的精确值）→ 代码给
  启发式默认，同时在返回里告诉 agent 该 review 什么，让 LLM 在需要时介入。

输出 ExportReport，由 refresh_preview action 决定怎么把结果给前端 / agent。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# 启发式：nav chrome 候选（CSS selector / class）
# 见到任一就在 hideSelectors 里加，并在 hint 里告诉 agent（让它 review 是否合理）
_NAV_CANDIDATE_SELECTORS = [
    '[data-deck-nav]',
    '.deck-controls',
    '.deck-nav',
    '.deck-dots',
    '.progress-dots',
    '.slide-nav',
    '.slide-controls',
    '.nav-arrow',
    '[aria-label*="slide" i]',
    '[aria-label*="navigation" i]',
]

# 常见 web 字体 host（@font-face 或 Google Fonts CDN 引用）→ 建议考虑 fontSwaps
_CUSTOM_FONT_HOSTS = [
    'fonts.googleapis.com',
    'fonts.gstatic.com',
    'use.typekit.net',
    'use.edgefonts.net',
]


@dataclass
class ExportReport:
    """HTML 扫描结果。

    tier:
        0 = 完全确定（结构 + 字体 + 无动画 + 无 nav）→ refresh_preview 静默
        1 = 有 nav/字体/动画迹象，但 baseline 已经给了合理默认 → 一行提示
        2 = 有具体不确定项，建议 agent review → 明确列出该看什么
        3 = 无法识别 slide 结构 → agent 必须介入（改 HTML 或手写 JSON）
    """

    ok: bool = True
    tier: int = 0
    config: dict = field(default_factory=dict)
    config_path: Optional[str] = None  # 写到了哪里；None = 没写
    hints: List[str] = field(default_factory=list)
    error: Optional[str] = None


def analyze_html_for_export(
    html_path: Path,
    entry_path_rel: str,
    out_dir: Path,
    filename_hint: Optional[str] = None,
) -> ExportReport:
    """扫描 HTML，生成 baseline export.json 到 out_dir/export.json。

    Args:
        html_path: 入口 HTML 的绝对文件路径（必须存在）
        entry_path_rel: 相对 task 目录的入口路径（写进 config 的 entryPath 字段）
        out_dir: export.json 写入目录（一般是 task 的 output/）
        filename_hint: pptx 文件名建议（一般从 task title 派生）

    Returns:
        ExportReport
    """
    report = ExportReport()

    try:
        html_text = html_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        report.ok = False
        report.tier = 3
        report.error = f"读 HTML 失败: {e}"
        return report

    # 用 stdlib html.parser 解析，避免引入 lxml/html5lib 解析器依赖
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_text, "html.parser")

    # ---------------------------------------------------------------
    # 1. 识别 slide 结构（必填字段）
    # ---------------------------------------------------------------
    slides, slide_source = _find_slides(soup)
    if not slides:
        report.ok = False
        report.tier = 3
        report.error = (
            "未识别到 slide 结构。期待以下任一约定：\n"
            "  - <deck-stage> 元素的直接子 <section>（推荐，见 deck-stage.js 约定）\n"
            "  - 带 [data-screen-label] 属性的元素\n"
            "  - <section data-slide=\"...\"> 或 class=\"slide\" 元素\n"
            "你有两个选择：\n"
            "  (a) 改 HTML，给 slide 元素加约定结构（推荐 deck-stage > section）；\n"
            "  (b) 手写 output/export.json，显式指定 slides[].selector 字段。"
        )
        # tier=3 时不写 export.json —— 保持「要么没有，要么对应当前 preview」语义
        return report

    # ---------------------------------------------------------------
    # 2. 读 canvas 尺寸
    # ---------------------------------------------------------------
    width, height, size_source = _read_canvas_size(soup, slides)

    # ---------------------------------------------------------------
    # 3. deck-stage → resetTransformSelector
    # ---------------------------------------------------------------
    deck_stage = soup.find("deck-stage")
    reset_sel = "deck-stage" if deck_stage else None

    # ---------------------------------------------------------------
    # 4. Google Font 导入（确定的）
    # ---------------------------------------------------------------
    google_imports, custom_fonts_seen = _scan_fonts(html_text)

    # ---------------------------------------------------------------
    # 5. nav chrome 候选（启发式，可能要 agent 介入）
    # ---------------------------------------------------------------
    nav_hits = _find_nav_chrome(soup)

    # ---------------------------------------------------------------
    # 6. 动画 / async 内容（启发式，可能要 agent 介入）
    # ---------------------------------------------------------------
    animation_signals = _find_animation_signals(soup, html_text)

    # 单显示 deck 检测：CSS 有 `.slide { display: none }` + `.slide.active` 模式，
    # 默认 editable 模式会捕获失败（hidden slide 走不通），建议改 screenshots 或加 showJs
    single_display = _detect_single_display_deck(html_text, slide_source)

    # ---------------------------------------------------------------
    # 7. filename（从 <title> 派生）
    # ---------------------------------------------------------------
    if not filename_hint:
        title_tag = soup.find("title")
        filename_hint = (
            _sanitize_filename(title_tag.get_text().strip())
            if title_tag and title_tag.get_text().strip()
            else "preview"
        )

    # ---------------------------------------------------------------
    # 组装 config
    # ---------------------------------------------------------------
    config = {
        "_auto": True,  # 标记：refresh_preview 自动生成（agent 手写时去掉此字段）
        "entryPath": entry_path_rel,
        "width": width,
        "height": height,
        "mode": "editable",
        "slides": slides,
        "googleFontImports": google_imports,
        "hideSelectors": list(nav_hits),
        "filename": f"{filename_hint}.pptx",
    }
    if reset_sel:
        config["resetTransformSelector"] = reset_sel
    report.config = config

    # ---------------------------------------------------------------
    # tier 判定
    # ---------------------------------------------------------------
    fully_deterministic = (
        slide_source in ("deck-stage", "data-screen-label")
        and not nav_hits
        and not animation_signals
        and not custom_fonts_seen
        and not single_display
    )
    if fully_deterministic:
        report.tier = 0
    elif single_display:
        # 单显示 deck 必须 agent 介入（否则 editable 模式必崩）
        report.tier = 2
        report.hints.append(
            "检测到单显示 deck 模式 (.slide { display: none } + .active) —— "
            "默认 editable 模式导出会失败（hidden slide 捕获不到）。"
            "两个选择：(a) 把 output/export.json 的 mode 改成 \"screenshots\"（最简单，导出为图片）；"
            "(b) 保持 editable，给每张 slide 加 slides[N].showJs 激活该 slide "
            "（如 `document.querySelectorAll('.slide.active').forEach(e=>e.classList.remove('active')); "
            "document.querySelectorAll('.slide')[N].classList.add('active')`）。"
        )
    elif nav_hits or animation_signals or custom_fonts_seen:
        report.tier = 2
        # 给 agent 具体的 review 提示
        if nav_hits:
            report.hints.append(
                f"检测到 nav chrome 候选 ({', '.join(nav_hits)}) → 默认在导出时隐藏。"
                "若其中有不该隐藏的元素（比如某个内容按钮恰好叫 .nav-arrow），"
                "改 output/export.json 的 hideSelectors 字段。"
            )
        if animation_signals:
            kinds = sorted(set(animation_signals))
            report.hints.append(
                f"检测到动画/异步内容 ({', '.join(kinds)}) → 默认 delay=0、不执行任何 JS。"
                "如果某张 slide 需要播放动画到终态或等待懒加载，"
                "在 output/export.json 对应 slides[N] 里加 showJs（slide 加载后执行的 JS）或 delay（毫秒）。"
            )
        if custom_fonts_seen:
            report.hints.append(
                f"引用了自定义字体 ({', '.join(sorted(custom_fonts_seen))}) → "
                "如果用户机器没装这些字体，pptx 会降级到 fallback 字体。"
                "若要强制替换，在 output/export.json 的 fontSwaps 加 {from, to} 条目。"
            )
    else:
        # slide 结构勉强识别（走 .slide fallback），baseline 仍可用
        report.tier = 1
        report.hints.append(
            f"slide 结构通过 {slide_source} 识别（不是推荐的 deck-stage/data-screen-label）。"
            "导出能跑，但建议改 HTML 用约定结构以获得更稳定的 selector。"
        )

    # ---------------------------------------------------------------
    # 写 export.json（先删后写，确保对应最新 preview）
    # ---------------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)
    config_path = out_dir / "export.json"
    try:
        if config_path.exists():
            config_path.unlink()
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report.config_path = str(config_path)
    except Exception as e:
        # 写盘失败不阻塞 refresh_preview，但要告诉 agent
        report.tier = max(report.tier, 2)
        report.hints.append(f"export.json 写盘失败: {e}（不影响预览，但导出按钮会报错）")
        report.config_path = None

    return report


# ---------------------------------------------------------------------------
# 内部：slide 识别
# ---------------------------------------------------------------------------

def _find_slides(soup) -> tuple[list[dict], str]:
    """返回 (slides 列表, 来源标签)。

    来源优先级：
        1. deck-stage         — <deck-stage> 的直接子 <section>
        2. data-screen-label  — 任意带 [data-screen-label] 的元素
        3. section.slide / [data-slide] — 兜底
    """
    # (a) deck-stage > section（首选约定）
    deck_stage = soup.find("deck-stage")
    if deck_stage:
        sections = [
            s for s in deck_stage.find_all("section", recursive=False)
            if not s.get("aria-hidden", "").lower() == "true"
        ]
        if sections:
            return (
                [
                    {"selector": f"deck-stage > section:nth-child({i + 1})"}
                    for i in range(len(sections))
                ],
                "deck-stage",
            )

    # (b) [data-screen-label]
    labelled = soup.select("[data-screen-label]")
    if labelled:
        # 用 attribute selector 顺序选 nth-of-type 不靠谱（多个不同元素混杂），
        # 直接给每个元素一个 [data-screen-label] selector，外加 nth-of-type 索引
        # 但不同 tag 混杂时 nth-of-type 仍可能不准 —— 给每个 label 唯一 attribute selector
        selectors = []
        for el in labelled:
            lbl = el.get("data-screen-label", "").strip()
            if lbl:
                selectors.append({"selector": f'[data-screen-label="{lbl}"]'})
            else:
                # 空 label，退回 nth-of-type（弱保证）
                idx = labelled.index(el) + 1
                selectors.append({"selector": f'[data-screen-label]:nth-of-type({idx})'})
        return selectors, "data-screen-label"

    # (c) section[data-slide] 或 section.slide
    by_attr = soup.select("section[data-slide]")
    if by_attr:
        return (
            [
                {"selector": f'section[data-slide]:nth-of-type({i + 1})'}
                for i in range(len(by_attr))
            ],
            "section[data-slide]",
        )
    by_class = soup.select("section.slide")
    if by_class:
        return (
            [
                {"selector": f'section.slide:nth-of-type({i + 1})'}
                for i in range(len(by_class))
            ],
            "section.slide",
        )

    return [], "none"


# ---------------------------------------------------------------------------
# 内部：canvas 尺寸
# ---------------------------------------------------------------------------

def _read_canvas_size(soup, slides) -> tuple[int, int, str]:
    """优先级：deck-stage data-width/height → slide[0] inline style width/height → 默认 1920×1080。"""
    # (a) deck-stage data 属性
    deck_stage = soup.find("deck-stage")
    if deck_stage:
        w = _to_int(deck_stage.get("data-width") or deck_stage.get("width"))
        h = _to_int(deck_stage.get("data-height") or deck_stage.get("height"))
        if w and h:
            return w, h, "deck-stage data-*"

    # (b) 第一个 slide 元素的 inline width/height
    # 通过 selector 反查第一个 slide 元素
    first_sel = slides[0].get("selector", "") if slides else ""
    if first_sel:
        try:
            first_el = soup.select(first_sel.replace("nth-child", "nth-of-type").replace("deck-stage > ", "deck-stage > "), limit=1)
            if first_el:
                el = first_el[0]
                style = el.get("style", "") or ""
                w = _parse_px_from_style(style, "width")
                h = _parse_px_from_style(style, "height")
                if w and h:
                    return w, h, "slide[0] inline style"
        except Exception:
            pass

    # (c) HTML 里搜 1920x1080 / 1280x720 这种字面常量（CSS :root --deck-width 之类）
    text = soup.prettify()
    m = re.search(r'(--deck-(?:width|w)|width)\s*:\s*(\d{3,4})\s*px', text)
    n = re.search(r'(--deck-(?:height|h)|height)\s*:\s*(\d{3,4})\s*px', text)
    if m and n:
        w, h = int(m.group(2)), int(n.group(2))
        if 200 <= w <= 8000 and 200 <= h <= 8000:
            return w, h, "css var"

    # (d) 默认
    return 1920, 1080, "default (1920×1080)"


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(str(v).strip().rstrip("px"))
    except (ValueError, TypeError):
        return None


def _parse_px_from_style(style: str, prop: str) -> Optional[int]:
    m = re.search(rf'{prop}\s*:\s*(\d+)\s*px', style)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# 内部：字体扫描
# ---------------------------------------------------------------------------

def _scan_fonts(html_text: str) -> tuple[list[str], set[str]]:
    """扫 Google Font imports。返回 (google_imports 列表, 见到的自定义字体 family 集合)。"""
    google_imports = set()
    custom_fonts = set()

    # <link href="https://fonts.googleapis.com/...">
    for m in re.finditer(
        r'<link[^>]+href=["\']([^"\']*fonts\.googleapis\.com/[^"\']+)["\']',
        html_text, re.IGNORECASE,
    ):
        google_imports.add(m.group(1))
        for fam in _parse_google_font_families(m.group(1)):
            custom_fonts.add(fam)

    # @import url('https://fonts.googleapis.com/...')
    for m in re.finditer(
        r'@import\s+(?:url\()?["\']([^"\']*fonts\.googleapis\.com/[^"\']+)["\']',
        html_text, re.IGNORECASE,
    ):
        google_imports.add(m.group(1))
        for fam in _parse_google_font_families(m.group(1)):
            custom_fonts.add(fam)

    # 其他自定义字体 host（typekit 等）
    for host in _CUSTOM_FONT_HOSTS:
        if host == 'fonts.googleapis.com':
            continue
        if host in html_text:
            custom_fonts.add(host)

    # @font-face 的 family 名
    for m in re.finditer(r'@font-face\s*\{[^}]*?font-family\s*:\s*["\']?([^;"\'\}]+)', html_text, re.IGNORECASE):
        family = m.group(1).strip()
        if family and family.lower() not in ('arial', 'helvetica', 'sans-serif', 'serif'):
            custom_fonts.add(family)

    return sorted(google_imports), custom_fonts


def _parse_google_font_families(url: str) -> list[str]:
    """从 Google Fonts URL 里解析出 family 名。

    'family=Inter:wght@400;700&family=Newsreader' → ['Inter', 'Newsreader']
    """
    families = []
    for m in re.finditer(r'family=([^&]+)', url):
        name = m.group(1).split(':')[0].split('|')[0]
        name = name.replace('+', ' ').strip()
        if name:
            families.append(name)
    return families


# ---------------------------------------------------------------------------
# 内部：nav chrome 候选
# ---------------------------------------------------------------------------

def _find_nav_chrome(soup) -> list[str]:
    """返回需要 hide 的 selector 列表（去重保序）。"""
    hits = []
    seen = set()
    for sel in _NAV_CANDIDATE_SELECTORS:
        try:
            found = soup.select(sel)
        except Exception:
            found = []
        if found:
            if sel not in seen:
                hits.append(sel)
                seen.add(sel)
    return hits


# ---------------------------------------------------------------------------
# 内部：动画 / async 信号
# ---------------------------------------------------------------------------

def _find_animation_signals(soup, html_text: str) -> list[str]:
    """返回检测到的「可能需要 delay / showJs」的信号类型列表。"""
    signals = []

    # <canvas>（很可能 JS 动画）
    if soup.find_all("canvas"):
        signals.append("canvas")

    # <video>
    if soup.find_all("video"):
        signals.append("video")

    # CSS @keyframes
    if re.search(r'@keyframes\s+', html_text):
        signals.append("@keyframes")

    # inline animation: style
    if re.search(r'animation\s*:', html_text):
        signals.append("inline animation")

    # Babel / module script（多文件原型，首屏可能要 JS hydration）
    if soup.find_all("script", attrs={"type": "text/babel"}):
        signals.append("babel-script")

    return signals


# ---------------------------------------------------------------------------
# 内部：单显示 deck 检测
# ---------------------------------------------------------------------------

# 匹配 `.slide { display: none }` / `.slide{display:none}` / 多余空白变体
# （含常见类名变体 .slide / section.slide / [data-screen-label]）
_SINGLE_DISPLAY_PATTERNS = [
    # .slide / section / [data-screen-label] 任一选择器 + display:none
    re.compile(r'\.slide\b[^{]*\{[^}]*display\s*:\s*none', re.IGNORECASE),
    re.compile(r'section\.slide\b[^{]*\{[^}]*display\s*:\s*none', re.IGNORECASE),
    re.compile(r'\[data-screen-label\][^{]*\{[^}]*display\s*:\s*none', re.IGNORECASE),
]


def _detect_single_display_deck(html_text: str, slide_source: str) -> bool:
    """检测 deck 是否用「单 slide 显示」模式（一次只一张可见）。

    信号：CSS 含 `display: none` 隐藏 slide 选择器 + 有 .active / [data-active] 状态类。
    editable 模式在这种结构下会失败 —— 应建议 screenshots 或 showJs。
    """
    has_hide = any(p.search(html_text) for p in _SINGLE_DISPLAY_PATTERNS)
    if not has_hide:
        return False
    # 有状态切换类才确认（避免误报纯装饰性 display:none）
    has_active_state = bool(re.search(r'\.active\b|data-active|classList\.\w+\(\s*["\']active', html_text))
    return has_active_state


# ---------------------------------------------------------------------------
# 内部：filename 清洗
# ---------------------------------------------------------------------------

_BAD_FN_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*\.]')


def _sanitize_filename(name: str) -> str:
    """把 HTML <title> 变成合法 pptx 文件名（去扩展名）。"""
    name = (name or "").strip()
    # 去掉 HTML <title> 里常见的 " - Google Slides" 之类尾巴（保守处理）
    name = re.sub(r'\s*[-–|]\s*$', '', name)
    # 去掉控制字符 / 非法符号
    name = _BAD_FN_CHARS.sub(" ", name)
    name = re.sub(r'\s+', " ", name).strip()
    return name or "preview"
