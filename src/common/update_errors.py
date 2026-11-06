"""更新执行器与主程序共用的错误类型，不加载业务依赖。"""


class SelfUpdateError(Exception):
    """自更新流程中的可预期失败。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
