# Web 模块化重构规范

## 📁 文件结构规范

```
web/
├── index.html                  # 主HTML文件（精简版，~900行）
├── components/                 # HTML组件模板目录
│   ├── ask-user-dialog.html    # Agent提问对话框（inline + modal 2个template）
│   ├── conversation-list.html  # 会话列表
│   ├── message-list.html       # 消息列表
│   ├── new-email-modal.html    # 新建邮件弹窗
│   └── settings-panel.html     # 设置面板
├── js/
│   ├── app.js                  # 主应用逻辑（Alpine.js data function）
│   ├── api.js                  # API客户端
│   ├── ws.js                   # WebSocket客户端
│   ├── stores/                 # Alpine.js状态管理（使用Alpine.store）
│   │   ├── agentStore.js       # Agent相关状态
│   │   ├── emailStore.js       # Email相关状态
│   │   ├── sessionStore.js     # Session相关状态
│   │   ├── settingsStore.js    # 设置相关状态
│   │   └── uiStore.js          # UI状态（包括askUserDialogs）
│   ├── services/               # 业务服务层
│   │   ├── agentService.js
│   │   ├── emailService.js
│   │   ├── modalService.js
│   │   ├── pollingService.js
│   │   └── sessionService.js
│   └── utils/                  # 工具函数
│       ├── componentLoader.js  # 组件加载器
│       ├── dom.js              # DOM操作工具
│       ├── format.js           # 格式化工具
│       ├── markdown.js         # Markdown渲染
│       └── validation.js       # 验证工具
├── css/                        # 样式文件（由Python生成，不手动编辑）
└── libs/                       # 第三方库
    └── marked.min.js           # Markdown解析器
```

## 🎯 组件模板规范

### 1. 模板文件格式

每个组件文件使用 `<template>` 标签包裹：

```html
<!-- component-name.html -->
<template id="component-name-template">
  <!-- 组件HTML内容 -->
</template>
```

**注意**：
- ✅ 使用语义化的 `template` ID：`<component-name>-template`
- ✅ template 内只包含组件的核心HTML，不包含 `<html>`, `<head>`, `<body>` 等标签
- ❌ 不要在 `<head>` 中放置包含 body 元素的模板

### 2. Alpine.js 语法规范

组件模板中的方法调用必须通过 `Alpine.store` 访问：

```html
<!-- ✅ 正确 -->
<span x-show="uiStore.hasAskUserDialog()">
<span x-text="uiStore.getCurrentAskUserDialog()?.agent_name">

<!-- ❌ 错误（直接调用app()中的方法）-->
<span x-show="hasAskUserDialog()">
<span x-text="getCurrentAskUserDialog()?.agent_name">
```

### 3. 组件加载规范

使用 `componentLoader.js` 中的函数加载组件：

```javascript
// 在 app.js 的 loadComponents() 中
loadComponents() {
    // 克隆模板
    const template = document.getElementById("component-name-template");
    const target = document.querySelector("#component-name");
    if (template && target) {
        target.appendChild(template.content.cloneNode(true));
        console.log("✅ ComponentName component mounted");
    }
}
```

**时机**：
- ✅ 在 Alpine.js 完全初始化后加载
- ✅ 在 `init()` 方法的最后调用
- ❌ 不要在页面加载时立即执行

## 📦 index.html 规范

### 1. 组件挂载点

使用 `<div>` 作为组件挂载点：

```html
<!-- 组件挂载点 -->
<div id="component-name"></div>
```

**注意**：
- ✅ ID 必须与组件名称一致（去除 `-template` 后缀）
- ✅ 放在正确的 DOM 位置（保持原有的布局结构）
- ❌ 不要包含任何内容（由组件模板填充）

### 2. 文件大小目标

- **目标行数**：< 1000 行
- **当前状态**：1640 行 → 目标 ~900 行
- **减少比例**：~45%

## 🔧 Alpine.js 架构规范

### 1. 状态管理使用 Alpine.store

所有共享状态和跨组件方法必须定义在 `Alpine.store` 中：

```javascript
// stores/uiStore.js
document.addEventListener('alpine:init', () => {
    Alpine.store('uiStore', {
        askUserDialogs: {},

        hasAskUserDialog() {
            // 实现
        },

        getCurrentAskUserDialog() {
            // 实现
        }
    });
});
```

### 2. app() 函数职责

`app()` 函数只负责：
- ✅ 初始化应用逻辑
- ✅ 加载组件
- ✅ 处理页面级事件
- ❌ 不定义跨组件的方法（放在 store 中）

### 3. 组件间通信

- ✅ 使用 `Alpine.store` 共享状态
- ✅ 使用自定义事件（`window.dispatchEvent()`）
- ❌ 避免直接调用其他组件的方法

## 🚨 错误防范清单

### 1. HTML 结构错误

❌ **错误示例**：在 `<head>` 中放置包含 body 元素的模板
```html
<head>
  <script type="text/html" id="template">
    <aside> <!-- 会导致浏览器自动开启body -->
  </aside>
  </script>
</head>
```

✅ **正确做法**：
- 使用 `<template>` 标签
- 或者放在 `<body>` 底部

### 2. Alpine.js 函数未定义

❌ **错误原因**：
- 组件模板中的函数调用在 Alpine.js 初始化前执行
- 函数定义在 `app()` 中，但组件通过 `Alpine.store` 访问

✅ **解决方案**：
- 所有跨组件方法定义在 `Alpine.store` 中
- 组件模板通过 `uiStore.methodName()` 调用

### 3. 组件加载时机错误

❌ **错误**：在页面加载时立即加载组件
```javascript
// 不要这样做
loadComponents(); // 在全局作用域立即执行
```

✅ **正确**：在 Alpine.js 初始化后加载
```javascript
async init() {
    await this.loadInitialData();
    this.loadComponents(); // 在最后加载
}
```

## 📋 工作流程规范

### 1. 提取新组件步骤

1. **定位组件范围**：在 index.html 中找到组件的起始和结束标签
2. **提取HTML**：使用 `sed -n 'start,endp'` 提取
3. **创建模板**：包装在 `<template>` 标签中
4. **创建挂载点**：在 index.html 中用 `<div id="component-name"></div>` 替换
5. **更新加载器**：在 `app.js` 的 `loadComponents()` 中添加加载逻辑
6. **验证语法**：运行 `node --check web/js/app.js`
7. **测试功能**：刷新浏览器验证组件正常工作

### 2. Git 提交规范

每个阶段完成后创建 commit：
```bash
git add web/index.html web/js/app.js web/components/
git commit -m "refactor(web): extract ComponentName component"
```

### 3. 验证清单

每完成一个组件后：
- [ ] `node --check web/js/app.js` 语法检查通过
- [ ] 浏览器 Console 无错误
- [ ] 组件功能正常
- [ ] index.html 行数减少
- [ ] Git commit 已创建

## 📊 当前进度

| 组件 | 状态 | index.html 行数 |
|------|------|-----------------|
| 原始状态 | - | 1640 |
| AskUserDialog | ✅ | -132 |
| ConversationList | ✅ | -93 |
| MessageList | ✅ | -256 |
| NewEmailModal | ✅ | -124 |
| SettingsPanel | ✅ | -159 |
| **总计** | **需恢复** | **1640 → 876** |

---

**最后更新**: 2026-03-16
**维护人**: Claude Code
**版本**: 2.0
