# CLI 教程

`tutorial/cli-agent/` 是一个基于 AgentMatrix Core 的终端 Agent 最小示例。它展示了如何实现 `AgentShell` 协议、如何配置 Brain 和 Cerebellum、如何运行 MicroAgent。

---

## 定位

这个教程的目标是让你理解 AgentMatrix 的核心架构，并作为构建自己应用的起点。

代码量约 200 行，实现了：
- AgentShell 协议接口
- 内存 SessionStore
- 多轮对话管理
- 基础 Skill（file、shell、base）

---

## 适用场景

- 想理解 AgentShell 协议和 Core 引擎如何工作的开发者
- 想把 MicroAgent 集成到自己应用中的开发者
- 想在终端环境中使用 Agent 的用户

---

## 快速开始

```bash
cd tutorial/cli-agent
export OPENAI_API_KEY=sk-xxx
python main.py -m openai:gpt-4o
```

如果安装了 Textual，会自动使用 TUI 界面；否则使用简单模式。

---

## 教程内容

CLI 教程的详细文档请查看教程目录内的 README：

→ **[tutorial/cli-agent/README.md](../../tutorial/cli-agent/)**

该 README 包含：
- 功能说明
- 命令参考
- 架构说明
- 文件结构

---

## 从这个教程出发

如果你想基于 CLI 教程构建自己的应用：

1. 复制 `tutorial/cli-agent/` 目录
2. 修改 `cli_shell.py` 中的 Shell 实现，适配你的场景
3. 添加或替换 Skill，扩展 Agent 的能力
4. 修改 `main.py` 的交互界面，集成到你的应用中

CLI 教程的代码结构和注释足够清晰，可以作为理解整个 AgentMatrix 架构的入口点。
