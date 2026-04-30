"""
CLI Agent — 基于 AgentMatrix Core 的终端 Agent。

使用 Textual TUI 框架提供交互界面。
内置 file、shell 两个 skill，可直接对话。

用法：
    python main.py                    # 交互模式（自动检测 Textual）
    python main.py -m openai:gpt-4o   # 指定 LLM
    python main.py --api-key sk-xxx   # 指定 API key
    python main.py --simple           # 强制简单模式（无 TUI）
"""

import asyncio
import sys
import os
import argparse
import logging
from pathlib import Path

# 将当前目录和项目 src 目录加入 sys.path
# 当前目录：方便导入 cli_shell, cli_config 等模块
# src 目录：让 agentmatrix 包可导入
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from cli_config import CLIConfig
from cli_shell import CLIShell
from cli_session import InMemorySessionStore
from skills.base_skill import BaseSkillMixin
from skills.file_skill import FileSkillMixin
from skills.shell_skill import ShellSkillMixin

from agentmatrix.core.micro_agent import MicroAgent
from agentmatrix.core.skills.registry import SKILL_REGISTRY
from agentmatrix.core.signals import TextSignal


# ── 注册内置 Skills ─────────────────────────────────────────

SKILL_REGISTRY.register_python_mixin("base", BaseSkillMixin)
SKILL_REGISTRY.register_python_mixin("file", FileSkillMixin)
SKILL_REGISTRY.register_python_mixin("shell", ShellSkillMixin)


# ── System Prompt ────────────────────────────────────────────

DEFAULT_SYSTEM_PROMPT = """\
你是一个有用的 AI 助手，运行在用户的终端环境中。

你可以通过工具来完成用户的任务：
- 获取当前时间
- 读写文件
- 执行 shell 命令

请用中文回复。当你需要执行操作时，使用 <action_script> 块。
"""


# ── 事件消费 ─────────────────────────────────────────────────

