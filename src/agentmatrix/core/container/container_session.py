"""
Container Session - 持久容器内 Shell 会话

维护一个常驻的 shell 进程，保持工作目录和环境变量状态。
"""

import os
import platform
import shutil
import subprocess
import threading
import time
import uuid
import logging
from typing import Optional, Tuple, Callable
from queue import Queue, Empty


class ContainerSession:
    """
    持久的容器内 Shell 会话

    通过 `podman exec -i --user <user>` 维护一个常驻的 bash 进程，实现：
    - 工作目录保持（cd 命令生效后持续）
    - 环境变量保持（export 生效后持续）
    - 类似终端的交互体验

    命令边界通过唯一分隔符标记，使用 $? 捕获退出码。
    """

    def __init__(
        self,
        container_name: str,
        runtime_type: str = "podman",
        initial_workdir: str = "/work_files",
        logger: Optional[logging.Logger] = None,
        username: Optional[str] = None,
    ):
        self.container_name = container_name
        self.runtime_type = runtime_type
        self.initial_workdir = initial_workdir
        self.logger = logger or logging.getLogger("container_session")
        self.username = username

        # 进程状态
        self.process: Optional[subprocess.Popen] = None
        self.is_active = False
        self.session_id = uuid.uuid4().hex[:8]

        # 输出读取
        self._output_queue: Queue = Queue()
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_queue: Queue = Queue()
        self._stderr_reader_thread: Optional[threading.Thread] = None

        # 分隔符（唯一标识）
        self._start_marker = f"__SESSION_{self.session_id}_START__"
        self._end_marker = f"__SESSION_{self.session_id}_END__"

        # Output mirror callback（Collab Mode 使用）
        # callback(stream_type: str, line_text: str) -> None
        # stream_type: "stdout" or "stderr"
        # 注意：callback 在 reader 线程中同步调用，不能直接调 asyncio 代码
        self._output_callback: Optional[Callable[[str, str], None]] = None

    def set_output_callback(self, callback: Optional[Callable[[str, str], None]]) -> None:
        """设置 output mirror callback（None 表示取消）"""
        self._output_callback = callback

    @staticmethod
    def _find_runtime_cmd(runtime_type: str) -> str:
        """查找容器运行时 CLI 的绝对路径。

        打包后的 app 中 PATH 不完整，直接用 "podman"/"docker" 可能找不到。
        先用 shutil.which 查，再检查常见安装路径。
        """
        name = "podman" if runtime_type == "podman" else "docker"

        # 1. shutil.which (尊重 PATH)
        path = shutil.which(name)
        if path:
            return path

        # 2. 常见安装路径 fallback
        platform_name = platform.system()
        if platform_name == "Darwin":
            candidates = [
                f"/opt/homebrew/bin/{name}",
                f"/usr/local/bin/{name}",
                f"/opt/podman/bin/{name}",
            ]
        elif platform_name == "Linux":
            candidates = [
                f"/usr/bin/{name}",
                f"/usr/local/bin/{name}",
                f"/snap/bin/{name}",
            ]
        else:  # Windows or others
            candidates = []

        for candidate in candidates:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate

        # 3. 全部失败，返回原名让 Popen 报错
        return name

    def start(self) -> None:
        """
        启动持久 shell 会话

        执行: podman exec -i --user username container_name bash
        """
        if self.is_active:
            self.logger.warning(f"Session {self.session_id} 已经在运行")
            return

        if not self.username:
            raise ValueError("ContainerSession.start() 需要 username")

        runtime_cmd = self._find_runtime_cmd(self.runtime_type)

        cmd = [
            runtime_cmd,
            "exec",
            "-i",
            "--user", self.username,
            self.container_name,
            "bash",
        ]

        self.logger.info(f"启动持久会话: {' '.join(cmd)}")

        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,  # 使用 bytes 以便精确控制
            bufsize=0,  # 无缓冲
        )

        self.is_active = True

        # 启动输出读取线程
        self._reader_thread = threading.Thread(
            target=self._read_stdout,
            daemon=True,
            name=f"session-{self.session_id}-stdout",
        )
        self._stderr_reader_thread = threading.Thread(
            target=self._read_stderr,
            daemon=True,
            name=f"session-{self.session_id}-stderr",
        )
        self._reader_thread.start()
        self._stderr_reader_thread.start()

        # 进入工作目录
        workdir = self.initial_workdir
        if not workdir and self.username:
            workdir = f"/home/{self.username}"
        if workdir:
            self._send_raw(f"cd {workdir}\n")

        self.logger.info(f"会话 {self.session_id} 已启动")

    def stop(self) -> None:
        """停止会话"""
        if not self.is_active:
            return

        self.is_active = False

        if self.process:
            try:
                # 发送 exit 命令
                self._send_raw("exit\n")
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
                self.process.wait()
            self.process = None

        self.logger.info(f"会话 {self.session_id} 已停止")

    def health_check(self, timeout: float = 5) -> bool:
        """检查 shell 是否能响应命令"""
        if not self.is_active or not self.is_alive():
            return False
        try:
            exit_code, stdout, _ = self.execute("echo __HEALTH_OK__", timeout=timeout)
            return exit_code == 0 and "__HEALTH_OK__" in stdout
        except Exception:
            return False

    def ensure_responsive(self):
        """确保 shell 可响应，不可响应则重启"""
        if not self.health_check():
            self.logger.warning(f"Shell 无响应，重启: {self.session_id}")
            self.restart()

    def execute(self, command: str, timeout: float = 3600) -> Tuple[int, str, str]:
        """
        执行命令并等待结果

        Args:
            command: 要执行的 shell 命令
            timeout: 超时时间（秒）

        Returns:
            (exit_code, stdout, stderr)

        实现原理：
        1. 发送: echo 'MARKER_START'; command; echo "MARKER_END:$?"
        2. 读取直到看到 MARKER_END
        3. 解析退出码
        """
        if not self.is_active or not self.process:
            raise RuntimeError("会话未启动")

        # 清空队列中的残留数据
        self._drain_queues()

        # 构造命令 - 先 cd 到当前工作目录确保位置正确
        # 使用唯一标记来捕获输出和退出码
        wrapped_cmd = (
            f"echo '{self._start_marker}'\n{command}\necho '{self._end_marker}:'$?\n"
        )

        self.logger.info(f"[session {self.session_id}] 执行:\n{command}")

        # Mirror 输入到 output callback（Collab Mode 使用）
        if self._output_callback:
            self._output_callback("stdin", f"$ {command}\n")

        # 发送命令
        self._send_raw(wrapped_cmd)

        # 读取结果直到看到结束标记
        stdout_lines = []
        stderr_lines = []
        exit_code = -1
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                self.logger.warning(f"命令超时 ({timeout}s): {command[:50]}，重启 shell 清除状态")
                self.restart()
                return -1, "\n".join(stdout_lines), "\n".join(stderr_lines) + "\n[超时]"

            try:
                line = self._output_queue.get(timeout=0.1)
                line_str = line.decode("utf-8", errors="replace").strip()

                # 跳过开始标记
                if line_str == self._start_marker:
                    continue

                # 检查结束标记（处理 base64 等无换行输出与 marker 拼接的情况）
                if self._end_marker in line_str:
                    marker_idx = line_str.find(self._end_marker)
                    if marker_idx > 0:
                        # marker 之前的部分是合法 stdout
                        stdout_lines.append(line_str[:marker_idx].rstrip("\n"))
                    # 解析退出码: __SESSION_xxx_END__:0
                    marker_and_rest = line_str[marker_idx:]
                    parts = marker_and_rest.split(":")
                    if len(parts) >= 2:
                        try:
                            exit_code = int(parts[-1])
                        except ValueError:
                            pass
                    break

                stdout_lines.append(line_str)
            except Empty:
                # 进程已死但 reader 线程已退出，队列不会再有数据，继续等也是空转
                if not self.is_alive():
                    self.logger.warning(f"容器 shell 进程已终止: {command[:50]}")
                    return -1, "\n".join(stdout_lines), "\n".join(stderr_lines) + "\n[进程已终止]"
                continue

        # 收集 stderr（非阻塞）
        while True:
            try:
                line = self._stderr_queue.get(timeout=0.05)
                line_str = line.decode("utf-8", errors="replace").strip()
                if line_str and not line_str.startswith(self._start_marker):
                    stderr_lines.append(line_str)
            except Empty:
                break

        stdout = "\n".join(stdout_lines)
        stderr = "\n".join(stderr_lines)

        self.logger.debug(f"[session {self.session_id}] 完成, exit={exit_code}")
        return exit_code, stdout, stderr

    def get_workdir(self) -> str:
        """获取当前工作目录"""
        code, out, _ = self.execute("pwd")
        if code == 0:
            return out.strip()
        return self.initial_workdir

    def _send_raw(self, data: str) -> None:
        """发送原始数据到 stdin"""
        if self.process and self.process.stdin:
            self.process.stdin.write(data.encode("utf-8"))
            self.process.stdin.flush()

    def _read_stdout(self) -> None:
        """后台线程：读取 stdout（块读取 + 自行分行，避免 readline 在无换行时阻塞）"""
        buf = b""
        while self.is_active and self.process and self.process.stdout:
            try:
                chunk = self.process.stdout.read(4096)
                if not chunk:
                    # 管道关闭，输出残留数据
                    if buf:
                        self._output_queue.put(buf)
                        if self._output_callback:
                            try:
                                self._output_callback("stdout", buf.decode("utf-8", errors="replace"))
                            except Exception:
                                pass
                    break
                buf += chunk
                # 按换行分割，将完整行放入队列
                while True:
                    idx = buf.find(b"\n")
                    if idx == -1:
                        break
                    line = buf[:idx]
                    buf = buf[idx + 1 :]
                    self._output_queue.put(line)
                    if self._output_callback:
                        try:
                            line_text = line.decode("utf-8", errors="replace")
                            # 过滤 marker 行，不 mirror 给用户
                            if self._start_marker not in line_text and self._end_marker not in line_text:
                                self._output_callback("stdout", line_text)
                        except Exception:
                            pass
            except Exception:
                if buf:
                    self._output_queue.put(buf)
                break

    def _read_stderr(self) -> None:
        """后台线程：读取 stderr（块读取 + 自行分行，避免 readline 在无换行时阻塞）"""
        buf = b""
        while self.is_active and self.process and self.process.stderr:
            try:
                chunk = self.process.stderr.read(4096)
                if not chunk:
                    if buf:
                        self._stderr_queue.put(buf)
                        if self._output_callback:
                            try:
                                self._output_callback("stderr", buf.decode("utf-8", errors="replace"))
                            except Exception:
                                pass
                    break
                buf += chunk
                while True:
                    idx = buf.find(b"\n")
                    if idx == -1:
                        break
                    line = buf[:idx]
                    buf = buf[idx + 1 :]
                    self._stderr_queue.put(line)
                    if self._output_callback:
                        try:
                            line_text = line.decode("utf-8", errors="replace")
                            if self._start_marker not in line_text and self._end_marker not in line_text:
                                self._output_callback("stderr", line_text)
                        except Exception:
                            pass
            except Exception:
                if buf:
                    self._stderr_queue.put(buf)
                break

    def _drain_queues(self) -> None:
        """清空队列"""
        for q in [self._output_queue, self._stderr_queue]:
            while True:
                try:
                    q.get_nowait()
                except Empty:
                    break

    def is_alive(self) -> bool:
        """检查会话是否存活"""
        if not self.is_active or not self.process:
            return False
        return self.process.poll() is None

    def restart(self) -> None:
        """重启会话"""
        self.logger.info(f"重启会话 {self.session_id}")
        self.stop()
        self.start()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
