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
