# AgentMatrix Desktop - UI设计系统

**版本**: v1.0
**最后更新**: 2026-03-18
**状态**: 已实施

---

## 📋 目录

- [设计哲学](#设计哲学)
- [颜色系统](#颜色系统)
- [排版系统](#排版系统)
- [间距系统](#间距系统)
- [边框圆角](#边框圆角)
- [阴影系统](#阴影系统)
- [动画与过渡](#动画与过渡)
- [布局规范](#布局规范)
- [组件规范](#组件规范)
- [图标系统](#图标系统)
- [无障碍设计](#无障碍设计)
- [响应式断点](#响应式断点)
- [暗色模式](#暗色模式)
- [代码实现示例](#代码实现示例)

---

## 设计哲学

### 核心原则

#### 1. 清晰胜于复杂 (Clarity Over Complexity)
- 每个元素都有其目的
- 移除而非添加
- 让内容有呼吸空间

#### 2. 精致的商务美学 (Refined Business Aesthetic)
- 专业而不冷漠
- 通过细节传递温度
- 通过克制传递自信

#### 3. 视觉层次 (Visual Hierarchy)
- 清晰的信息架构
- 有目的的对比
- 引导视线流动

#### 4. 响应式与自适应 (Responsive & Adaptive)
- 流畅的布局
- 优雅的降级
- 性能优先的动画

### 设计灵感来源

**结构灵感**:
- Microsoft Outlook for Mac (布局效率)
- Apple Mail (精致和打磨)
- Notion (清晰和目的性)

**视觉语言**:
- Apple's Human Interface Guidelines
- Swiss/International Typographic Style
- 现代日式极简设计

### 我们避免的陈词滥调

❌ **避免使用**:
- 通用的 Material Design 阴影 (elevation 1-8)
- 标准的 8px/12px/16px 圆角
- 重的渐变叠加
- 过度使用的圆角卡片
- 通用的蓝色主色

✅ **我们的做法**:
- 微妙、有目的的阴影
- 刻意的圆角刻度 (6px, 10px, 14px, 18px)
- 颜色作为强调，而非装饰
- 有目的的圆角和锐利边缘
- 复杂的色彩调色板

---

## 颜色系统

### 主色调 (Primary Colors)

我们的主色调是精致且中性的。

```css
--primary-50:  #EEF2FF
--primary-100: #E0E7FF
--primary-200: #C7D2FE
--primary-300: #A5B4FC
--primary-400: #818CF8
--primary-500: #6366F1  /* ← 主要品牌色 */
--primary-600: #4F46E5
--primary-700: #4338CA
--primary-800: #3730A3
--primary-900: #312E81
```

**使用场景**:
- 主要操作、CTA按钮
- 激活状态
- 重要指示器
- 链接（需要时）

### 中性色 (Neutral Colors)

温暖的中性色调，比纯灰色更柔和。

```css
--neutral-50:  #FAFAF9
--neutral-100: #F5F5F4
--neutral-200: #E7E5E4
--neutral-300: #D6D3D1
--neutral-400: #A8A29E
--neutral-500: #78716C
--neutral-600: #57534E
--neutral-700: #44403C
--neutral-800: #292524
--neutral-900: #1C1917
```

**语义映射**:
- 背景: 50, 100, 200
- 边框: 200, 300
- 文本: 500, 600, 700, 800
- UI元素: 300, 400

### 语义色 (Semantic Colors)

为特定UI状态设计的目的性颜色。

```css
/* 成功 - Success */
--success-50:  #ECFDF5
--success-500: #10B981
--success-700: #047857

/* 警告 - Warning */
--warning-50:  #FFFBEB
--warning-500: #F59E0B
--warning-700: #B45309

/* 错误 - Error */
--error-50:   #FEF2F2
--error-500:  #EF4444
--error-700:  #B91C1C

/* 信息 - Info */
--info-50:    #EFF6FF
--info-500:   #3B82F6
--info-700:   #1D4ED8
```

**使用场景**:
- **Success**: 操作成功、完成状态
- **Warning**: Agent问题、需要用户注意
- **Error**: 错误提示、失败状态
- **Info**: 信息提示、帮助文本

---

## 排版系统

### 字号层级

```css
--font-xs:    0.75rem   (12px)   /* 说明文字 */
--font-sm:    0.875rem  (14px)   /* 正文 */
--font-base:  1rem      (16px)   /* 基础字号 */
--font-lg:    1.125rem  (18px)   /* 大号文字 */
--font-xl:    1.25rem   (20px)   /* 标题3 */
--font-2xl:   1.5rem    (24px)   /* 标题2 */
--font-3xl:   1.875rem  (30px)   /* 标题1 */
```

### 字体家族

```css
/* 无衬线字体 - 用于UI文本 */
--font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Text",
             "Segoe UI", "Helvetica Neue", Arial,
             "PingFang SC", "Microsoft YaHei", sans-serif;

/* 显示字体 - 用于标题 */
--font-display: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                 "Segoe UI", "Helvetica Neue", Arial,
                 "PingFang SC", "Microsoft YaHei", sans-serif;

/* 等宽字体 - 用于代码 */
--font-mono: "SF Mono", "Menlo", "Monaco", "Cascadia Code",
             "Courier New", monospace;
```

### 字重规范

```css
--font-normal:   400  /* 常规文本 */
--font-medium:   500  /* 强调文本、按钮 */
--font-semibold: 600  /* 小标题 */
--font-bold:     700  /* 大标题 */
```

### 排版层次

| 层级 | 字号 | 字重 | 行高 | 用途 |
|------|------|------|------|------|
| Display | 30px | Semibold | 1.2 | 大标题、Hero标题 |
| Heading 1 | 24px | Semibold | 1.3 | 页面标题 |
| Heading 2 | 18px | Medium | 1.4 | 区域标题 |
| Body | 14px | Normal | 1.5 | 正文内容 |
| Caption | 12px | Normal | 1.5 | 元数据、时间戳 |

---

## 间距系统

### 基础间距刻度

基于 4px 基础单位的间距系统。

```css
--spacing-0:   0
--spacing-1:   0.25rem  (4px)
--spacing-2:   0.5rem   (8px)
--spacing-3:   0.75rem  (12px)
--spacing-4:   1rem     (16px)
--spacing-5:   1.25rem  (20px)
--spacing-6:   1.5rem   (24px)
--spacing-8:   2rem     (32px)
--spacing-10:  2.5rem   (40px)
--spacing-12:  3rem     (48px)
--spacing-16:  4rem     (64px)
--spacing-20:  5rem     (80px)
```

### 常用间距模式

```css
--spacing-xs:   var(--spacing-1)   (4px)   - 紧密间距
--spacing-sm:   var(--spacing-2)   (8px)   - 紧凑间距
--spacing-md:   var(--spacing-4)   (16px)  - 默认间距
--spacing-lg:   var(--spacing-6)   (24px)  - 舒适间距
--spacing-xl:   var(--spacing-8)   (32px)  - 宽松间距
--spacing-2xl:  var(--spacing-12)  (48px)  - 特宽间距
```

**使用场景**:
- **xs (4px)**: 卡片内元素间距、图标与文字间距
- **sm (8px)**: 紧凑列表项间距
- **md (16px)**: 默认padding、表单元素间距
- **lg (24px)**: 区域间距、卡片间距
- **xl (32px)**: 大区域间距
- **2xl (48px)**: 页面级间距

---

## 边框圆角

### 圆角刻度

刻意的圆角刻度，避免常见值。

```css
--radius-sm:   6px     /* 小元素、标签 */
--radius-md:   10px    /* 按钮、输入框、卡片 */
--radius-lg:   14px    /* 大卡片、模态框 */
--radius-xl:   18px    /* Hero卡片、面板 */
--radius-full: 9999px  /* 胶囊、徽章、头像 */
```

### 使用场景

| 圆角值 | 使用场景 |
|--------|---------|
| 6px | Badge/Tag、小按钮 |
| 10px | 按钮、输入框、卡片（默认） |
| 14px | 大卡片、对话框 |
| 18px | Hero元素、大面板 |
| 9999px | 头像、胶囊按钮 |

---

## 阴影系统

### 阴影层级

微妙、有目的的阴影。高程是暗示而非声明。

```css
--shadow-xs:  0 1px 2px rgba(0, 0, 0, 0.05)
--shadow-sm:  0 1px 3px rgba(0, 0, 0, 0.08),
              0 1px 2px rgba(0, 0, 0, 0.04)
--shadow-md:  0 4px 6px rgba(0, 0, 0, 0.07),
              0 2px 4px rgba(0, 0, 0, 0.06)
--shadow-lg:  0 10px 15px rgba(0, 0, 0, 0.08),
              0 4px 6px rgba(0, 0, 0, 0.05)
--shadow-xl:  0 20px 25px rgba(0, 0, 0, 0.08),
              0 10px 10px rgba(0, 0, 0, 0.04)
```

### 使用场景

| 阴影 | 使用场景 |
|------|---------|
| shadow-xs | Hover状态、微妙深度 |
| shadow-sm | 卡片、面板 |
| shadow-md | 下拉菜单、弹出框 |
| shadow-lg | 模态框、大面板 |
| shadow-xl | Hero元素、CTA |

---

## 动画与过渡

### 时长规范

```css
--duration-fast:   150ms   /* 快速反馈 */
--duration-base:   200ms   /* 基础过渡 */
--duration-slow:   300ms   /* 慢速过渡 */
--duration-slower: 500ms   /* 复杂动画 */
```

### 缓动函数

```css
--ease-out:     cubic-bezier(0, 0, 0.2, 1)
--ease-in-out:  cubic-bezier(0.4, 0, 0.2, 1)
--ease-spring:  cubic-bezier(0.175, 0.885, 0.32, 1.275)
```

### 常用动画

#### Fade In (淡入)
```css
opacity: 0 → 1
duration: 200ms
easing: ease-out
```

#### Slide In (滑入)
```css
transform: translateY(-8px) → translateY(0)
opacity: 0 → 1
duration: 250ms
easing: ease-out
```

#### Scale Press (按压缩放)
```css
transform: scale(1) → scale(0.96)
duration: 100ms
easing: ease-out
```

---

## 布局规范

### 固定宽度组件

```css
/* View Selector (左侧视图选择器) */
--view-selector-width: 72px
--view-selector-collapsed: 72px

/* Session List (会话列表) */
--session-list-width: 280px
--session-list-collapsed: 280px

/* Email List (邮件列表) */
--email-list-min-width: 400px
```

### 全局布局

```css
--app-max-width: 100%
--app-padding: 0
```

**原则**:
- 应用内容占据整个可见宽度
- 两侧无留白
- 无中心约束

### 视图结构

```
┌─────────────────────────────────────────────┐
│  View Selector │  Session List │ Email List │
│    (72px)      │    (280px)    │  (flex)    │
└─────────────────────────────────────────────┘
```

---

## 组件规范

### 按钮

#### Primary Button (主按钮)
```css
height: 40px
padding: 0 20px
background: var(--primary-500)
color: white
border-radius: var(--radius-md)
font: 14px Medium
```

#### Secondary Button (次要按钮)
```css
height: 40px
padding: 0 20px
background: var(--neutral-100)
color: var(--neutral-700)
border-radius: var(--radius-md)
font: 14px Medium
border: 1px solid var(--neutral-200)
```

#### Ghost Button (幽灵按钮)
```css
height: 40px
padding: 0 20px
background: transparent
color: var(--neutral-600)
border-radius: var(--radius-md)
font: 14px Medium
```

### 输入框

#### Text Input (文本输入)
```css
height: 40px
padding: 0 16px
background: var(--neutral-50)
border: 1px solid var(--neutral-200)
border-radius: var(--radius-md)
font: 14px Normal

focus: border-color: var(--primary-300)
```

#### Search Input (搜索输入)
```css
height: 36px
padding: 0 16px 0 40px
background: var(--neutral-50)
border: 1px solid var(--neutral-200)
border-radius: var(--radius-md)
icon-position: left, 12px
```

### 卡片

#### Default Card (默认卡片)
```css
padding: 16px
background: white
border: 1px solid var(--neutral-200)
border-radius: var(--radius-md)
box-shadow: var(--shadow-sm)
```

#### Email Card (邮件卡片)
```css
padding: 12px 16px
background: white
border: 1px solid var(--neutral-200)
border-radius: var(--radius-md)
hover: var(--shadow-md)
```

### Badge/Tag (标签/徽章)

```css
height: 20px
padding: 0 8px
border-radius: 6px
font: 11px Medium
```

### Session Item (会话项)

```css
height: 56px
padding: 12px 16px
border-radius: 10px
gap: 12px

avatar: 32px
title: 14px Semibold
subtitle: 12px Normal
```

---

## 图标系统

### 图标库

- **主要**: Tabler Icons (ti-*)
- **备用**: Heroicons, Lucide

### 图标尺寸

```css
--icon-xs:  16px
--icon-sm:  18px
--icon-md:  20px
--icon-lg:  24px
--icon-xl:  28px
```

### 使用原则

- 有目的地使用图标，而非装饰
- 保持 2px 描边宽度
- 使用圆形/圆角变体增加温暖感
- 图标+文字组合时左对齐

---

## 无障碍设计

### 颜色对比度

- **WCAG AA**: 正常文本 4.5:1
- **WCAG AA**: 大文本 3:1
- **WCAG AAA**: 正常文本 7:1 (推荐)

### 焦点指示器

```css
:focus-visible {
  outline: 2px solid var(--primary-500);
  outline-offset: 2px;
}
```

### 键盘导航

- Tab顺序: 逻辑清晰
- 跳过链接: 可用
- 焦点陷阱: 模态框
- Escape键: 关闭/取消

---

## 响应式断点

```css
--breakpoint-sm:  640px
--breakpoint-md:  768px
--breakpoint-lg:  1024px
--breakpoint-xl:  1280px
--breakpoint-2xl: 1536px
```

**注意**: Desktop应用主要针对 1024px+ 屏幕

---

## 暗色模式

### 启用方式

#### 自动（系统偏好）
应用自动遵循系统的暗色模式偏好。

#### 手动切换
添加 `.dark` 类到 HTML 元素:

```javascript
// 启用暗色模式
document.documentElement.classList.add('dark')

// 禁用暗色模式
document.documentElement.classList.remove('dark')
```

### 暗色模式颜色

```css
.dark {
  /* 背景 */
  --bg-primary:   #0A0A0A
  --bg-secondary: #141414
  --bg-tertiary:  #1C1C1E
  --bg-elevated:  #2C2C2E

  /* 文本 */
  --text-primary:   #FFFFFF
  --text-secondary: #EBEBF5
  --text-tertiary:  rgba(235, 235, 245, 0.6)
  --text-quaternary: rgba(235, 235, 245, 0.3)

  /* 中性色反转 */
  --neutral-50:  #1C1C1E
  --neutral-100: #2C2C2E
  --neutral-200: #3A3A3C
  /* ... 其他中性色 */

  /* 阴影加深 */
  --shadow-xs:  0 1px 2px rgba(0, 0, 0, 0.3)
  --shadow-sm:  0 1px 3px rgba(0, 0, 0, 0.4), 0 1px 2px rgba(0, 0, 0, 0.3)
  /* ... 其他阴影 */
}
```

### 适配原则

- 稍微降低饱和度以减少眼睛疲劳
- 增加文本对比度
- 减少白色背景
- 更柔和的阴影

---

## 代码实现示例

### 在Vue组件中使用设计Token

```vue
<template>
  <button class="my-button">
    Click me
  </button>
</template>

<style scoped>
.my-button {
  height: var(--button-height-md);
  padding: var(--button-padding-md);
  background: var(--primary-500);
  color: white;
  border-radius: var(--radius-md);
  font-weight: var(--font-medium);
  transition: all var(--duration-base) var(--ease-out);
}

.my-button:hover {
  background: var(--primary-600);
  box-shadow: var(--shadow-md);
}

.my-button:active {
  transform: scale(0.96);
}
</style>
```

### 创建卡片组件

```vue
<template>
  <div class="card">
    <h3 class="card__title">{{ title }}</h3>
    <p class="card__content">{{ content }}</p>
  </div>
</template>

<style scoped>
.card {
  padding: var(--card-padding-md);
  background: white;
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.card__title {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin-bottom: var(--spacing-sm);
}

.card__content {
  font-size: var(--font-sm);
  color: var(--neutral-600);
  line-height: var(--leading-relaxed);
}
</style>
```

### 响应式布局

```vue
<template>
  <div class="container">
    <!-- Content -->
  </div>
</template>

<style scoped>
.container {
  width: 100%;
  padding: var(--spacing-md);
}

@media (min-width: 1024px) {
  .container {
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--spacing-xl);
  }
}
</style>
```

---

## 相关资源

- **设计Token文件**: `agentmatrix-desktop/src/styles/tokens.css`
- **全局样式**: `agentmatrix-desktop/src/styles/global.css`
- **组件参考**: [component-reference.md](./component-reference.md)
- **交互设计**: [ui-interaction-flows.md](./ui-interaction-flows.md)

---

## 维护说明

### 更新原则

1. **设计Token优先**: 所有设计值都应使用CSS变量
2. **一致性优先**: 保持跨组件的一致性
3. **文档同步**: 任何设计变更都应更新本文档

### 版本历史

**v1.0** (2026-03-18)
- 初始版本
- 完整的设计系统定义
- 从 ui-design-guide.md 和 ui-quick-reference.md 提取内容

---

**文档维护者**: AgentMatrix Team
**下次审查**: 每季度
