# Web 应用重构执行计划

## 🎯 重构目标

将 `app.js`（1651 行）和 `index.html`（1551 行）从单一巨石文件重构为模块化架构。

---

## 📊 当前状态

### 文件分析

```
文件              行数   问题
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
index.html        1551   包含所有 UI 模板
js/app.js         1651   包含所有逻辑和状态
```

### 功能分布（app.js）

- 状态管理: 9% (~150 行)
- 会话管理: 9% (~150 行)
- 邮件管理: 15% (~250 行)
- Agent 管理: 15% (~250 行)
- 设置管理: 24% (~400 行)
- 文件管理: 3% (~50 行)
- UI 交互: 9% (~150 行)
- 状态轮询: 6% (~100 行)
- 事件处理: 9% (~150 行)
- 工具函数: 6% (~100 行)

---

## 🔄 版本管理

### 分支策略

```bash
# 1. 创建重构分支
git checkout -b refactor/web-moduleization

# 2. 创建开发起点标记（用于对比）
git tag pre-refactor-start

# 3. 每个阶段完成后创建标记
git tag refactor/phase-1-complete
git tag refactor/phase-2-complete
```

### 回滚计划

```bash
# 如果需要回滚
git checkout main

# 或者回滚到某个阶段
git checkout refactor/phase-1-complete
```

---

## 📋 执行计划

### Phase 1: 基础设施搭建

**目标**：建立模块系统，保持功能不变

**时间**: 1 天

**步骤**:

1. **创建目录结构**（10 分钟）
   ```bash
   mkdir -p web/js/stores
   mkdir -p web/js/services
   mkdir -p web/utils
   mkdir -p docs/web
   ```

2. **创建 main.js 入口**（20 分钟）
   ```javascript
   // web/js/main.js
   import './app.js';
   ```

3. **更新 index.html 引入**（10 分钟）
   ```html
   <!-- 移除 app.js，引入 main.js -->
   <script src="/js/main.js" type="module"></script>
   ```

4. **验证功能**（30 分钟）
   - 启动应用
   - 测试所有核心功能
   - 确认无回归

**验收**：
- ✅ 目录结构创建完成
- ✅ 功能完全正常
- ✅ 无控制台错误

**回滚点**：`git reset --hard pre-refactor-start`

---

### Phase 2: 提取工具函数

**目标**：提取格式化和工具函数到独立模块

**时间**: 半天

**步骤**:

1. **创建 `utils/format.js`**（1 小时）
   ```javascript
   // web/js/utils/format.js
   export function formatTime(timestamp) {...}
   export function formatDate(timestamp) {...}
   export function formatFileSize(bytes) {...}
   export function formatStatusTime(timestamp) {...}
   ```

2. **创建 `utils/markdown.js`**（30 分钟）
   ```javascript
   // web/js/utils/markdown.js
   export function renderMarkdown(content) {...}
   ```

3. **创建 `utils/dom.js`**（30 分钟）
   ```javascript
   // web/js/utils/dom.js
   export function scrollToBottom(containerId) {...}
   export function getElement(selector) {...}
   ```

4. **创建 `utils/validation.js`**（30 分钟）
   ```javascript
   // web/utils/validation.js
   export function validateEmail(email) {...}
   export function validateRequired(fields) {...}
   ```

5. **更新 app.js 引用**（30 分钟）
   - 替换本地函数为导入
   - 测试所有格式化显示

**验收**：
- ✅ 4 个 utils 文件创建
- ✅ app.js 减少约 60 行
- ✅ 所有格式化正常显示

**回滚点**：`git reset --hard HEAD~1`

---

### Phase 3: 拆分状态管理

**目标**：将 app() 中的状态按领域拆分到 stores

**时间**: 1-2 天

**步骤**:

1. **创建 `stores/sessionStore.js`**（2 小时）
   ```javascript
   // web/js/stores/sessionStore.js
   export function useSessionStore() {
       return {
           // 状态
           sessions: [],
           currentSession: null,
           currentSessionEmails: [],
           isLoadingSessions: false,

           // 方法
           async loadSessions() {...},
           async selectSession(session) {...},
           async loadSessionEmails(sessionId) {...},
           getAvatarName(name) {...}
       };
   }
   ```

2. **创建 `stores/emailStore.js`**（2 小时）
   ```javascript
   // web/js/stores/emailStore.js
   export function useEmailStore() {
       return {
           // 状态
           newEmailPopup: null,
           replyStates: {},
           quickReplyBody: '',

           // 方法
           startReply(email, mode) {...},
           cancelReply(email) {...},
           async sendEmail(...) {...},
           handleNewEmail(data) {...},
       };
   }
   ```

