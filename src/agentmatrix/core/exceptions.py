"""
AgentMatrix 自定义异常类

定义了系统中使用的各种异常类型，特别是 LLM 服务相关的异常。
"""


class LLMServiceUnavailableError(Exception):
    """LLM 服务不可用异常（基类）

    当 LLM 服务因任何原因无法访问时抛出此异常。
    包括网络故障、API 错误、超时等情况。
    """
    pass


class LLMServiceTimeoutError(LLMServiceUnavailableError):
    """LLM 服务超时异常

    当 LLM 请求超时时抛出。
    """
    pass


class LLMServiceConnectionError(LLMServiceUnavailableError):
    """LLM 服务连接异常

    当无法建立到 LLM 服务的网络连接时抛出。
    例如：DNS 解析失败、连接被拒绝等。
    """
    pass


class LLMServiceAPIError(LLMServiceUnavailableError):
    """LLM 服务 API 错误

    当 LLM API 返回错误状态码时抛出。
    例如：502, 503, 504 等服务不可用错误。
    """

    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


# ==================== Docker 相关异常 ====================


class DockerConnectionError(Exception):
    """Docker 连接失败

    当 Docker 守护进程未运行或无法连接时抛出。
    """
    pass


class ContainerNotFoundError(Exception):
    """容器不存在

    当尝试访问不存在的容器时抛出。
    """
    pass


class ContainerExecutionError(Exception):
    """容器内执行失败

    当在容器内执行命令失败时抛出。
    """
    pass


class WorkspaceSwitchError(Exception):
    """工作区切换失败

    当切换工作区符号链接失败时抛出。
    """
    pass


# ==================== 容器运行时通用异常 ====================


class ContainerRuntimeError(Exception):
    """容器运行时基类异常

    所有容器运行时相关异常的基类。
    """
    pass


class ContainerRuntimeNotAvailableError(ContainerRuntimeError):
    """运行时不可用

    当容器运行时（Docker/Podman）未安装或无法启动时抛出。
    """
    pass


class ContainerRuntimeConnectionError(ContainerRuntimeError):
    """运行时连接失败

    当无法连接到容器运行时守护进程时抛出。
    """
    pass


class ContainerRuntimeNotFoundError(ContainerRuntimeError):
    """找不到可用的运行时

    当自动检测无法找到任何可用的容器运行时时抛出。
    """
    pass
