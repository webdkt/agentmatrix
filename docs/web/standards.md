# Web 前端开发规范

## 🎯 设计原则

1. **单一职责**：每个文件/模块只负责一个功能领域
2. **小文件原则**：单个文件不超过 300 行
3. **低耦合**：模块间依赖最小化
4. **高内聚**：相关功能组织在一起
5. **易测试**：核心逻辑可独立测试

---

## 📁 目录结构规范

```
web/
├── index.html                 # 主 HTML 容器（~150 行）
├── main.js                   # ES 模块入口（~50 行）
│
├── js/
│   ├── app.js                 # Alpine.js 主应用（~200 行）
│   │
│   ├── stores/                # 状态管理（每个 ~100-250 行）
│   │   ├── sessionStore.js    # 会话状态
│   │   ├── emailStore.js      # 邮件状态
│   │   ├── agentStore.js      # Agent 状态
│   │   ├── settingsStore.js   # 设置状态
│   │   └── uiStore.js         # UI 状态
│   │
│   ├── services/              # 业务逻辑（每个 ~80-150 行）
│   │   ├── sessionService.js  # 会话业务逻辑
│   │   ├── emailService.js    # 邮件业务逻辑
│   │   ├── agentService.js    # Agent 业务逻辑
│   │   ├── pollingService.js  # 状态轮询逻辑
│   │   └── modalService.js    # 模态框管理
│   │
│   ├── components/            # UI 组件（可选，后期）
│   │
│   ├── utils/                 # 工具函数（每个 ~30-60 行）
│   │   ├── format.js          # 格式化工具
│   │   ├── markdown.js        # Markdown 渲染
│   │   ├── validation.js      # 验证工具
│   │   └── dom.js             # DOM 操作
│   │
│   ├── api.js                # API 封装（~250 行，已有）
│   └── ws.js                 # WebSocket 封装（~105 行，已有）
│
├── css/
│   ├── base.css               # 基础样式（~200 行）
│   ├── components.css         # 组件样式（~300 行）
│   └── utilities.css         # 工具类（~100 行）
│
└── assets/                   # 静态资源（图片、图标等）
```

---

## 📦 模块分类规范

### 1. Stores（状态管理）

**职责**：
- 管理应用状态
- 提供状态操作方法
- 触发 UI 更新

**命名**：`{domain}Store.js`

**示例**：
- `sessionStore.js` - 会话列表、当前会话
- `emailStore.js` - 邮件列表、回复状态
- `agentStore.js` - Agent 列表、模态框状态

**结构**：
```javascript
export function {domain}Store() {
    return {
        // ========== 状态 ==========
        // 状态字段定义

        // ========== 方法 ==========
        // 方法定义

        // ========== 生命周期 ==========
        // init() 等可选
    };
}
```

**使用**：
```javascript
function app() {
    return {
        ...useSessionStore(),
        ...useEmailStore(),
        ...useAgentStore(),
    };
}
```

---

### 2. Services（业务逻辑）

**职责**：
- 封装业务逻辑
- 调用 API
- 数据转换

**命名**：`{domain}Service.js`

**示例**：
- `emailService.js` - 发送邮件、格式化邮件
- `agentService.js` - 加载 Agent、保存配置
- `pollingService.js` - 状态轮询

**结构**：
```javascript
export class {Domain}Service {
    constructor(api) {
        this.api = api;
    }

    async {method}() {
        // 业务逻辑
        // API 调用
        // 返回结果
    }
}
```

**使用**：
```javascript
// 在 store 中
const emailService = new EmailService(API);

async sendEmail(...) {
    return await emailService.send(...);
}
```

---

### 3. Utils（工具函数）

**职责**：
- 纯函数式
- 无状态
- 可复用

**命名**：按功能命名

**示例**：
- `format.js` - 格式化时间、日期、文件大小
- `markdown.js` - Markdown 渲染
- `dom.js` - DOM 操作
- `validation.js` - 验证函数

**结构**：
```javascript
// 导出纯函数
export function formatTime(timestamp) {
    // 逻辑
}

export function formatDate(timestamp) {
    // 逻辑
}
```

---

### 4. Components（UI 组件，可选）

**职责**：
- 封装 UI 逻辑
- 可复用的 UI 片段

**命名**：PascalCase（如 `SessionList.js`）

**结构**：
```javascript
export function SessionList() {
    return {
        // 组件状态和方法
    };
}
```

---

## 📝 编码规范

### 命名规范

| 类型 | 命名 | 示例 |
|------|------|------|
| 文件 | camelCase | `sessionStore.js`, `emailService.js` |
| 类/构造函数 | PascalCase | `EmailService`, `PollingService` |
| 函数/方法 | camelCase | `loadSessions()`, `formatTime()` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| 私有变量 | _camelCase | `_pendingUserQuestion` |

### 注释规范

```javascript
/**
 * 功能描述
 *
 * @param {Type} name - 参数说明
 * @returns {Type} 返回值说明
 */
function functionName(name) {
    // 实现
}
```

### 导入导出规范

```javascript
// 命名导出（推荐）
export function formatTime() {}
export function formatDate() {}

// 默认导出（类）
export class EmailService {}

// 命名导入
import { formatTime } from './utils/format.js';
import { EmailService } from './services/emailService.js';
```

---

## 🎨 UI 组件规范

### Alpine.js 组件模式

```javascript
function app() {
    return {
        // 状态
        showModal: false,

        // 方法
        openModal() {
            this.showModal = true;
        },

        // 生命周期
        init() {
            // 初始化逻辑
        }
    };
}
```

### HTML 模板规范

- 使用 `x-show` 控制显示/隐藏
- 使用 `x-if` 控制存在性
- 使用 `x-for` 渲染列表
- 使用 `@click` 绑定事件

---

## 🧪 测试规范

### 单元测试

**测试位置**：`tests/unit/{module}.test.js`

**测试框架**：Vitest

```javascript
import { describe, it, expect } from 'vitest';
import { formatTime } from '../../js/utils/format.js';

describe('Format Utils', () => {
    it('should format time correctly', () => {
        const result = formatTime('2025-03-13T14:30:00');
        expect(result).toBe('14:30');
    });
});
```

### 测试覆盖目标

- Utils: 90%+
- Services: 70%+
- Stores: 50%+

---

## 🔄 开发流程

### 新增功能流程

1. **确定模块归属**（Store/Service/Util）
2. **创建/修改文件**
3. **添加/更新导出**
4. **在 app.js 中引入**
5. **测试功能**
6. **提交代码**

### 修改功能流程

1. **定位文件**（根据功能找模块）
2. **修改逻辑**
3. **测试影响范围**
4. **提交代码**

---

## 📋 代码审查清单

### 提交前检查

- [ ] 文件行数不超过 300 行
- [ ] 单一职责（只做一件事）
- [ ] 无重复代码
- [ ] 有适当注释
- [ ] 命名符合规范
- [ ] 已测试（如果需要）

---

## 📚 参考文档

- [Alpine.js 官方文档](https://alpinejs.dev/)
- [JavaScript 最佳实践](https://github.com/ryanmcdermott/guides/tree/main/style-guide)
- [Clean Code JavaScript](https://github.com/ryanmcdermott/clean-code-javascript)
