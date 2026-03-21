#!/usr/bin/env python3
"""
Tmux Auto-Confirm CLI Tool

功能：
- 启动一个新的 tmux 窗口
- 每隔一分钟读取窗口内容
- 如果内容无变化且检测到确认提示，自动发送回车
"""

import subprocess
import time
import sys
import re
import argparse
import signal
import os
import threading


class TmuxAutoConfirm:
    def __init__(self, session_name="auto_confirm"):
        self.session_name = session_name
        self.last_content = None
        self.check_interval = 60  # 60 seconds
        self.bottom_lines = 10  # 检查底部10行
        self.running = True
        self._stop_event = threading.Event()  # 用于阻塞等待退出信号
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理中断信号"""
        signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        print(f"\n\n⏹️  收到 {signal_name} 信号，正在停止...")
        self.running = False
        self._stop_event.set()  # 唤醒阻塞的等待
        
    def run_command(self, cmd):
        """执行shell命令并返回输出"""
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=10
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timeout", 1
        except Exception as e:
            return "", str(e), 1
    
    def check_tmux_installed(self):
        """检查tmux是否已安装"""
        stdout, stderr, rc = self.run_command("which tmux")
        if rc != 0:
            print("错误: 未安装 tmux。请先安装 tmux:")
            print("  macOS: brew install tmux")
            print("  Ubuntu/Debian: sudo apt install tmux")
            print("  CentOS/RHEL: sudo yum install tmux")
            return False
        return True
    
    def session_exists(self):
        """检查tmux会话是否已存在"""
        stdout, _, rc = self.run_command(f"tmux has-session -t {self.session_name} 2>/dev/null")
        return rc == 0
    
    def _apply_tmux_config(self):
        """应用tmux配置（支持滚动、复制等）"""
        # 启用鼠标支持（可以用鼠标滚轮滚动）
        self.run_command(f"tmux set-option -t {self.session_name} mouse on")
        # 设置历史缓冲区大小（默认2000，设为5000行）
        self.run_command(f"tmux set-option -t {self.session_name} history-limit 5000")
        # 鼠标拖动选中后自动复制到系统剪贴板（Mac使用pbcopy）
        self.run_command(f"tmux bind-key -T copy-mode-vi MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel 'pbcopy'")
        self.run_command(f"tmux bind-key -T copy-mode MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel 'pbcopy'")
    
    def create_session(self, command=None):
        """创建新的tmux会话"""
        if command:
            # 在tmux中运行指定命令
            cmd = f"tmux new-session -d -s {self.session_name} '{command}'"
        else:
            # 创建空会话
            cmd = f"tmux new-session -d -s {self.session_name}"
        
        stdout, stderr, rc = self.run_command(cmd)
        if rc != 0:
            print(f"创建tmux会话失败: {stderr}")
            return False
        
        # 应用tmux配置
        self._apply_tmux_config()
        
        print(f"✓ 已创建 tmux 会话: {self.session_name}")
        print(f"  - 鼠标滚动: 已启用")
        print(f"  - 历史缓冲区: 5000 行")
        print(f"  - 提示: 也可用 Ctrl+B [ 进入复制模式，用方向键/PgUp/PgDn 滚动")
        return True
    
    def attach_session(self):
        """附加到tmux会话（在独立终端窗口中）"""
        # 尝试在不同终端中打开
        # macOS: 使用 Terminal.app 或 iTerm
        # Linux: 使用 xterm, gnome-terminal, konsole 等
        
        attach_cmds = [
            # macOS Terminal
            f"""osascript -e 'tell app "Terminal" to do script "tmux attach -t {self.session_name}"'""",
            # iTerm2
            f"""osascript -e 'tell app "iTerm" to create window with default profile command "tmux attach -t {self.session_name}"'""",
            # Linux - gnome-terminal
            f"gnome-terminal -- tmux attach -t {self.session_name}",
            # Linux - konsole
            f"konsole -e tmux attach -t {self.session_name}",
            # Linux - xterm
            f"xterm -e tmux attach -t {self.session_name} &",
        ]
        
        for cmd in attach_cmds:
            stdout, stderr, rc = self.run_command(cmd)
            if rc == 0:
                return True
        
        # 如果都失败，提示用户手动附加
        print(f"\n⚠️  无法自动打开终端窗口")
        print(f"   请手动运行: tmux attach -t {self.session_name}")
        return False
    
    def capture_pane(self):
        """捕获tmux窗格内容"""
        cmd = f"tmux capture-pane -t {self.session_name} -p"
        stdout, stderr, rc = self.run_command(cmd)
        if rc != 0:
            return None
        return stdout
    
    def send_enter(self):
        """向tmux发送回车键"""
        cmd = f"tmux send-keys -t {self.session_name} Enter"
        _, stderr, rc = self.run_command(cmd)
        if rc == 0:
            print("  → 已发送回车键")
            return True
        else:
            print(f"  ✗ 发送回车失败: {stderr}")
            return False
    
    def check_confirmation_prompt(self, content):
        """
        检查内容是否包含确认提示：
        - 去掉所有空白行后，在非空行中查找
        - 有 "Do you want to" 开头的行
        - 在其下方不远处有 "❯ 1. Yes" 或类似的选项行
        """
        lines = content.split('\n')
        
        # 去掉所有空白行，得到非空行列表
        non_empty = [line.strip() for line in lines if line.strip()]
        
        for i, line in enumerate(non_empty):
            # 检查是否是 "Do you want to" 开头
            if line.startswith("Do you want to"):
                # 检查这行之后的非空行（最多检查后5行）
                for j in range(i + 1, min(i + 6, len(non_empty))):
                    next_line = non_empty[j]
                    
                    # 匹配 "❯ 1. Yes" 或类似的选项格式
                    # 支持多种变体: "❯ 1. Yes", "> 1. Yes", "1. Yes" 等
                    patterns = [
                        r'^[❯>➤]\s*1\.\s*Yes',
                        r'^1\.\s*Yes',
                        r'^\(\d+\)\s*Yes',
                    ]
                    
                    for pattern in patterns:
                        if re.match(pattern, next_line, re.IGNORECASE):
                            print(f"\n  检测到确认提示:")
                            print(f"    {line}")
                            print(f"    {next_line}")
                            return True
                    
                    # 如果遇到了另一个问题，停止搜索
                    if next_line.endswith('?') and not next_line.startswith('Do you want to'):
                        break
        
        return False
    
    def monitor(self):
        """主监控循环"""
        print(f"\n🔍 开始监控 tmux 会话 '{self.session_name}'")
        print(f"   检查间隔: {self.check_interval} 秒")
        print(f"   按 Ctrl+C 停止\n")
        
        try:
            while self.running:
                current_content = self.capture_pane()
                
                if current_content is None:
                    print("✗ 无法读取tmux内容，会话可能已结束")
                    break
                
                print(f"[{time.strftime('%H:%M:%S')}] 检查中...")
                
                # 检查确认提示（去掉空白行后判断）
                if self.check_confirmation_prompt(current_content):
                    self.send_enter()
                    # 发送后等待一下，让内容变化
                    self._stop_event.wait(2)  # 阻塞等待2秒，可被信号唤醒
                    continue
                
                # 阻塞等待检查间隔，可被信号立即唤醒
                self._stop_event.wait(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  监控已停止")
            self.running = False
    
    def cleanup(self):
        """清理tmux会话"""
        print(f"\n清理 tmux 会话 '{self.session_name}'...")
        self.run_command(f"tmux kill-session -t {self.session_name} 2>/dev/null")
        print("✓ 已清理")
    
    def start(self, command=None, attach=True):
        """启动完整流程"""
        # 检查tmux
        if not self.check_tmux_installed():
            return False
        
        # 如果会话已存在，询问是否复用
        if self.session_exists():
            print(f"tmux 会话 '{self.session_name}' 已存在")
            response = input("是否复用现有会话? (y/n): ").strip().lower()
            if response != 'y':
                print("请使用不同的会话名称，或手动关闭现有会话")
                return False
            # 复用时也应用配置（确保滚动和复制功能正常）
            self._apply_tmux_config()
        else:
            # 创建新会话
            if not self.create_session(command):
                return False
        
        # 在独立窗口中打开
        if attach:
            self.attach_session()
            # 等待一下让终端窗口启动
            time.sleep(2)
        
        # 开始监控
        try:
            self.monitor()
        finally:
            self.cleanup()
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Tmux 自动确认工具 - 监控终端窗口并自动响应确认提示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                          # 创建空的tmux会话并监控
  %(prog)s -c "npm init"            # 在tmux中运行npm init并监控
  %(prog)s -s mysession -c "yarn"   # 指定会话名并运行yarn
  %(prog)s --no-attach              # 只监控，不打开新窗口

注意: 需要安装 tmux
        """
    )
    
    parser.add_argument(
        '-s', '--session',
        default='auto_confirm',
        help='tmux 会话名称 (默认: auto_confirm)'
    )
    
    parser.add_argument(
        '-c', '--command',
        help='要在tmux中运行的命令'
    )
    
    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=60,
        help='检查间隔，单位秒 (默认: 60)'
    )
    

    
    parser.add_argument(
        '--no-attach',
        action='store_true',
        help='不自动打开终端窗口（手动附加）'
    )
    
    args = parser.parse_args()
    
    # 创建实例
    app = TmuxAutoConfirm(session_name=args.session)
    app.check_interval = args.interval
    
    # 启动
    success = app.start(
        command=args.command,
        attach=not args.no_attach
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
