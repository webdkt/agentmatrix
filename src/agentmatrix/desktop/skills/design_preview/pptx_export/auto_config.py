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


# Canonical export.json schema 摘要 —— 在 refresh_preview 提示 agent 时引用，
# 让 LLM 手写 export.json 时字段名有 anchor。完整版见 design agent profile 的
# 「PPT 导出」章节。
EXPORT_JSON_SCHEMA_HINT = """\
canonical schema（字段名严格匹配）:
  width, height            # canvas px，顶层字段
  slides: [{selector, showJs?, delay?}]
  mode: "editable" | "screenshots"
  googleFontImports: [...]
  hideSelectors: [...]      # 导出时隐藏的 selector
  resetTransformSelector?: "deck-stage"
  fontSwaps?: [{from, to}]
  filename?: "my-deck.pptx"\
"""


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
    out_dir: Path,
    filename_hint: Optional[str] = None,
) -> ExportReport:
    """扫描 HTML，生成 baseline export.json 到 out_dir/export.json。

    Args:
        html_path: 入口 HTML 的绝对文件路径（必须存在）
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
        report.error = _diagnose_non_deck_stage(soup, html_text)
        # tier=3 时清掉 stale export.json —— 保持「要么没有，要么对应当前 preview」
        # 语义。之前成功跑过的 export.json 若留着，会被 export 按钮当当前 preview
        # 的配置使用，但实际入口已换 / 已坏 → 用户点导出会拿到误导性错误。
        _try_unlink_export_json(out_dir)
        return report

    # ---------------------------------------------------------------
    # 1b. 验证 deck-stage 是真正的 Web Component（不是手写假的）
    # ---------------------------------------------------------------
    # _find_slides 只看 <deck-stage> 字面量，但 agent 可能在 HTML 里写了
    # <deck-stage> 标签 + 内联手写 class DeckStage {...}，没调
    # customElements.define('deck-stage', ...)。这种情况下元素是 HTMLUnknownElement，
    # 没有 .goTo() API —— export 时 showJs 会崩。这里提前发现，让 agent 在
    # refresh_preview 返回里就看到错误。
    runtime_err = _verify_deck_stage_runtime(soup, html_text)
    if runtime_err:
        report.ok = False
        report.tier = 3
        report.error = runtime_err
        _try_unlink_export_json(out_dir)
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
    # 6. 动画 / async 内容（deck-stage 模式下动画由 [data-deck-active] gate，
    #    capture 时当前 slide 必然 active，所以这些信号不影响 export 正确性，
    #    仅作为给 agent 的 review hint）
    # ---------------------------------------------------------------
    animation_signals = _find_animation_signals(soup, html_text)

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
    # deck-stage 自带的 chrome（thumbnail rail / overlay / fullscreen 按钮等）
    # 都带 data-omelette-chrome 属性，导出时统一隐藏
    hide = list(nav_hits)
    if "[data-omelette-chrome]" not in hide:
        hide.append("[data-omelette-chrome]")

    config = {
        "_auto": True,  # 标记：refresh_preview 自动生成（agent 手写时去掉此字段）
        "width": width,
        "height": height,
        "mode": "editable",
        "slides": slides,
        "googleFontImports": google_imports,
        "hideSelectors": hide,
        "filename": f"{filename_hint}.pptx",
    }
    if reset_sel:
        config["resetTransformSelector"] = reset_sel
    report.config = config

    # ---------------------------------------------------------------
    # tier 判定 —— deck-stage 已经保证 export 能跑，tier 只反映 "要不要 agent review"
    # ---------------------------------------------------------------
    if not nav_hits and not animation_signals and not custom_fonts_seen:
        report.tier = 0
    else:
        report.tier = 2
        if nav_hits:
            report.hints.append(
                f"检测到 nav chrome 候选 ({', '.join(nav_hits)}) → 默认在导出时隐藏。"
                "若其中有不该隐藏的元素（比如某个内容按钮恰好叫 .nav-arrow），"
                "改 output/export.json 的 hideSelectors 字段。"
            )
        if animation_signals:
            kinds = sorted(set(animation_signals))
            report.hints.append(
                f"检测到动画/异步内容 ({', '.join(kinds)}) → deck-stage 下 slide 动画 "
                "gate 在 [data-deck-active] 上，capture 时当前 slide 必然 active，"
                "动画会播放到终态。若某张 slide 需要更长 settle，"
                "在 output/export.json 对应 slides[N] 里加 delay（毫秒）。"
            )
        if custom_fonts_seen:
            report.hints.append(
                f"引用了自定义字体 ({', '.join(sorted(custom_fonts_seen))}) → "
                "如果用户机器没装这些字体，pptx 会降级到 fallback 字体。"
                "若要强制替换，在 output/export.json 的 fontSwaps 加 {from, to} 条目。"
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

    只识别 <deck-stage> 的直接子 <section> —— 这是本环境 PPT 导出工具
    唯一支持的 deck 结构（参考 baoyu-design export-as-pptx-editable.md）。

    其他结构（data-screen-label / section.slide / section[data-slide]）一律
    不识别，让 main flow 走 tier 3 报错路径，要求 agent 改用 deck-stage。

    为什么只支持 deck-stage：
        export 工具依赖 deck-stage 的两个约定 ——
        (1) runtime 把 data-deck-active 属性加到当前 slide（_applyIndex）
        (2) 公开 API goTo(N) 切换 slide（line 1944）
        这两者结合，让 export.json 能机械生成：
            selector = "deck-stage > [data-deck-active]"  # 所有 slide 共用
            showJs   = "document.querySelector('deck-stage').goTo(N)"
        agent 自写的 deck（opacity/.active/display:none 切换等）class 名
        千变万化，无法可靠推断切换逻辑 —— 强约束 deck-stage 是唯一可行方案。
    """
    deck_stage = soup.find("deck-stage")
    if deck_stage:
        sections = [
            s for s in deck_stage.find_all("section", recursive=False)
            if not s.get("aria-hidden", "").lower() == "true"
        ]
        if sections:
            # 所有 slide 共享同一个 selector —— runtime 时 data-deck-active
            # 只在当前 slide 上（_applyIndex 控制），showJs 通过 goTo(N) 切换
            return (
                [
                    {
                        "selector": "deck-stage > [data-deck-active]",
                        "showJs": f"document.querySelector('deck-stage').goTo({i})",
                    }
                    for i in range(len(sections))
                ],
                "deck-stage",
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
# 内部：非 deck-stage deck 诊断（tier 3 报错用）
# ---------------------------------------------------------------------------

def _verify_deck_stage_runtime(soup, html_text: str) -> Optional[str]:
    """验证 <deck-stage> 是真正的 Web Component，不是手写假的。

    检测三种真正的 deck-stage 加载方式：
    1. <script src="...deck-stage.js">（外部脚本，文件名必须是 deck-stage.js）
    2. inline customElements.define('deck-stage', ...)（inline 注册）
    3. inline <script type="module"> 含 customElements.define('deck-stage'

    如果 HTML 有 <deck-stage> 标签但三种都没有，说明 agent 手写了假的实现
    （常见模式：内联 class DeckStage {...} + new DeckStage(el)，方法名常是
    goToSlide 而非 goTo）—— 元素是 HTMLUnknownElement，没有 .goTo() API。

    返回 None 表示 OK，返回 str 表示错误描述（用于 tier 3 报错）。
    """
    # 必须先有 <deck-stage> 元素才做这个检查；否则跳过
    if not soup.find("deck-stage"):
        return None

    # (1) 外部脚本 src 含 deck-stage.js（路径任意，文件名必须匹配）
    for script in soup.find_all("script"):
        src = script.get("src", "") or ""
        # 去掉 query/hash 后比对文件名
        src_file = src.split("?")[0].split("#")[0].rstrip("/")
        if src_file.endswith("/deck-stage.js") or src_file == "deck-stage.js":
            return None

    # (2) / (3) inline script 含 customElements.define('deck-stage'
    if re.search(
        r"customElements\s*\.\s*define\s*\(\s*['\"]deck-stage['\"]",
        html_text,
    ):
        return None

    # 都没有 —— agent 手写了假的。生成具体诊断。
    # 尝试猜 agent 是怎么实现的，给最针对性的修法
    has_inline_deck_class = bool(
        re.search(r"\bclass\s+DeckStage\b", html_text)
    )
    fake_hint = ""
    if has_inline_deck_class:
        # 进一步猜方法名（常见：goToSlide / showSlide / setCurrentSlide）
        m = re.search(
            r"\bclass\s+DeckStage\b[\s\S]{0,2000}?\b(go\w*Slide|show\w*Slide|set\w*Slide)\s*\(",
            html_text,
        )
        if m:
            fake_hint = (
                f"\n\n检测到手写的 class DeckStage，方法名可能是 {m.group(1)}(N) —— "
                "这跟 deck-stage.js 的 goTo(N) 约定不一致，export 工具用不了。"
            )

    return (
        "检测到 <deck-stage> 标签，但 HTML 既没有 <script src=\"deck-stage.js\">，"
        "也没有 inline customElements.define('deck-stage', ...) —— "
        "说明 agent 手写了假的 deck-stage 实现（例如内联 class DeckStage + new DeckStage(el)），"
        "<deck-stage> 元素其实是 HTMLUnknownElement，没有 .goTo(N) API，"
        "export 时 document.querySelector('deck-stage').goTo(0) 会报 \"not a function\"。"
        + fake_hint
        +
        "\n\n修法（二选一，推荐第一个）：\n"
        "  (a) cp ~/starter-components/deck-stage.js ~/current_task/output/，\n"
        "      HTML 里加 <script src=\"deck-stage.js\"></script>（vanilla JS，不是 type=\"text/babel\"），\n"
        "      然后删掉自己写的 class DeckStage 和 new DeckStage(...) —— 真正的 Web Component\n"
        "      会自动 upgrade 所有 <deck-stage> 元素，不需要手动 new。\n"
        "  (b) 在 inline <script> 里加 customElements.define('deck-stage', DeckStage)，\n"
        "      且 class 方法名必须叫 goTo(N)（不是 goToSlide）—— 但这只是凑活，\n"
        "      你 reimplement 的缩放/键盘/thumbnail/print 逻辑多半有 bug，还是用 (a)。"
        "\n\n改完调 refresh_preview 让 auto_config 重新扫，会自动生成对的 export.json。"
    )


def _try_unlink_export_json(out_dir: Path) -> None:
    """tier 3 时清掉 stale export.json，不抛异常。"""
    try:
        p = out_dir / "export.json"
        if p.exists():
            p.unlink()
    except Exception:
        pass


def _diagnose_non_deck_stage(soup, html_text: str) -> str:
    """对没有 <deck-stage> 的 HTML 给出针对性错误信息。

    检测三类常见违反约束的情况：
    1. React/babel 渲染（slide 内容由 JS 生成，静态扫描看不到）
    2. 手写 deck（有 section.slide / [data-screen-label] 等信号，但没 deck-stage）
    3. 完全没有 slide 结构（landing page / 长文档等非 deck 页面）

    所有情况都要求 agent 改 HTML 用 deck-stage，不兜底允许手写 export.json ——
    因为 agent 自写切换逻辑（class 名千变万化）无法可靠 export。
    """
    has_babel = bool(soup.find_all("script", attrs={"type": "text/babel"}))
    has_empty_root = bool(soup.find("div", id="root")) and not soup.find("div", id="root").get_text(strip=True)
    has_section_slide = bool(soup.select("section.slide"))
    has_section_data_slide = bool(soup.select("section[data-slide]"))
    has_data_screen_label = bool(soup.select("[data-screen-label]"))

    common_hint = (
        "本环境的 PPT 导出工具只支持 deck-stage 结构（详见 ~/built-in-skills/make-a-deck.md）。"
        "deck-stage 自带 goTo(N) API + data-deck-active 切换约定，"
        "auto_config 才能机械生成 selector 和 showJs。\n\n"
        "改造步骤：\n"
        "  1. cp ~/starter-components/deck-stage.js 到 ~/current_task/output/\n"
        "  2. HTML 里 <script src=\"deck-stage.js\"></script> 加载（vanilla JS，非 JSX）\n"
        "  3. 把所有 slide 写成 <deck-stage width=\"1920\" height=\"1080\"> 的直接子 <section>，\n"
        "     每个 <section data-label=\"...\"> 是一张 slide\n"
        "  4. slide 内容写静态 HTML —— 不要用 React/babel 渲染 slide 内容，\n"
        "     静态 HTML 用户能直接编辑、export 工具能稳定 capture\n"
        "  5. 调 refresh_preview 让 auto_config 重新扫，会自动生成对的 export.json"
    )

    if has_babel or has_empty_root:
        return (
            "未识别到 <deck-stage> slide 结构。检测到 React/babel 渲染（script[type=\"text/babel\"]"
            f"{' + 空 <div id=\"root\">' if has_empty_root else ''}）—— slide 内容由 JS 在 runtime 生成，\n"
            "auto_config 静态扫描看不到任何 slide，export 工具也没法可靠 capture。\n\n"
            "如果 slide 内容是静态的（文字 / 图 / 表格 / 布局），必须改成静态 HTML 写在\n"
            "<deck-stage> 的 <section> 里 —— 这也是 make-a-deck.md 的核心约束：「能静态就静态，\n"
            "React 仅限 slide 真正需要交互（图表动画 / live demo）时使用，且 slide 容器仍是\n"
            "静态 <section>，交互组件嵌在内部」。\n\n"
            + common_hint
        )

    if has_section_slide or has_section_data_slide or has_data_screen_label:
        signals = []
        if has_section_slide: signals.append("section.slide")
        if has_section_data_slide: signals.append("section[data-slide]")
        if has_data_screen_label: signals.append("[data-screen-label]")
        return (
            f"检测到 slide 信号 ({', '.join(signals)})，但没有 <deck-stage> 容器 —— "
            "这是手写的 deck 结构，本环境不支持。\n\n"
            "为什么禁止：手写 deck 的 slide 切换逻辑千变万化（.active + opacity / "
            "display:none + .show / [data-active] / inline style 等），auto_config 无法可靠\n"
            "推断切换 class 名和加在哪个元素。deck-stage 把这一切标准化为 goTo(N) + \n"
            "data-deck-active，才能机械生成对的 export.json。\n\n"
            + common_hint
        )

    return (
        "未识别到 slide 结构 —— 这看起来不是 slide-structured deck（可能是 landing page / \n"
        "dashboard / 长文档）。PPT 导出工具只支持 slide-structured deck，不支持任意 HTML。\n\n"
        "两个选择：\n"
        "  (a) 把内容重新组织成 deck-stage 结构（推荐，参考 ~/built-in-skills/make-a-deck.md）；\n"
        "  (b) 告诉用户这个页面不是 deck，无法导出 PPT。"
    )


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
