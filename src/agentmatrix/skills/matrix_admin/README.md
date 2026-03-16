# Matrix Admin Skill

AgentMatrix 系统管理技能，提供运行时管理功能。

## ✨ 新功能：完整支持 Email Proxy（SMTP + IMAP）

现在支持：
- 📤 **SMTP 发送**：Agent 可以发送邮件到用户邮箱
- 📥 **IMAP 接收**：从用户邮箱接收邮件，自动转发给对应 Agent
- ⏱️ **自动拉取**：每 30 秒检查一次新邮件
- 🎯 **智能路由**：支持通过 @mention 指定收件 Agent

---

## 功能列表

### 1. `add_agent` - 添加新 Agent

创建新的 Agent 配置文件并加载到系统中。

**参数:**
- `agent_name` (必需): Agent 名称，如 'assistant'
- `description` (必需): Agent 描述
- `backend_model` (可选): 后端模型名称
- `skills` (可选): 技能列表，逗号分隔，如 'email,file'
- `persona` (可选): Persona 提示词

**示例:**
```
add_agent(
    agent_name="researcher",
    description="负责深度研究和数据分析",
    backend_model="claude-opus-4",
    skills="web_search,file",
    persona="你是一个专业的研究助手..."
)
```

### 2. `reload_agent` - 重载 Agent

重新加载已存在的 Agent 配置。

**参数:**
- `agent_name` (必需): 要重载的 Agent 名称

**示例:**
```
reload_agent(agent_name="researcher")
```

### 3. `config_email_proxy` - 配置 Email Proxy ⭐

配置或更新 Email Proxy 服务（支持 SMTP 发送和 IMAP 接收）。

**参数:**
- `enabled` (必需): 是否启用 (true/false)
- `matrix_mailbox` (必需): Matrix 邮箱地址（用于发送邮件给用户）
- `user_mailbox` (必需): 用户邮箱地址（只接收来自此地址的邮件）
- `smtp_host` (必需): SMTP 服务器地址
- `smtp_port` (必需): SMTP 端口
- `smtp_user` (必需): SMTP 用户名
- `smtp_password` (必需): SMTP 密码或应用密码
- `imap_host` (必需): IMAP 服务器地址
- `imap_port` (必需): IMAP 端口
- `imap_user` (可选): IMAP 用户名（默认同 smtp_user）
- `imap_password` (可选): IMAP 密码（默认同 smtp_password）

**功能说明:**
- **SMTP**: Agent 发送邮件到用户邮箱
- **IMAP**: 从用户邮箱接收邮件，转发给对应 Agent
- **过滤**: 只处理来自 user_mailbox 的邮件
- **路由**: 支持通过 @mention 指定收件 Agent
- **频率**: 每 30 秒检查一次新邮件

**Gmail 配置示例:**
```
config_email_proxy(
    enabled=True,
    matrix_mailbox="matrix@gmail.com",
    user_mailbox="your-email@gmail.com",
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    smtp_user="matrix@gmail.com",
    smtp_password="abcd efgh ijkl mnop",  # Gmail 应用专用密码
    imap_host="imap.gmail.com",
    imap_port=993,
    imap_user="your-email@gmail.com",
    imap_password="wxyz abcd efgh ijkl"   # Gmail 应用专用密码
)
```

**常用邮箱配置:**

| 邮箱服务商 | SMTP 服务器 | SMTP 端口 | IMAP 服务器 | IMAP 端口 |
|-----------|------------|----------|------------|----------|
| Gmail | smtp.gmail.com | 587 | imap.gmail.com | 993 |
| Outlook | smtp-mail.outlook.com | 587 | outlook.office365.com | 993 |
| QQ邮箱 | smtp.qq.com | 587 | imap.qq.com | 993 |
| 163邮箱 | smtp.163.com | 465 | imap.163.com | 993 |

**⚠️ 重要提示:**
- Gmail/Outlook 必须使用"应用专用密码"，不能用账户密码
- QQ/163邮箱需要开启 SMTP/IMAP 服务并使用"授权码"

### 4. `change_agent_setting` - 修改 Agent 设置

修改运行中 Agent 的配置。

**参数:**
- `agent_name` (必需): Agent 名称
- `setting_key` (必需): 设置键 (description, backend_model, skills)
- `setting_value` (必需): 新的设置值

**示例:**
```
# 修改描述（立即生效）
change_agent_setting(
    agent_name="researcher",
    setting_key="description",
    setting_value="资深研究专家"
)

# 修改模型（需要重载）
change_agent_setting(
    agent_name="researcher",
    setting_key="backend_model",
    setting_value="claude-opus-4"
)

# 修改技能（需要重载）
change_agent_setting(
    agent_name="researcher",
    setting_key="skills",
    setting_value="web_search,file,email"
)
```

### 5. `list_agents` - 列出所有 Agent

查看系统中所有 Agent 的状态。

**示例:**
```
list_agents()
```

**返回示例:**
```
系统中的 Agent（共 3 个）：

** User **
   描述: 用户代理
   状态: 运行中
   模型: default_llm
   技能: email, base
   邮箱: 0 封未读邮件

** assistant **
   描述: AI助手
   状态: 运行中
   模型: claude-sonnet-4-6
   技能: email, base, scheduler
   邮箱: 2 封未读邮件
```

