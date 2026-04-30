# CLI Agent Tutorial

基于 AgentMatrix Core 的终端 Agent 示例。

## 功能

- 多轮对话（保持上下文）
- 内置 Skills：base（获取时间）、file（读写文件）、shell（执行命令）
- Textual TUI 界面（可选）
- 简单模式（纯终端）

## 快速开始

```bash
# 安装依赖
pip install textual  # 可选，用于 TUI 界面

# 设置 API Key
export OPENAI_API_KEY=sk-xxx

# 运行
cd tutorial/cli-agent
python main.py -m openai:gpt-4o
```

## 命令

| 命令 | 功能 |
|------|------|
| `/set-llm openai:gpt-4o` | 切换 LLM |
| `/api-key sk-xxx` | 设置 API Key |
| `/system-prompt <file>` | 加载 system prompt |
| `/skills <dir>` | MD skill 目录 |
| `/status` | 查看配置 |
| `/clear` | 清空对话 |
| `/quit` | 退出 |

## 示例对话

```
👤 列出当前目录的文件
[action] file.list_dir 开始...
[action] file.list_dir -> 📁 skills/  📄 main.py  📄 cli_shell.py ...
🤖 当前目录下有以下文件和目录...

👤 创建一个 hello.txt 写入 hello world
[action] file.write 开始...
[action] file.write -> [Done] 已写入 hello.txt (11 字符)
🤖 已创建 hello.txt 并写入 "hello world"。

👤 执行 ls -la
[action] shell.bash 开始...
[action] shell.bash -> total 32 ...
🤖 命令执行结果如下...
```

## 架构

```
┌─────────────────────────────────────┐
│  main.py — Textual TUI / 简单模式    │
│  AgentChat — 多轮对话管理             │
├─────────────────────────────────────┤
│  cli_shell.py — AgentShell 实现      │
│  cli_config.py — 配置管理            │
│  cli_session.py — 内存 SessionStore  │
├─────────────────────────────────────┤
│  MicroAgent — Core 执行引擎          │
│  Skills: file, shell                │
└─────────────────────────────────────┘
```

## 文件结构

```
tutorial/cli-agent/
├── main.py              # 入口 + TUI + 简单模式
├── cli_shell.py         # AgentShell 协议实现
├── cli_config.py        # 配置管理（LLM、API Key）
├── cli_session.py       # 内存 SessionStore
├── skills/
│   ├── base_skill.py    # base.get_current_datetime
│   ├── file_skill.py    # file.read, file.write, file.list_dir
│   └── shell_skill.py   # shell.bash
└── README.md
```
