"""AI 服务统一错误码与异常类型（与后端 ResultCode 30xxx 段对齐）。

- 30001 调用超时
- 30002 AI 服务不可用（连接失败 / 模型服务未启动）
- 30003 模型错误（模型未拉取/不存在、鉴权失败、返回格式异常等）

对外响应体统一为 {"code": ..., "message": ...}，供后端 ai-gateway 精确映射
（同步接口走全局异常处理器；SSE 流式接口由事件生成器转为 error 事件）。
"""


class AiServiceError(Exception):
    """AI 服务业务异常基类。"""

    code = 50000
    http_status = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LLMTimeoutError(AiServiceError):
    """模型调用超时（30001，HTTP 504）。"""

    code = 30001
    http_status = 504


class LLMUnavailableError(AiServiceError):
    """模型服务不可用：连接失败 / 服务未启动（30002，HTTP 502）。"""

    code = 30002
    http_status = 502


class LLMModelError(AiServiceError):
    """模型错误：模型不存在/未拉取、鉴权失败、返回格式异常（30003，HTTP 502）。"""

    code = 30003
    http_status = 502
