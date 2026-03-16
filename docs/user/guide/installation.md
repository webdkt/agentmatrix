# Installation

安装 AgentMatrix。

## 系统要求

- Python 3.9+
- pip 或 uv

## 安装方式

### 方式一：pip 安装

```bash
pip install matrix-for-agents
```

### 方式二：源码安装

```bash
git clone <repo-url>
cd agentmatrix
pip install -e .
```

## 启动 Web 应用

```bash
python server.py
```

访问 http://localhost:8000

## 目录初始化

首次启动自动创建目录结构：

```
MatrixWorld/
├── .matrix/          # 系统数据
└── workspace/        # 用户工作区
```

## 配置 LLM

创建 `.matrix/configs/agents/llm_config.json`:

```json
{
  "default_llm": {
    "type": "openai",
    "model": "gpt-4o",
    "api_key": "${OPENAI_API_KEY}"
  }
}
```

支持的环境变量：
- `OPENAI_API_KEY`: OpenAI API Key

## 验证安装

访问 Web UI，创建新对话，验证 Agent 正常响应。
