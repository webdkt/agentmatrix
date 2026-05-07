"""
CLI Agent — 基于 AgentMatrix Core 的终端 Agent。

使用 Textual TUI 框架提供交互界面。
用户输入非阻塞：投入 input_queue，Agent 异步处理。

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
import importlib
import logging
from pathlib import Path

# 将当前目录和项目 src 目录加入 sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from cli_config import CLIConfig, load_config_file, apply_config_file, load_config
from cli_agent import CLIAgent
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


# ── 外部 Python Skill 发现 ──────────────────────────────────

def _resolve_module_path(fs_path: Path) -> str | None:
    """
    尝试将文件系统路径转换为 Python 模块路径（dotted name）。
    """
    resolved = fs_path.resolve()
    for sp in sys.path:
        try:
            sp_resolved = Path(sp).resolve()
        except Exception:
            continue
        try:
            rel = resolved.relative_to(sp_resolved)
        except ValueError:
            continue
        parts = [p for p in rel.parts if not p.endswith('.py')]
        module_path = ".".join(parts)
        try:
            importlib.import_module(module_path)
            return module_path
        except ImportError:
            continue
    return None


def discover_python_skills(skill_dir: str) -> list[str]:
    """
    扫描目录发现可用的 Python Skill。
    """
    found = []
    p = Path(skill_dir).resolve()
    if not p.is_dir():
        logging.warning(f"Skill 目录不存在: {p}")
        return found

    for child in sorted(p.iterdir()):
        if child.is_dir() and (child / "skill.py").exists():
            found.append(child.name)

    for f in sorted(p.glob("*_skill.py")):
        name = f.stem.removesuffix("_skill")
        if name not in found:
            found.append(name)

    return found


def register_skill_dirs(dirs: list[str]) -> list[str]:
    """注册外部 Python skill 目录并返回发现的 skill 名称。"""
    all_skills = []
    for d in dirs:
        d = os.path.expanduser(d)
        skills = discover_python_skills(d)
        if skills:
            search_path = _resolve_module_path(Path(d)) or d
            SKILL_REGISTRY.add_search_path(search_path)
            all_skills.extend(skills)
            logging.info(f"从 {d} 发现 skills: {skills} (search_path={search_path})")
        else:
            logging.warning(f"在 {d} 中未发现 Python Skill")
    return all_skills


# ── System Prompt ────────────────────────────────────────────

DEFAULT_SYSTEM_PROMPT = """\
你是一个有用的 AI 助手，运行在用户的终端环境中。

你可以通过工具来完成用户的任务：
- 获取当前时间
- 读写文件
- 执行 shell 命令

