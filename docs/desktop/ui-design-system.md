# MERIDIAN — AgentMatrix 设计语言

**版本**: v2.0 | **更新**: 2026-03-21 | **状态**: 已实施

---

## 设计哲学

MERIDIAN 为 AgentMatrix「分布式认知调度系统」而生。气质不是 SaaS 仪表盘，而是**情报档案室**——温暖、克制、精确。

**四条原则：**

1. **编辑优先，装饰为零** — 区分层级靠边框线和留白，而非阴影和渐变。
2. **衬线承载思想，无衬线承载操作** — 标题/邮件正文用衬线（Source Serif 4 / Noto Serif SC），按钮/导航用系统无衬线，代码用等宽。
3. **朱砂一点，克制使用** — Vermillion (#C23B22) 仅用于：选中左边框、焦点边框、强调按钮、思考进度条。
4. **中英文同等对待** — 衬线栈含 Noto Serif SC，无衬线栈含 PingFang SC / Noto Sans SC。中文行高 1.8。

---

## 色彩

### Parchment（羊皮纸）— 背景

| Token | 值 | 用途 |
|-------|-----|------|
| `--parchment-50` | #FDFCF9 | 页面背景 |
| `--parchment-100` | #F7F5F0 | 侧边栏 |
| `--parchment-200` | #EDE9E1 | 悬停态 |
| `--parchment-300` | #DBD5C9 | 边框线 |

### Ink（墨）— 文本

| Token | 值 | 用途 |
|-------|-----|------|
| `--ink-900` | #1A1A1A | 标题 |
| `--ink-700` | #3D3D3D | 正文 |
| `--ink-500` | #6B6B6B | 次要文本 |
| `--ink-400` | #8A8A8A | 禁用态 |
| `--ink-300` | #ABABAB | 图标 |
| `--ink-200` | #D4D4D4 | 浅边框 |

### Accent（朱砂）— 强调

| Token | 值 | 用途 |
|-------|-----|------|
| `--accent` | #C23B22 | 主强调色 |
| `--accent-hover` | #A33220 | 悬停态 |
| `--accent-muted` | #E8C4B8 | 强调色背景 |

### Semantic（语义）

| Token | 含义 | 值 |
|-------|------|-----|
| `--verdant` / `--verdant-muted` | 成功/运行 | #2D6A4F / #B7E4C7 |
| `--amber` / `--amber-muted` | 警告/待处理 | #B45309 / #FDE68A |
| `--fault` / `--fault-muted` | 错误/停止 | #9B2C2C / #FED7D7 |
| `--azure` / `--azure-muted` | 信息/链接 | #2B6CB0 / #BEE3F8 |

---

## 排版

| 角色 | Token | 字体 |
|------|-------|------|
| 衬线 | `--font-serif` | Source Serif 4 → Noto Serif SC → Songti SC → Georgia |
| 无衬线 | `--font-sans` | 系统字体 + PingFang SC + Noto Sans SC |
| 等宽 | `--font-mono` | SF Mono → Menlo → Cascadia Code |

**规则**：衬线=h1-h6、邮件正文、思考内容。无衬线=按钮、标签、导航。等宽=代码、Action Readout。

**编辑标签**：取代药丸 badge。小号大写字母 + 字间距：`font-variant: small-caps; letter-spacing: 0.1em; text-transform: uppercase; font-size: 11px`

---

## 视觉语言 — 七种模式

1. **镌刻线** — 水平线分割，非阴影
2. **朱砂边** — 左侧 3px 朱砂边框标记选中/悬停
3. **编辑标签** — 小号大写字母，非药丸形
4. **底线输入** — 只有底部 1px 边框，聚焦变朱砂
5. **墨底按钮** — 主按钮：#1A1A1A 背景 + 羊皮纸色文字，大写有字间距
6. **思考条** — 朱砂 2px 进度条往复填充，取代旋转加载器
7. **调度头** — 日期行，衬线 ink-400，两侧延伸水平线

---

## 组件速查

| 组件 | MERIDIAN 模式 |
|------|-------------|
| Email 卡片 | 无阴影，2px 圆角，左边框朱砂强调 |
| Session 列表项 | 左边框朱砂标记选中态 |
| 按钮 | 墨底主按钮，朱砂强调，线框次要 |
| 输入框 | 底线式，朱砂焦点 |
| 对话框 | 无毛玻璃，最小阴影，衬线标题 |
| 状态指示器 | 实心圆点，无发光 |
| 徽章/标签 | 编辑小写体 |
| 加载 | 思考进度条 |

---

## 暗色模式

`<html class="dark">` 切换。Parchment ↔ Ink 反转。朱砂在暗色更亮（#E05A42）。

## 中文排版

衬线回退：Source Serif 4 → Noto Serif SC → Songti SC → SimSun。中文行高 1.8。

## 演示

打开 `agentmatrix-desktop/meridian-demo/index.html`。源码是唯一参考，本文档是地图。
