# Release v0.2.0 - ask_user 交互机制 + Skill 架构重构

## 🎯 主要功能

### 1. 💬 ask_user 交互机制

**核心功能**：Agent 可以在执行过程中向用户提问，等待用户回答后继续执行。

**使用场景**：
- 信息确认：Agent 需要用户确认关键信息（如预算、偏好）
- 决策辅助：Agent 需要用户提供决策依据
- 交互式任务：需要用户在执行过程中提供输入

**技术亮点**：
- ✅ 使用 `asyncio.Future` 传递数据（而非 Event）
- ✅ 兼容全局暂停机制（等待期间仍可响应 pause）
- ✅ 支持嵌套 MicroAgent（外层自动恢复）
- ✅ 走特殊通道（UI 弹窗），不通过邮件流程

**Server API**：
```bash
# 查询是否有等待用户输入的问题
GET /api/agents/{name}/pending_user_input

# 提交用户回答
POST /api/agents/{name}/user_input
Body: {"answer": "用户回答"}
```

**实现细节**：
- `BaseAgent.ask_user(question)`: 等待用户输入，返回回答
- `BaseAgent.submit_user_input(answer)`: 唤醒等待中的 Agent
- `MicroAgent._execute_action`: 特殊处理 ask_user action
- `BaseSkillMixin.ask_user`: Action 注册（base skill）

### 2. 🎁 Skill 架构重构

**重构目的**：更清晰的职责分离，便于扩展和维护。

**核心 Skills**：

| Skill | Actions | 说明 | 强制注入 |
|-------|---------|------|---------|
| **base** | get_current_datetime, take_a_break, ask_user | 通用基础功能 | ✅ Top-level |
| **email** | send_email | 邮件发送 | ✅ Top-level |
| **all_finished** | all_finished | 任务终止 | ✅ 所有层级 |

**重构内容**：
- ✅ 创建 `email` skill（包含 `send_email`）
- ✅ `base` skill 移除 `send_email` 和 `rest_n_wait`
- ✅ `rest_n_wait` 已淘汰（统一使用 `all_finished`）
- ✅ Top-level MicroAgent 自动注入 `base + email`

**设计原则**：
- **Top-level MicroAgent**：需要 `base + email`（和用户通信）
- **内部 MicroAgent**：不需要 `email`（返回结果给父级）
- **all_finished**：所有 MicroAgent 都有（硬编码）

**未来扩展**：
- `email` skill 可添加 `check_email`、`read_email` 等功能
- 不影响 `base` skill 的简洁性

---

## 📝 自 v0.1.6 以来的其他改进

### Agent 运行时控制
- ⏸️ Agent 暂停/恢复机制（可随时暂停执行，查看状态）
- 📊 执行栈追踪（查询嵌套层次和当前任务）

### 架构改进
- 📂 Agent 状态目录与工作目录分离（为容器化做准备）
- 🏗️ 项目结构重组（明确核心框架、Web应用和示例的边界）

### Skill 系统增强
- 🔄 Lazy Load 机制（按名字自动发现并加载 Skills）
- 📁 Simple Web Search Skill 实现
- 🎨 BrowserSkill 和 FileSkill 基于 Mixin 重构

### 代码质量
- 🧹 移除 instruction_to_caller 属性
- 🧹 清理旧架构代码
- ✨ 新增 418 行代码，删除 73 行旧代码

---

## 📦 安装

```bash
pip install matrix-for-agents==0.2.0
```

或从源码安装：

```bash
git clone https://github.com/webdkt/agentmatrix.git
cd agentmatrix
git checkout v0.2.0
pip install -e .
```

---

## 🚀 使用示例

### ask_user 示例

```python
# Agent 在执行中向用户提问
# LLM 决定调用 ask_user action
answer = await self.root_agent.ask_user("请确认预算范围")
# 返回: "5万-10万"

# 前端通过 API 查询和提交
GET /api/agents/Tom/pending_user_input
POST /api/agents/Tom/user_input {"answer": "5万-10万"}
```

### Skill 配置

```yaml
# profile.yml
skills:
  - browser   # 可选 skills
  - file      # 可选 skills
  # base 和 email 自动注入，无需配置
```

---

## 🙏 致谢

感谢所有贡献者的支持！
