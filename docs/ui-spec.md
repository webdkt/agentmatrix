# AgentMatrix UI 设计规范

> **设计理念**: Production SaaS 美学 - 专业、简洁、高效
> **版本**: 1.0
> **更新日期**: 2025-01-06

## 📋 目录

- [设计原则](#设计原则)
- [颜色系统](#颜色系统)
- [排版系统](#排版系统)
- [组件规范](#组件规范)
- [交互规范](#交互规范)
- [实现指南](#实现指南)

---

## 🎨 设计原则

### 1. Production SaaS 美学

- **目标**: 打造适合长期使用的专业 Dashboard 界面
- **避免**: 过于花哨的动画和装饰（避免"Dribbble 概念"风格）
- **强调**: 清晰、高效、可读性

### 2. 固体表面（Solid Surfaces）

- **内容卡片**: 使用 `bg-white`（纯白背景）
- **边框**: 添加 `border border-slate-200/60` 清晰定义边缘
- **不依赖**: 仅使用阴影来定义边界

### 3. 玻璃拟态（Glassmorphism）

**仅用于以下场景**:
- Sticky Header（固定顶部导航）
- Floating Modals（浮动模态框）

**实现方式**:
```css
background: rgba(255, 255, 255, 0.7);
backdrop-filter: blur(20px);
-webkit-backdrop-filter: blur(20px);
```

### 4. 优化的对比度

**文字颜色层次**:
- 标题: `text-slate-900` (最深的颜色)
- 正文: `text-slate-700` (从 slate-500 提升对比度)
- 说明: `text-slate-600` (从 slate-500 提升)
- 辅助: `text-slate-400` (最小信息)

**确保**: 所有文字在纯白背景 (bg-white) 上具有良好的可读性

---

## 🎨 颜色系统

### 主色调

```css
/* 主操作色 - 纯色，不使用渐变 */
--primary: indigo-600;      /* #4f46e5 */
--primary-hover: indigo-700; /* #4338ca */
```

**应用场景**:
- 主要按钮 (CTA Buttons)
- 激活状态 (Active States)
- 进度指示器 (Progress Indicators)

### 辅助色

```css
/* 成功 */
--success: emerald-600;     /* #059669 */
--success-bg: emerald-50;   /* #ecfdf5 */

/* 警告 */
--warning: amber-600;       /* #d97706 */

/* 错误 */
--error: red-600;           /* #dc2626 */
```

### 背景色系统

```css
/* 页面背景 - 微妙渐变 */
body {
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
}

/* 卡片背景 - 纯白 */
.card {
  background: white;
}

/* 次要背景 - 浅灰 */
.secondary-bg {
  background: slate-50;
}
```

### 图标颜色

**微妙填充风格**（不使用渐变）:
```css
/* 蓝色系图标容器 */
.icon-blue {
  background: blue-50;
  color: blue-600;
}

/* 绿色系图标容器 */
.icon-green {
  background: emerald-50;
  color: emerald-600;
}

/* 紫色系图标容器 */
.icon-purple {
  background: purple-50;
  color: purple-600;
}
```

### 边框颜色

```css
/* 标准边框 - 60% 透明度 */
border: 1px solid theme('colors.slate.200 / 0.6');
/* 等同于: border border-slate-200/60 */
```

---

## 📝 排版系统

### 字体

- **主字体**: `Inter`, sans-serif
- **代码字体**: 等宽字体 (`font-mono`)

### 字间距（Letter Spacing）

```css
/* 标题 - 紧凑 */
h1, h2, h3, h4, h5, h6 {
  letter-spacing: -0.025em; /* tracking-tight */
}

/* 小标签 - 宽松 */
.label, .badge {
  letter-spacing: 0.05em; /* tracking-wide */
}
```

### 数字对齐

```css
/* 用于表格、数据列表、时间戳 */
.tabular-nums {
  font-variant-numeric: tabular-nums;
}
```

### 文字层次

| 层级 | 大小 | 字重 | 颜色 | 用途 |
|------|------|------|------|------|
| H1 | text-4xl | font-bold | slate-900 | 页面主标题 |
| H2 | text-2xl | font-semibold | slate-900 | 区块标题 |
| H3 | text-xl | font-medium | slate-900 | 卡片标题 |
| 正文 | text-base | normal | slate-700 | 主要内容 |
| 说明 | text-sm | normal | slate-600 | 辅助信息 |
| 标签 | text-xs | normal | slate-400 | 小标签、时间戳 |

---

## 🧩 组件规范

### 按钮（Buttons）

#### 主按钮（Primary Button）
```html
<button class="px-6 py-3 rounded-xl bg-indigo-600 text-white font-medium
               shadow-elegant transition-smooth btn-press
               hover:bg-indigo-700 hover:shadow-elegant-lg hover:-translate-y-0.5
               focus-ring-custom">
  主要操作
</button>
```

**关键点**:
- 使用纯色 `bg-indigo-600`（不是渐变）
- Hover: `bg-indigo-700`（加深颜色）
- 点击: `active:scale-95`（缩放效果）

#### 次按钮（Secondary Button）
```html
<button class="px-6 py-3 rounded-xl bg-white border border-slate-200
               text-slate-700 font-medium shadow-elegant
               transition-smooth btn-press
               hover:bg-slate-50 hover:shadow-elegant-lg
               focus-ring-custom">
  次要操作
</button>
```

#### 文本按钮（Text Button）
```html
<button class="px-6 py-3 rounded-xl text-slate-600 font-medium
               transition-smooth btn-press
               hover:bg-slate-100
               focus-ring-custom">
  文本操作
</button>
```

### 卡片（Cards）

#### 标准卡片
```html
<div class="bg-white rounded-2xl shadow-elegant
            border border-slate-200/60 p-6">
  <!-- 内容 -->
</div>
```

**关键点**:
- `bg-white`（纯白，不是半透明）
- `border border-slate-200/60`（清晰边缘）
- `shadow-elegant`（精致阴影，见下方阴影系统）

#### 可交互卡片
```html
<div class="bg-white rounded-2xl shadow-elegant
            border border-slate-200/60 p-6
            transition-smooth cursor-pointer btn-press
            hover:shadow-elegant-lg hover:-translate-y-1">
  <!-- 内容 -->
</div>
```

### 输入框（Input Fields）

```html
<input type="text"
       class="w-full px-4 py-3 rounded-xl
              bg-white border border-slate-200
              text-slate-900 placeholder-slate-400
              focus:outline-none focus:ring-2 focus:ring-offset-2
              focus:ring-indigo-500/20 transition-smooth"
       placeholder="请输入..." />
```

**关键点**:
- `bg-white`（纯白背景）
- `border border-slate-200`（边框）
- 自定义焦点环（见下方交互规范）

### 头像（Avatars）

```html
<!-- 文字头像 - 微妙填充 -->
<div class="w-10 h-10 rounded-full
            bg-blue-100 text-blue-700
            font-semibold shadow-elegant
            flex items-center justify-center">
  U
</div>
```

**关键点**:
- 使用微妙填充（如 `bg-blue-100`）
- 文字颜色加深（`text-blue-700`）
- 不使用渐变

### 空状态（Empty States）

```html
<div class="empty-state">
  <div class="w-16 h-16 mx-auto mb-4
              rounded-2xl bg-slate-100
              flex items-center justify-center">
    <i class="ti ti-folder text-3xl text-slate-400"></i>
  </div>
  <h4 class="text-lg font-semibold text-slate-900 mb-2">
    暂无文件
  </h4>
  <p class="text-sm text-slate-500">
    这个会话还没有关联的文件
  </p>
</div>
```

---

## 🎭 交互规范

### 阴影系统（Shadow System）

```css
/* 精致阴影 - 默认 */
.shadow-elegant {
  box-shadow: 0 8px 30px rgb(0, 0, 0, 0.04);
}

/* 大阴影 - Hover 状态 */
.shadow-elegant-lg {
  box-shadow: 0 12px 40px rgb(0, 0, 0, 0.08);
}
```

### 过渡动画（Transitions）

```css
/* 统一的平滑过渡 */
.transition-smooth {
  transition: all 0.2s cubic-bezier(0.25, 0.1, 0.25, 1.0);
}
```

**所有交互元素必须使用此过渡**:
- 按钮
- 卡片
- 输入框
- 链接

### 按钮按压效果

```css
.btn-press:active {
  transform: scale(0.95);
}
```

### 悬停效果（Hover Effects）

```css
/* 上浮效果 */
hover:-translate-y-0.5

/* 阴影加深 */
hover:shadow-elegant-lg
```

### 焦点环（Focus Ring）

```css
.focus-ring-custom:focus {
  outline: none;
  ring: 2px;
  ring-offset: 2px;
  --tw-ring-color: rgb(99 102 241 / 0.2); /* indigo-500/20 */
}
```

**替代 Tailwind**:
```html
<div class="focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500/20">
```

---

## 🛠️ 实现指南

### CSS 类定义（添加到 custom.css）

```css
/* Glassmorphism - 仅用于 Header 和 Modals */
.glass {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.glass-strong {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
}

/* Reflective Edge - 顶部反光边缘 */
.reflective-edge::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.8) 50%,
    transparent 100%);
}

/* Sophisticated Shadows */
.shadow-elegant {
  box-shadow: 0 8px 30px rgb(0, 0, 0, 0.04);
}

.shadow-elegant-lg {
  box-shadow: 0 12px 40px rgb(0, 0, 0, 0.08);
}

/* Smooth Transitions */
.transition-smooth {
  transition: all 0.2s cubic-bezier(0.25, 0.1, 0.25, 1.0);
}

/* Button Press Effect */
.btn-press:active {
  transform: scale(0.95);
}

/* Empty State */
.empty-state {
  border: 2px dashed #e2e8f0;
  border-radius: 12px;
  padding: 48px;
  text-align: center;
  background: linear-gradient(135deg,
    rgba(248, 250, 252, 0.5) 0%,
    rgba(226, 232, 240, 0.3) 100%);
}
```

### 页面背景

```html
<body>
  <!-- 微妙的渐变背景 -->
  <div style="background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); min-height: 100vh;">
    <!-- 内容 -->
  </div>
</body>
```

### 典型的卡片结构

```html
<!-- Panel/Card 容器 -->
<div class="bg-white rounded-2xl shadow-elegant border border-slate-200/60 overflow-hidden">

  <!-- Panel Header - 带底部边框 -->
  <div class="px-5 py-4 border-b border-slate-200/60 flex items-center justify-between">
    <h3 class="font-semibold text-slate-900 tracking-tight">标题</h3>
    <button class="w-8 h-8 rounded-lg bg-blue-50 text-blue-600
                   flex items-center justify-center
                   transition-smooth btn-press hover:bg-blue-100">
      <i class="ti ti-plus"></i>
    </button>
  </div>

  <!-- Panel Body -->
  <div class="p-4">
    <!-- 内容 -->
  </div>

</div>
```

---

## 📐 布局规范

### 三栏布局（主应用界面）

```html
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

  <!-- 左侧面板 - 会话列表 -->
  <div class="bg-white rounded-2xl shadow-elegant border border-slate-200/60">
    <!-- 会话列表 -->
  </div>

  <!-- 中间面板 - 对话历史 (占据 2 列) -->
  <div class="lg:col-span-2 bg-white rounded-2xl shadow-elegant border border-slate-200/60">
    <!-- 对话内容 -->
  </div>

</div>
```

### 响应式断点

- `lg`: 1024px 及以上使用三栏布局
- `lg` 以下: 单栏堆叠布局

---

## 🎯 设计检查清单

在实现或审查 UI 时，使用此清单确保符合设计规范：

### ✅ 颜色和背景
- [ ] 内容卡片使用 `bg-white`（纯白）
- [ ] 添加 `border border-slate-200/60` 边框
- [ ] 按钮使用纯色 `bg-indigo-600`（不是渐变）
- [ ] 图标使用微妙填充（如 `bg-blue-50`）

### ✅ 排版
- [ ] 标题使用 `tracking-tight`
- [ ] 小标签使用 `tracking-wide`
- [ ] 数字和日期使用 `tabular-nums`
- [ ] 正文使用 `text-slate-700`（不是 slate-500）

### ✅ 交互
- [ ] 所有可点击元素使用 `transition-smooth`
- [ ] 按钮有 `btn-press` 效果
- [ ] 自定义焦点环 `focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500/20`
- [ ] 卡片 hover 有 `hover:shadow-elegant-lg hover:-translate-y-0.5`

### ✅ 特殊效果
- [ ] 玻璃拟态仅用于 Header 和 Modals
- [ ] 没有使用光泽扫过动画（shimmer effect）
- [ ] 阴影使用 `shadow-elegant` 系列

---

## 📚 参考资源

### 完整实现示例

**Mockup 文件**: `web/mockup.html`

此文件包含所有 UI 组件的完整实现，是实施本规范的最佳参考。

### 设计系统灵感

本规范基于以下设计原则：
- **Production SaaS**: 适合长期使用的专业界面
- **Accessibility**: WCAG AA 级别的对比度标准
- **Performance**: 轻量级动画，不影响性能
- **Consistency**: 统一的设计语言

---

## 🔄 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2025-01-06 | 初始版本 - Production SaaS 设计系统 |

---

## 📝 维护说明

### 如何更新此规范

1. **设计变更**: 先更新 `web/mockup.html` 展示新设计
2. **更新文档**: 同步更新 `docs/ui-spec.md`
3. **实施到代码**: 更新 `index.html`, `wizard.html` 等
4. **测试验证**: 确保所有页面符合新规范

### 规范违反

如果发现违反本规范的实现：
1. 检查 `mockup.html` 中的正确实现
2. 参考 `docs/ui-spec.md` 中的具体规则
3. 使用检查清单验证修复

---

**最后更新**: 2025-01-06
**维护者**: AgentMatrix Team
