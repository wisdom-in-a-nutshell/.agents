"""Shared CLI error types."""

from __future__ import annotations

import argparse
from typing import Any


class ParserExit(Exception):
    """Raised when argparse wants to exit after rendering help."""

    def __init__(self, *, exit_code: int, output: str) -> None:
        super().__init__(output)
        self.exit_code = exit_code
        self.output = output


class CliError(Exception):
    """Structured command failure."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        exit_code: int,
        retryable: bool,
        hint: str,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.retryable = retryable
        self.hint = hint
        self.detail = detail


class CliArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises structured validation errors."""

    def exit(self, status: int = 0, message: str | None = None) -> None:
        raise ParserExit(exit_code=status, output=message or "")

    def error(self, message: str) -> None:  # noqa: A003
        raise CliError(
            code="E_VALIDATION",
            message=message,
            exit_code=2,
            retryable=False,
            hint="Review the required flags or run --help for command examples.",
        )