class EventConsumer:
    """消费 CoreEvent，格式化输出。"""

    def __init__(self, micro_agent, output_cb):
        self.agent = micro_agent
        self.output_cb = output_cb  # async def cb(text, style)
        self._task = None

    def start(self):
        self._task = asyncio.create_task(self._run())

    def stop(self):
        if self._task:
            self._task.cancel()

    async def _run(self):
        while True:
            try:
                event = await self.agent.event_queue.get()
                await self._dispatch(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.warning(f"EventConsumer error: {e}")

    async def _dispatch(self, event):
        et, en, d = event.event_type, event.event_name, event.detail
        cb = self.output_cb

        if et == "think" and en == "brain":
            thought = d.get("thought", "")
            if thought:
                await cb(f"\n🤖 {thought}", "")

        elif et == "action" and en == "detected":
            await cb(f"[action] {', '.join(d.get('actions', []))}", "bold cyan")

        elif et == "action" and en == "started":
            await cb(f"[action] {d.get('action_name', '?')} ...", "cyan")

        elif et == "action" and en == "completed":
            name = d.get("action_name", "?")
            status = d.get("status", "ok")
            preview = d.get("result_preview", "")
            if status == "ok":
                await cb(f"[action] {name} -> {preview[:200]}", "green")
            elif status == "error":
                await cb(f"[action] {name} 失败: {preview}", "red")

        elif et == "action" and en == "error":
            await cb(f"[action] {d.get('action_name', '?')} 错误: {d.get('error_message', '')}", "red")


# ── Agent 会话管理 ───────────────────────────────────────────

class AgentChat:
    """管理 MicroAgent 的多轮对话生命周期。"""

    def __init__(self, config: CLIConfig, output_cb):
        self.config = config
        self.output_cb = output_cb
        self.shell = CLIShell(config)
        self.session_store = InMemorySessionStore()
        self.available_skills = ["base", "file", "shell"]
        self._micro_agent = None
        self._event_consumer = None
        self._busy = False  # agent 正在执行

    def _create_micro_agent(self) -> MicroAgent:
        """创建新的 MicroAgent 实例。"""
        return MicroAgent(
            parent=self.shell,
            name=self.config.agent_name,
            available_skills=self.available_skills,
            system_prompt=self.config.system_prompt,
            compression_token_threshold=self.config.compression_token_threshold,
        )

    async def send(self, user_text: str):
        """发送用户消息并执行 agent。

        每次调用创建新的 MicroAgent（复用 session_store 保持历史）。
        """
        if self._busy:
            await self.output_cb("⏳ Agent 正在处理中，请等待...", "yellow")
            return

        self._busy = True
        try:
            await self._do_send(user_text)
        finally:
            self._busy = False

    async def _do_send(self, user_text: str):
        # 显示用户消息
        await self.output_cb(f"\n👤 {user_text}", "bold")

        # 创建 MicroAgent（每次新的，但 session_store 保持历史）
        ma = self._create_micro_agent()

        # 启动事件消费
        ec = EventConsumer(ma, self.output_cb)
        ec.start()

        try:
            # 注入用户信号
            ma.signal_queue.put_nowait(
                TextSignal(text=user_text, type_name="user_input")
            )

            # 执行（task="" → 信号驱动）
            await ma.execute(
                run_label="CLI Chat",
                task="",
                session_store=self.session_store,
            )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.output_cb(f"[Error] {e}", "red")
        finally:
            ec.stop()

    def clear(self):
        """清空对话历史。"""
        self.session_store.clear()


# ── CLI 命令处理 ─────────────────────────────────────────────

async def handle_command(cmd_text: str, chat: AgentChat, output_cb) -> str:
    """处理 / 命令。返回 'quit' 表示退出。"""
    parts = cmd_text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/quit", "/exit"):
        return "quit"

    if cmd == "/help":
        lines = [
            "命令:",
            "  /set-llm <provider:model>  设置 LLM（如 openai:gpt-4o）",
            "  /set-llm <url:model>       设置自定义 endpoint + model",
            "  /url <endpoint>            设置 API endpoint URL",
            "  /api-key <key>             设置 API Key",
            "  /system-prompt <file>      加载 system prompt 文件",
            "  /skills <dir>              指定 MD skill 目录",
            "  /status                    显示当前配置",
            "  /prompt                    显示完整 system prompt",
            "  /clear                     清空对话历史",
            "  /quit                      退出",
        ]
        for line in lines:
            await output_cb(line, "dim")

    elif cmd == "/set-llm":
        if not arg:
            await output_cb("用法: /set-llm <provider:model> 或 <url:model>", "yellow")
        else:
            chat.config.set_llm(arg)
            chat.shell.rebuild_brain(chat.config)
            await output_cb(f"✅ LLM: {chat.config.llm_model} @ {chat.config.llm_url}", "green")

    elif cmd == "/url":
        if not arg:
            await output_cb("用法: /url <endpoint_url>", "yellow")
        else:
            chat.config.set_url(arg)
            chat.shell.rebuild_brain(chat.config)
            await output_cb(f"✅ URL: {chat.config.llm_url}", "green")

    elif cmd == "/api-key":
        if not arg:
            await output_cb("用法: /api-key sk-xxx", "yellow")
        else:
            chat.config.llm_api_key = arg
            chat.shell.rebuild_brain(chat.config)
            await output_cb("✅ API Key 已更新", "green")

    elif cmd == "/system-prompt":
        if not arg:
            await output_cb("用法: /system-prompt <file>", "yellow")
        else:
            p = Path(arg).expanduser()
            if p.exists():
                chat.config.system_prompt = p.read_text(encoding="utf-8")
                chat.config.system_prompt_file = str(p)
                await output_cb(f"✅ System prompt: {p.name}", "green")
            else:
                await output_cb(f"❌ 文件不存在: {arg}", "red")

    elif cmd == "/skills":
        chat.config.skill_dir = arg or None
        await output_cb(f"✅ Skill 目录: {arg or '(已清除)'}", "green")

    elif cmd == "/status":
        c = chat.config
        await output_cb(f"LLM: {c.llm_model}", "dim")
        await output_cb(f"Endpoint: {c.llm_url}", "dim")
        await output_cb(f"API Key: {'已设置 (' + c.llm_api_key[:8] + '...)' if c.llm_api_key else '未设置'}", "dim")
        await output_cb(f"Prompt: {c.system_prompt_file or '(内置)'}", "dim")

    elif cmd == "/prompt":
        # 创建临时 MicroAgent 获取完整 prompt
        ma = chat._create_micro_agent()
        full_prompt = ma._build_system_prompt()
        await output_cb("─── System Prompt ───", "bold")
        await output_cb(full_prompt, "")
        await output_cb("─── End ───", "bold")

    elif cmd == "/clear":
        chat.clear()
        await output_cb("✅ 对话已清空", "green")

    else:
        await output_cb(f"未知命令: {cmd}", "yellow")

    return None


# ── Textual TUI 模式 ────────────────────────────────────────

def run_textual(config: CLIConfig):
    """启动 Textual TUI。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, RichLog, Input
    from rich.text import Text

    class CLIAgentApp(App):
        CSS = """
        Screen { layout: vertical; }
        #output { height: 1fr; border: solid $primary; padding: 0 1; }
        #input-area { height: 3; dock: bottom; margin: 0 0 1 0; }
        """
        BINDINGS = [("ctrl+c", "quit", "Quit")]

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._chat = None

        def compose(self) -> ComposeResult:
            yield Header()
            yield RichLog(id="output", markup=True, wrap=True)
            yield Input(placeholder="输入消息或 /help ...", id="input-area")

        async def on_mount(self):
            log = self.query_one("#output", RichLog)

            async def output_cb(text, style=""):
                if style:
                    log.write(Text(text, style=style))
                else:
                    log.write(text)

            self._chat = AgentChat(config, output_cb)
            await output_cb("✅ CLI Agent 已启动", "bold green")
            await output_cb(f"   模型: {config.llm_model}", "dim")
            await output_cb(f"   Skills: {', '.join(self._chat.available_skills)}", "dim")
            await output_cb("   输入消息开始对话，/help 查看命令\n", "dim")

            if not config.llm_api_key:
                await output_cb("⚠️  未设置 API Key，请先: /api-key sk-xxx", "yellow")

        async def on_input_submitted(self, event: Input.Submitted):
            text = event.value.strip()
            self.query_one("#input-area", Input).value = ""
            if not text:
                return

            if text.startswith("/"):
                result = await handle_command(text, self._chat, self._chat.output_cb)
                if result == "quit":
                    self.exit()
                return

            # 普通消息：后台执行 agent
            asyncio.create_task(self._chat.send(text))

        async def action_quit(self):
            self.exit()

    app = CLIAgentApp()
    app.run()


# ── 简单模式（无 Textual）────────────────────────────────────

async def run_simple(config: CLIConfig):
    """简单交互模式（fallback）。"""

    async def output_cb(text, style=""):
        print(text)

    chat = AgentChat(config, output_cb)
    print(f"✅ CLI Agent 已启动 (简单模式)")
    print(f"   模型: {config.llm_model}")
    print(f"   Skills: {', '.join(chat.available_skills)}")
    print(f"   /help 查看命令，Ctrl+C 退出\n")

    if not config.llm_api_key:
        print("⚠️  未设置 API Key，请先: /api-key sk-xxx\n")

    try:
        while True:
            try:
                text = input("> ").strip()
            except EOFError:
                break

            if not text:
                continue

            if text.startswith("/"):
                result = await handle_command(text, chat, output_cb)
                if result == "quit":
                    break
                continue

            await chat.send(text)

    except KeyboardInterrupt:
        pass
    finally:
        print("\n👋 再见！")


# ── 入口 ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AgentMatrix CLI Agent")
    parser.add_argument("-m", "--model", help="LLM (e.g. openai:gpt-4o)")
    parser.add_argument("--url", help="API endpoint URL")
    parser.add_argument("--api-key", help="API key")
    parser.add_argument("--system-prompt", help="System prompt file")
    parser.add_argument("--skills", help="MD skill directory")
    parser.add_argument("--simple", action="store_true", help="Simple mode (no TUI)")
    args = parser.parse_args()

    config = CLIConfig()

    # 环境变量
    if os.environ.get("OPENAI_API_KEY"):
        config.llm_api_key = os.environ["OPENAI_API_KEY"]

    # 命令行参数
    if args.url:
        config.set_url(args.url)
    if args.model:
        config.set_llm(args.model)
    if args.api_key:
        config.llm_api_key = args.api_key
    if args.system_prompt:
        p = Path(args.system_prompt).expanduser()
        if p.exists():
            config.system_prompt = p.read_text(encoding="utf-8")
            config.system_prompt_file = str(p)
    if args.skills:
        config.skill_dir = args.skills

    # 选择模式
    if not args.simple:
        try:
            import textual
            run_textual(config)
            return
        except ImportError:
            pass

    asyncio.run(run_simple(config))


if __name__ == "__main__":
    main()
