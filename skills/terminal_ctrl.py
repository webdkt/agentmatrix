# skills/terminal_ctrl.py
import libtmux
import os
import time
import platform
import subprocess

import time
import random
import logging
from core.action import register_action

logging.getLogger('libtmux').setLevel(logging.WARNING)
class TerminalSkillMixin:
    """
    赋予 Agent 操作 Tmux 终端的能力。
    支持：创建会话、输入命令、读取屏幕、弹出窗口。
    """
    
    def _get_server(self):
        # 获取或启动 tmux server
        return libtmux.Server()

    def _get_session(self, session_name="matrix_coder"):
        server = self._get_server()
        try:
            session = server.sessions.get(session_name=session_name)
        except Exception:
            session = None
            
        if not session:
            # 创建新会话，默认 shell
            session = server.new_session(session_name=session_name)
        return session

    def _get_pane(self, session_name="matrix_coder"):
        session = self._get_session(session_name)
        return session.windows[0].panes[0]

    @register_action("初始化并弹出一个可见的终端窗口。只需调用一次。", param_infos={
        "session_name": "会话名称，默认为 matrix_coder"
    })
    async def launch_terminal_window(self, session_name="matrix_coder"):
        """
        在宿主机操作系统层面弹出一个终端窗口，并 Attach 到指定的 tmux 会话。
        这样用户可以看到 Agent 的操作。
        """
        # 1. 确保 Session 存在
        self._get_session(session_name)

        # 转换为绝对路径
        workspace_root = os.path.abspath(self.workspace_root)
        
        system = platform.system()
        cmd = ""
        
        try:
            if system == "Darwin": # macOS
                # 使用 AppleScript 调用 Terminal.app 并执行 tmux attach
                # 这是一个比较 hacky 但有效的方法
                script = f'''
                tell application "Terminal"
                    do script "cd {workspace_root} && tmux attach -t {session_name}"
                    activate
                end tell
                '''
                subprocess.run(["osascript", "-e", script])
                return f"Success: MacOS Terminal launched attached to '{session_name}'."
            
            elif system == "Linux":
                # 尝试 gnome-terminal (Ubuntu/Debian)
                # 如果是其他发行版需要调整
                subprocess.Popen(["gnome-terminal", "--", "bash", "-c", f"cd {workspace_root} && exec tmux attach -t {session_name}"])
                return f"Success: Linux Terminal launched attached to '{session_name}'."
            
            else:
                return "Error: Unsupported OS for auto-launching window. Please manually run 'tmux attach -t matrix_coder'."
                
        except Exception as e:
            return f"Error launching window: {str(e)}"

    @register_action("向终端发送命令或文本（如启动 claude 或回答 y/n）。", param_infos={
        "command": "要输入的文本",
        "press_enter": "是否在末尾加回车，默认为 True"
    })
    async def send_terminal_command(self, command: str, press_enter: bool = True):
        pane = self._get_pane()
        for char in command:
            pane.send_keys(char, enter=False)
            # triangular(left, mode, right) - 延迟更可能接近 0.05
            time.sleep(random.triangular(0.05, 0.05, 0.5))
        
        if press_enter:
            pane.send_keys("Enter")
        
        # 给一点点时间让终端反应
        time.sleep(1) 
        return f"Command '{command}' sent."






    
    

  

    @register_action("查看终端屏幕的当前内容（截图）。", param_infos={
        "lines": "读取最近多少行，默认 20"
    })
    async def read_terminal_screen(self, lines: int = 20):
        pane = self._get_pane()
        # capture_pane 返回的是列表
        output_lines = pane.capture_pane()
        
        # 取最后 N 行
        recent_output = output_lines[-int(lines):]
        content = "\n".join(recent_output)
        
        return f"=== TERMINAL SCREEN ===\n{content}\n======================="