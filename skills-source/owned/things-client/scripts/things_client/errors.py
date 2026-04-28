from __future__ import annotations


ERROR_EXIT_CODES = {
    "E_VALIDATION": 2,
    "E_NOT_FOUND": 1,
    "E_IO": 1,
    "E_RUNTIME": 1,
    "E_DEPENDENCY": 4,
    "E_AUTH": 3,
    "E_TIMEOUT": 5,
}


class ThingsError(RuntimeError):
    def __init__(self, code: str, message: str, *, hint: str = "", retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.retryable = retryable