### 6. `system_status` - 查看系统状态

查看 AgentMatrix 系统的整体状态。

**示例:**
```
system_status()
```

**返回示例:**
```
=== AgentMatrix 系统状态 ===

📊 Agent 数量: 3
📬 PostOffice: 运行中
⏰ TaskScheduler: 运行中
📧 EmailProxy: 运行中
🔍 LLM Monitor: 运行中
```

### 7. `remove_agent` - 删除 Agent

从系统中移除指定的 Agent。

**参数:**
- `agent_name` (必需): 要删除的 Agent 名称
- `delete_config` (可选): 是否同时删除配置文件（默认 false）

**示例:**
```
# 只从运行时移除（保留配置文件）
remove_agent(agent_name="old_agent")

# 同时删除配置文件
remove_agent(agent_name="old_agent", delete_config=True)
```

---

## 使用方法

### 1. 在 Agent 配置中启用

在 Agent 的 `.yml` 配置文件中添加 `matrix_admin` 到 skills 列表：

```yaml
name: admin
description: 系统管理员
class_name: agentmatrix.agents.base.BaseAgent
backend_model: default_llm
skills:
  - base
  - email
  - matrix_admin
```

### 2. 通过对话使用

启用后，可以直接与 Agent 对话来管理系统：

```
你: 帮我添加一个叫 researcher 的 Agent
你: 查看系统状态
你: 重载 assistant Agent
你: 配置 Email Proxy
```

### 3. Email Proxy 使用示例

**配置 Email Proxy:**
```
你: 配置 Email Proxy

SystemAdmin:
  好的！我来帮你配置 Email Proxy。

  ## 📋 需要的信息

  **1. 邮箱服务商**
     你用的是哪个邮箱服务商？
     - Gmail
     - Outlook
     - QQ邮箱
     - 163邮箱

  **2. 邮箱地址**
     - Matrix 邮箱（用于发送）：_______@gmail.com
     - 用户邮箱（用于接收）：_______@gmail.com

  **3. 服务器信息**
     - SMTP 服务器：smtp.gmail.com
     - SMTP 端口：587
     - IMAP 服务器：imap.gmail.com
     - IMAP 端口：993

  **4. 凭证信息**
     ⚠️ **重要提示**：
     - Gmail/Outlook 需要使用"应用专用密码"
     - 不能使用账户登录密码
     - 我可以指导你如何生成应用密码

  请提供以上信息，我来完成配置。
```

**通过邮件与 Agent 对话:**
```
From: your-email@gmail.com
To: matrix@gmail.com
Subject: @Researcher 查找最新的 AI 论文

请帮我找最近一周的 AI 论文，重点关注大语言模型领域。
```

Email Proxy 会：
1. 接收邮件
2. 识别 @Researcher → 转发给 Researcher Agent
3. Agent 处理并回复邮件

---

## 📧 Email Proxy 工作原理

### IMAP 邮件拉取流程

```
┌─────────────────┐
│  用户邮箱       │
│ (IMAP Server)  │
└────────┬────────┘
         │
         │ 每 30 秒检查一次
         │
         ▼
┌─────────────────┐
│  Email Proxy    │
│  - 过滤发件人   │
│  - 解析 @mention │
│  - 转换格式      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PostOffice     │
│  - 路由到 Agent  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  目标 Agent     │
│  - 处理任务     │
└─────────────────┘
```

### 邮件过滤规则

**只处理来自 user_mailbox 的邮件**：
- 发件人 = `user_mailbox` → 处理
- 发件人 ≠ `user_mailbox` → 忽略

**收件人识别（优先级）**：
1. 主题中的 @mention（最高优先级）
2. 正文第一行的 @mention
3. 默认发给 User Agent

### Session 管理

- 自动在主题中添加 `[Session: xxx]` 标记
- 用于关联同一对话的多封邮件
- Agent 可以识别并继续之前的对话

---

## 依赖

- `base`: 基础技能（自动加载）

---

## 注意事项

1. **权限**: 只有具有 `matrix_admin` skill 的 Agent 才能执行这些操作
2. **重载**: 某些设置修改（如 backend_model, skills）需要重载 Agent 才能生效
3. **配置文件**: `add_agent` 创建的配置文件保存在 `agent_config_dir/` 目录
4. **Email Proxy**:
   - 配置需要正确的 SMTP/IMAP 服务器信息
   - Gmail/Outlook 必须使用应用专用密码
   - 每 30 秒拉取一次邮件

---

## 技术细节

- **Skill 类名**: `Matrix_adminSkillMixin`
- **Skill 名称**: `matrix_admin`
- **文件路径**: `src/agentmatrix/skills/matrix_admin/skill.py`
- **自动发现**: 支持 SKILL_REGISTRY 的 Lazy Load 机制

---

## 📚 相关文档

- `docs/email_proxy_config_guide.md` - Email Proxy 详细配置指南
- `docs/system_admin_guide.md` - SystemAdmin 使用指南
- `src/agentmatrix/services/email_proxy_service.py` - EmailProxy 服务实现