请用中文回复。当你需要执行操作时，使用 <action_script> 块。
"""


# ── Agent 会话管理 ───────────────────────────────────────────

class AgentChat:
    """管理 CLIAgent 的会话。

    用户输入通过 agent.input_queue 异步投递，不阻塞。
    Agent 后台运行 _main_loop 消费信号。
    """

    def __init__(self, config: CLIConfig, output_cb):
        self.config = config
        self.output_cb = output_cb
        self.agent = CLIAgent(config, output_cb)

        # 从配置文件的 skill_dirs 发现外部 skills
        if config.skill_dirs:
            register_skill_dirs(config.skill_dirs)

        # 如果配置了 skills 列表，覆盖默认值
        if config.skills:
            self.agent.skills = list(config.skills)

    async def send(self, user_text: str):
        """非阻塞：显示消息 + 投入 input_queue。"""
        await self.output_cb(f"\n👤 {user_text}", "bold")
        self.agent.input_queue.put_nowait(
            TextSignal(text=user_text, type_name="user_input")
        )

    def new_session(self):
        """创建新 session（/new 命令）。"""
        self.agent.new_session()


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
            "  /new                       新会话（重新加载配置和 skills）",
            "  /reload-agent              重新加载 skills（不清空配置）",
            "  /restart-with-skill <s1> <s2> ...  重启并切换 skills",
            "  /set-llm <provider:model>  设置 LLM（如 openai:gpt-4o）",
            "  /set-llm <url:model>       设置自定义 endpoint + model",
            "  /url <endpoint>            设置 API endpoint URL",
            "  /api-key <key>             设置 API Key",
            "  /system-prompt <file>      加载 system prompt 文件",
            "  /skill-dir <dir>           添加 Python skill 目录",
            "  /save-msg                  保存会话历史到 messages.json",
            "  /status                    显示当前配置",
            "  /prompt                    显示完整 system prompt",
            "  /clear                     清空对话历史（等同 /new）",
            "  /quit                      退出",
        ]
        for line in lines:
            await output_cb(line, "dim")

    elif cmd == "/set-llm":
        if not arg:
            await output_cb("用法: /set-llm <provider:model> 或 <url:model>", "yellow")
        else:
            chat.config.set_llm(arg)
            chat.agent.rebuild_brain(chat.config)
            await output_cb(f"LLM: {chat.config.llm_model} @ {chat.config.llm_url}", "green")

    elif cmd == "/url":
        if not arg:
            await output_cb("用法: /url <endpoint_url>", "yellow")
        else:
            chat.config.set_url(arg)
            chat.agent.rebuild_brain(chat.config)
            await output_cb(f"URL: {chat.config.llm_url}", "green")

    elif cmd == "/api-key":
        if not arg:
            await output_cb("用法: /api-key sk-xxx", "yellow")
        else:
            chat.config.llm_api_key = arg
            chat.agent.rebuild_brain(chat.config)
            await output_cb("API Key 已更新", "green")

    elif cmd == "/system-prompt":
        if not arg:
            await output_cb("用法: /system-prompt <file>", "yellow")
        else:
            p = Path(arg).expanduser()
            if p.exists():
                chat.config.system_prompt = p.read_text(encoding="utf-8")
                chat.config.system_prompt_file = str(p)
                await output_cb(f"System prompt: {p.name}", "green")
            else:
                await output_cb(f"文件不存在: {arg}", "red")

    elif cmd == "/skills":
        chat.config.skill_dir = arg or None
        await output_cb(f"Skill 目录: {arg or '(已清除)'}", "green")

    elif cmd == "/skill-dir":
        if not arg:
            await output_cb("用法: /skill-dir <dir>", "yellow")
        else:
            extra = register_skill_dirs([arg])
            if extra:
                chat.agent.skills.extend(extra)
                await output_cb(f"加载 skills: {', '.join(extra)}", "green")
            else:
                await output_cb(f"在 {arg} 中未发现 Python Skill", "red")

    elif cmd == "/restart-with-skill":
        skills = arg.split()
        if not skills:
            await output_cb("用法: /restart-with-skill skill1 skill2 ...", "yellow")
        else:
            for s in skills:
                SKILL_REGISTRY.unload_skill(s)
            chat.agent.skills = skills
            chat.new_session()
            await output_cb(f"Agent 已重启，skills: {', '.join(skills)}", "green")

    elif cmd == "/reload-agent":
        data = load_config_file()
        if data:
            apply_config_file(chat.config, data)
            chat.agent.rebuild_brain(chat.config)
        for s in chat.agent.skills:
            SKILL_REGISTRY.unload_skill(s)
        if chat.config.skill_dirs:
            register_skill_dirs(chat.config.skill_dirs)
        chat.new_session()
        await output_cb(f"Agent 已重新加载", "green")
        await output_cb(f"   Skills: {', '.join(chat.agent.skills)}", "dim")

    elif cmd == "/new":
        data = load_config_file()
        if data:
            apply_config_file(chat.config, data)
            chat.agent.rebuild_brain(chat.config)
        for s in chat.agent.skills:
            SKILL_REGISTRY.unload_skill(s)
        if chat.config.skill_dirs:
            register_skill_dirs(chat.config.skill_dirs)
        if chat.config.skills:
            chat.agent.skills = list(chat.config.skills)
        chat.new_session()
        await output_cb("新会话已启动（配置和 skills 已重新加载）", "bold green")
        await output_cb(f"   模型: {chat.config.llm_model}", "dim")
        await output_cb(f"   Skills: {', '.join(chat.agent.skills)}", "dim")

    elif cmd == "/status":
        c = chat.config
        await output_cb(f"LLM: {c.llm_model}", "dim")
        await output_cb(f"Endpoint: {c.llm_url}", "dim")
        await output_cb(
            f"API Key: {'已设置 (' + c.llm_api_key[:8] + '...)' if c.llm_api_key else '未设置'}",
            "dim",
        )
        await output_cb(f"Prompt: {c.system_prompt_file or '(内置)'}", "dim")
        await output_cb(f"Skills: {', '.join(chat.agent.skills)}", "dim")
        await output_cb(f"Session: {chat.agent._current_session_id}", "dim")

    elif cmd == "/save-msg":
        ma = chat.agent.active_micro_agent
        if not ma or not ma.messages:
            await output_cb("(无会话历史)", "dim")
        else:
            import json as _json
            out = Path("messages.json")
            out.write_text(_json.dumps(ma.messages, ensure_ascii=False, indent=2), encoding="utf-8")
            await output_cb(f"已保存 {len(ma.messages)} 条消息到 {out.resolve()}", "green")

    elif cmd == "/prompt":
        ma = chat.agent._create_micro_agent()
        full_prompt = ma._build_system_prompt()
        await output_cb("─── System Prompt ───", "bold")
        await output_cb(full_prompt, "")
        await output_cb("─── End ───", "bold")

    elif cmd == "/clear":
        chat.new_session()
        await output_cb("对话已清空（新 session）", "green")

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
            self._agent_task = None

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

            # 启动 agent 后台运行
            self._agent_task = asyncio.create_task(self._chat.agent.run())

            await output_cb("CLI Agent 已启动", "bold green")
            await output_cb(f"   模型: {config.llm_model}", "dim")
            await output_cb(f"   Skills: {', '.join(self._chat.agent.skills)}", "dim")
            await output_cb("   输入消息开始对话，/help 查看命令\n", "dim")

            if not config.llm_api_key:
                await output_cb("未设置 API Key，请先: /api-key sk-xxx", "yellow")

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

            # 普通消息：非阻塞投入 input_queue
            await self._chat.send(text)

        async def action_quit(self):
            if self._agent_task:
                self._agent_task.cancel()
            self.exit()

    app = CLIAgentApp()
    app.run()


# ── 简单模式（无 Textual）────────────────────────────────────

async def run_simple(config: CLIConfig):
    """简单交互模式（fallback）。"""

    async def output_cb(text, style=""):
        print(text)

    chat = AgentChat(config, output_cb)
    loop = asyncio.get_event_loop()

    # 启动 agent 后台运行
    agent_task = asyncio.create_task(chat.agent.run())

    print("CLI Agent 已启动 (简单模式)")
    print(f"   模型: {config.llm_model}")
    print(f"   Skills: {', '.join(chat.agent.skills)}")
    print(f"   /help 查看命令，Ctrl+C 退出\n")

    if not config.llm_api_key:
        print("未设置 API Key，请先: /api-key sk-xxx\n")

    try:
        while True:
            # 非阻塞输入：input 在 executor 线程中运行
            # agent 的 _main_loop 在后台异步处理 input_queue
            try:
                text = await loop.run_in_executor(None, input, "> ")
            except (KeyboardInterrupt, EOFError):
                break

            text = text.strip()
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
        agent_task.cancel()
        try:
            await agent_task
        except (asyncio.CancelledError, Exception):
            pass
        print("\n再见！")


# ── 入口 ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AgentMatrix CLI Agent")
    parser.add_argument("-m", "--model", help="LLM (e.g. openai:gpt-4o)")
    parser.add_argument("--url", help="API endpoint URL")
    parser.add_argument("--api-key", help="API key")
    parser.add_argument("--system-prompt", help="System prompt file")
    parser.add_argument("--skills", help="MD skill directory")
    parser.add_argument("--skill-dir", action="append", default=[],
                        help="Python skill 目录（可多次指定）")
    parser.add_argument("--simple", action="store_true", help="Simple mode (no TUI)")
    args = parser.parse_args()

    config = load_config()

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
    if args.skill_dir:
        config.skill_dirs = args.skill_dir

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
