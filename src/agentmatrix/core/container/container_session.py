"""
Container Session - 持久容器内 Shell 会话

维护一个常驻的 shell 进程，保持工作目录和环境变量状态。
"""

import subprocess
import threading
import time
import uuid
import logging
from typing import Optional, Tuple
from queue import Queue, Empty


class ContainerSession:
    """
    持久的容器内 Shell 会话

    通过维护一个常驻的 `sh` 进程，实现：
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

    def start(self) -> None:
        """
        启动持久 shell 会话

        执行: podman exec -i container_name sh
        """
        if self.is_active:
            self.logger.warning(f"Session {self.session_id} 已经在运行")
            return

        runtime_cmd = "podman" if self.runtime_type == "podman" else "docker"
        if self.username:
            cmd = [
                runtime_cmd,
                "exec",
                "-i",
                self.container_name,
                "su",
                "-",
                self.username,
            ]
        else:
            cmd = [runtime_cmd, "exec", "-i", self.container_name, "sh"]

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

        self.logger.debug(f"[session {self.session_id}] 执行: {command[:100]}")

        # 发送命令
        self._send_raw(wrapped_cmd)

        # 读取结果直到看到结束标记
        stdout_lines = []
        stderr_lines = []
        exit_code = -1
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                self.logger.warning(f"命令超时 ({timeout}s): {command[:50]}")
                return -1, "\n".join(stdout_lines), "\n".join(stderr_lines) + "\n[超时]"

            try:
                line = self._output_queue.get(timeout=0.1)
                line_str = line.decode("utf-8", errors="replace").strip()

                # 跳过开始标记
                if line_str == self._start_marker:
                    continue

                # 检查结束标记
                if line_str.startswith(self._end_marker):
                    # 解析退出码: __SESSION_xxx_END__:0
                    parts = line_str.split(":")
                    if len(parts) >= 2:
                        try:
                            exit_code = int(parts[-1])
                        except ValueError:
                            pass
                    break

                stdout_lines.append(line_str)
            except Empty:
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
        """后台线程：读取 stdout"""
        while self.is_active and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                self._output_queue.put(line)
            except Exception:
                break

    def _read_stderr(self) -> None:
        """后台线程：读取 stderr"""
        while self.is_active and self.process and self.process.stderr:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                self._stderr_queue.put(line)
            except Exception:
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