3. **创建 `stores/agentStore.js`**（2 小时）
   ```javascript
   // web/js/stores/agentStore.js
   export function useAgentStore() {
       return {
           // 状态
           agents: [],
           agentSearchQuery: '',

           // Agent Modal
           showAgentModal: false,
           editingAgent: null,
           // ... agent 相关状态和方法
       };
   }
   ```

4. **创建 `stores/settingsStore.js`**（2 小时）
   ```javascript
   // web/js/stores/settingsStore.js
   export function useSettingsStore() {
       return {
           // 设置相关状态和方法
       };
   }
   ```

5. **创建 `stores/uiStore.js`**（1 小时）
   ```javascript
   // web/js/stores/uiStore.js
   export function useUiStore() {
       return {
           // UI 交互状态
           currentTab: 'master',
           leftPanelWidth: 280,
           // ...
       };
   }
   ```

6. **更新 `app.js` 使用 stores**（2 小时）
   ```javascript
   import { useSessionStore } from './stores/sessionStore.js';
   import { useEmailStore } from './stores/emailStore.js';
   // ...

   function app() {
       return {
           ...useSessionStore(),
           ...useEmailStore(),
           // ...
       };
   }
   ```

**验收**：
- ✅ 5 个 store 文件创建
- ✅ app.js 减少到 ~800 行
- ✅ 功能完全正常

**回滚点**：每个文件独立回滚（`git checkout HEAD~1 filename`）

---

### Phase 4: 提取业务逻辑

**目标**：将业务逻辑从 stores 移到 services

**时间**: 1-2 天

**步骤**:

1. **创建 `services/sessionService.js`**（1.5 小时）
   ```javascript
   export class SessionService {
       constructor(api) {
           this.api = api;
       }

       async getSessions() {
           return await this.api.getSessions();
       }

       async getSessionEmails(sessionId) {
           return await this.api.getSessionEmails(sessionId);
       }
   }
   ```

2. **创建 `services/emailService.js`**（2 小时）
   ```javascript
   export class EmailService {
       async sendEmail(sessionId, emailData, files) {
           // 验证
           // 构建 FormData
           // API 调用
       }

       formatEmailForDisplay(email) {
           // 格式化
       }
   }
   ```

3. **创建 `services/agentService.js`**（1.5 小时）

4. **创建 `services/pollingService.js`**（1 小时）

5. **更新 stores 使用 services**（2 小时）

**验收**：
- ✅ 5 个 service 文件创建
- ✅ stores 只包含状态，逻辑移到 services
- ✅ 功能正常

**回滚点**：同 Phase 3

---

### Phase 5: CSS 模块化

**目标**：拆分 `custom.css` 为功能模块

**时间**: 半天

**步骤**:

1. **创建 `css/base.css`**（1 小时）
   - CSS 变量
   - 基础样式
   - Tailwind 扩展

2. **创建 `css/components.css`**（1 小时）
   - 消息列表样式
   - 模态框样式
   - 表单样式

3. **创建 `css/utilities.css`**（30 分钟）
   - 动画
   - 工具类

4. **更新 `index.html` 引用**（10 分钟）

**验收**：
- ✅ CSS 按功能组织
- ✅ 样式无破坏

---

### Phase 6: 清理和优化

**目标**：清理重复代码，优化性能

**时间**: 1 天

**步骤**:

1. **提取模态框通用逻辑**（2 小时）
   - 创建 `services/modalService.js`
   - 统一模态框打开/关闭

2. **提取表单验证逻辑**（1 小时）
   - 在 `utils/validation.js` 中增强

3. **优化事件处理**（1 小时）
   - 统一事件格式

4. **代码审查**（2 小时）
   - 检查重复代码
   - 检查耦合度
   - 添加必要注释

5. **性能优化**（1 小时）
   - 减少重复计算
   - 优化 DOM 查询

**验收**：
- ✅ 无重复代码
- ✅ 代码行数减少 20%+
- ✅ 性能无明显下降

---

## 📊 详细任务列表

### 任务 1: 创建目录结构

```bash
# 1. 创建目录
mkdir -p web/js/stores
mkdir -p web/js/services
mkdir -p web/utils
```

### 任务 2: 提取格式化函数

**文件**: `web/js/utils/format.js`

**提取内容**:
- `formatTime()` (app.js:654)
- `formatDate()` (app.js:663)
- `formatFileSize()` (app.js:173)
- `formatStatusTime()` (app.js:627)
- `getAgentDescription()` (app.js:274)

### 任务 3: 提取 DOM 操作

**文件**: `web/js/utils/dom.js`

**提取内容**:
- `scrollToBottom()` (app.js:496)
- `getAvatarName()` (app.js:699)

### 任务 4: 创建 sessionStore

**文件**: `web/js/stores/sessionStore.js`

**提取内容**:
- 状态: `sessions`, `currentSession`, `currentSessionEmails`, `isLoadingSessions`
- 方法: `loadSessions()`, `selectSession()`, `loadSessionEmails()`, `getAvatarName()`

