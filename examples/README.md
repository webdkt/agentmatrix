# AgentMatrix 示例

本目录包含 AgentMatrix 框架的使用示例和参考配置。

## 📁 目录结构

```
examples/
└── MyWorld/           # 示例 Agent 世界
    ├── agents/        # 示例 Agent 配置文件
    │   ├── researcher.yml
    │   ├── User.yml
    │   └── ...
    ├── workspace/     # 工作区（包含浏览器数据、会话历史等）
    └── README.md      # MyWorld 详细说明
```

## 🚀 快速开始

### 1. 创建你自己的世界

```bash
# 复制示例世界作为起点
cp -r examples/MyWorld MyWorld

# 或者创建新的世界目录
mkdir MyWorld
```

### 2. 配置你的 Agent

编辑 `MyWorld/agents/` 下的 YAML 配置文件，定义你的 Agent：

```yaml
# MyWorld/agents/my-agent.yml
name: MyAgent
description: 我的自定义 Agent
module: agentmatrix.agents.base
class_name: BaseAgent

mixins:
  - agentmatrix.skills.filesystem.FileSkillMixin
  - agentmatrix.skills.web_searcher.WebSearcherMixin

system_prompt: |
  你是一个有帮助的助手，专注于研究和分析。

backend_model: gpt-4
cerebellum_model: gpt-3.5-turbo
```

### 3. 启动 AgentMatrix

```bash
# 使用 Web 界面
python server.py --matrix-world ./MyWorld

# 或使用 CLI
python main.py --matrix-world ./MyWorld
```

## 📖 示例说明

### MyWorld

MyWorld 是一个完整的示例世界，展示了如何：

- ✨ 配置多个不同角色的 Agent（研究员、用户等）
- 🔧 为 Agent 添加不同的技能（文件操作、网络搜索、爬虫等）
- 💾 持久化会话和状态
- 🌐 集成浏览器自动化
- 🔍 使用向量数据库进行语义搜索

**详细说明**: 参见 [MyWorld/README.md](MyWorld/README.md)

## 🎯 常见使用场景

### 场景 1: 研究助手

创建一个专门用于信息收集和研究的 Agent：

```yaml
name: ResearchAssistant
description: 研究和信息收集专家
mixins:
  - agentmatrix.skills.web_searcher.WebSearcherMixin
  - agentmatrix.skills.crawler_helpers.CrawlerHelpersMixin
  - agentmatrix.skills.notebook.NotebookMixin
```

### 场景 2: 文件管理器

创建一个用于文件组织和管理的 Agent：

```yaml
name: FileManager
description: 文件操作和组织专家
mixins:
  - agentmatrix.skills.filesystem.FileSkillMixin
  - agentmatrix.skills.notebook.NotebookMixin
```

### 场景 3: 项目管理员

创建一个用于项目规划和任务分解的 Agent：

```yaml
name: ProjectManager
description: 项目规划和任务管理专家
mixins:
  - agentmatrix.skills.project_management.ProjectManagementMixin
  - agentmatrix.skills.notebook.NotebookMixin
```

## 📚 更多资源

- [核心框架文档](../docs/)
- [Agent 配置指南](../docs/agent-and-micro-agent-design.md)
- [技能开发指南](../docs/skill-architecture-cleanup-summary.md)
- [Web 应用使用](../web/README.md)

## ⚠️ 注意事项

1. **工作区隔离**: 每个 World 的 `workspace/` 目录包含独立的数据（会话、向量数据库、浏览器配置等），不同 World 之间完全隔离。

2. **版本控制**: 建议将 Agent 配置文件（`*.yml`）纳入版本控制，但 `workspace/` 目录应被 `.gitignore` 忽略。

3. **API 密钥**: 在启动前确保设置了必要的环境变量（如 `OPENAI_API_KEY`）。

4. **资源清理**: 定期清理 `workspace/` 中的旧数据以节省磁盘空间。

## 🤝 贡献示例

欢迎提交更多示例！如果你创建了有趣的 Agent 配置或使用场景，可以：

1. Fork 本项目
2. 在 `examples/` 下添加你的示例
3. 提交 Pull Request

我们特别欢迎：
- 🎨 创新的 Agent 配置
- 📚 完整的使用教程
- 🛠️ 特定场景的解决方案
- 📊 性能优化示例
