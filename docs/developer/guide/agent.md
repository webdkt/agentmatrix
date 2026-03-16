# Agent Development

Agent 开发指南。

## Agent 配置

Agent 通过 YAML 配置文件定义。

```yaml
name: MyAgent
description: "Agent 描述"
class_name: "agentmatrix.agents.micro_agent.MicroAgent"
backend_model: default_llm

skills:
  - browser
  - file

persona:
  base: |
    你是 MyAgent，负责...

prompts:
  task_prompt: "任务提示模板"
```

### 关键字段

| 字段 | 说明 | 必需 |
|------|------|------|
| `name` | Agent 唯一标识 | Yes |
| `class_name` | 完整类路径 | Yes |
| `backend_model` | 使用的 LLM | No (default: default_llm) |
| `skills` | Skill 列表 | No |
| `persona.base` | 系统角色定义 | Yes |
| `prompts.task_prompt` | 任务提示 | No |

### class_name 格式

使用完整 Python 路径：
- 标准 MicroAgent: `agentmatrix.agents.micro_agent.MicroAgent`
- 自定义 Agent: `my_package.MyAgentClass`

## 创建 Agent

### 1. 创建配置文件

```bash
# 在 .matrix/configs/agents/ 下创建
mkdir -p .matrix/configs/agents/my_agent
cat > .matrix/configs/agents/my_agent/profile.yml << 'EOF'
name: MyAgent
description: "示例 Agent"
class_name: "agentmatrix.agents.micro_agent.MicroAgent"
backend_model: default_llm

skills:
  - base
  - browser
  - file

persona:
  base: |
    你是一个助手...
EOF
```

### 2. 配置 LLM

在 `.matrix/configs/agents/llm_config.json` 定义后端：

```json
{
  "default_llm": {
    "type": "openai",
    "model": "gpt-4",
    "api_key": "${OPENAI_API_KEY}"
  }
}
```

### 3. 重启加载

Agent 在系统启动时自动加载配置文件。

## 运行时访问

Agent 运行时可访问以下属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.name` | str | Agent 名称 |
| `self.brain` | LLMClient | LLM 客户端 |
| `self.cerebellum` | Cerebellum | Action 解析器 |
| `self.session_manager` | SessionManager | 会话管理 |
| `self.runtime.paths` | MatrixPaths | 路径管理 |

## 自定义 Agent 类

继承 MicroAgent 创建自定义 Agent：

```python
from agentmatrix.agents.micro_agent import MicroAgent
from agentmatrix.core.action import register_action

class MyCustomAgent(MicroAgent):
    
    @register_action(
        short_desc="自定义 Action",
        description="执行自定义逻辑",
        param_infos={}
    )
    async def custom_action(self) -> str:
        # 访问运行时资源
        work_dir = self.runtime.paths.get_agent_work_files_dir(
            self.name, self.current_task_id
        )
        return f"Working in {work_dir}"
```

配置文件：

```yaml
class_name: "my_module.MyCustomAgent"
```

## 最佳实践

1. **Skill 优先**：通用功能做成 Skill，不要写在 Agent 类里
2. **配置分离**：Prompts 放配置文件，不要硬编码
3. **依赖声明**：Skill 通过 `_skill_dependencies` 声明依赖
4. **错误处理**：Action 内捕获异常，返回友好错误信息