### 任务 5: 创建 emailStore

**文件**: `web/js/stores/emailStore.js`

**提取内容**:
- 状态: `newEmailPopup`, `replyStates`, `quickReplyBody`, `newEmail` 对象相关
- 方法: `startReply()`, `cancelReply()`, `sendEmail()`, `handleNewEmail()`, `getLastEmailSender()`

### 任务 6: 创建 agentStore

**文件**: `web/js/stores/agentStore.js`

**提取内容**:
- 状态: `agents`, `agentSearchQuery`
- Agent Modal 相关所有状态和方法
- Skill Search Modal 相关所有状态和方法

### 任务 7: 创建 settingsStore

**文件**: `web/js/stores/settingsStore.js`

**提取内容**:
- LLM 配置管理相关所有状态和方法
- 设置视图切换

### 任务 8: 创建 uiStore

**文件**: `web/js/stores/uiStore.js`

**提取内容**:
- `currentTab`, `showFilePanel`
- 面板尺寸调整相关

### 任务 9: 创建 pollingService

**文件**: `web/js/services/pollingService.js`

**提取内容**:
- `checkAndStartStatusPolling()`
- `startAgentStatusPolling()`
- `stopAgentStatusPolling()`
- `fetchAgentStatus()`
- `checkLastEmailChanged()`
- `formatStatusTime()`

### 任务 10: 创建 emailService

**文件**: `web/js/services/emailService.js`

**提取内容**:
- 邮件发送逻辑
- 邮件格式化逻辑

### 任务 11: 创建 sessionService

**文件**: `web/js/services/sessionService.js`

**提取内容**:
- 会话加载逻辑
- 会话切换逻辑

---

## 🚀 执行顺序

### 优先级排序

1. **Phase 1: 基础设施** ⭐⭐⭐
   - 必须首先完成
   - 后续阶段依赖

2. **Phase 2: 工具函数** ⭐⭐
   - 简单独立
   - 立即见效
   - 风险最低

3. **Phase 3: 状态管理** ⭐⭐⭐
   - 核心重构
   - 影响最大

4. **Phase 4: 业务逻辑** ⭐⭐⭐
   - 依赖 Phase 3
   - 进一步解耦

5. **Phase 5: CSS 模块化** ⭐⭐
   - 可独立进行
   - 低风险

6. **Phase 6: 优化** ⭐
   - 可选
   - 收尾工作

---

## ⚠️ 风险控制

### 每个阶段的回滚点

```bash
# 开始前创建标记
git add .
git commit -m "phase-N-start"

# 完成后创建标记
git add .
git commit -m "phase-N-complete"
```

### 回滚命令

```bash
# 回滚整个重构
git checkout main

# 回滚单个文件
git checkout HEAD~1 web/js/app.js

# 回滚到某个阶段
git checkout refactor/phase-1-complete
```

---

## 📝 验证清单

### 每个阶段完成后的验证

- [ ] 功能完全正常
- [ ] 无控制台错误
- [ ] 核心流程测试通过
  - [ ] 创建会话
  - [ ] 发送邮件
  - [ ] Agent 状态轮询
  - [ ] Agent 配置管理
  - [ ] ask_user 功能
- [ ] 文件行数符合规范（<300 行）
- [ ] 无明显性能下降

---

## 📈 预期成果

### 代码质量指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 最大文件行数 | 1651 | <300 |
| 平均文件行数 | 1651 | <150 |
| 代码重复率 | 高 | 低 |
| 测试覆盖率 | 0% | 50%+ |

### 开发效率

- 新功能开发时间: ⬇️ 30%
- Bug 修复时间: ⬇️ 50%
- 代码审查时间: ⬇️ 40%

---

## 📅 时间线

| 阶段 | 时间 | 累计 |
|------|------|------|
| Phase 1 | 1 天 | 1 天 |
| Phase 2 | 0.5 天 | 1.5 天 |
| Phase 3 | 1.5 天 | 3 天 |
| Phase 4 | 1.5 天 | 4.5 天 |
| Phase 5 | 0.5 天 | 5 天 |
| Phase 6 | 1 天 | 6 天 |

**缓冲时间**: +1-2 天（应对意外情况）

---

## 🎯 最终结构预览

```
web/
├── index.html              # ~150 行
├── main.js                 # ~50 行
├── js/
│   ├── app.js              # ~200 行
│   ├── stores/             # ~7 个文件，~800 行
│   ├── services/           # ~5 个文件，~600 行
│   ├── utils/              # ~4 个文件，~160 行
│   ├── api.js              # ~250 行
│   └── ws.js              # ~105 行
└── css/
    ├── base.css            # ~200 行
    ├── components.css      # ~300 行
    └── utilities.css      # ~100 行
```

**总行数**: 从 3200+ 行 → ~2600 行
**最大文件**: 从 1651 行 → ~300 行
