"""Dobby Shelf v2 package."""
from __future__ import annotations

from .cli import add_subparsers
from .model import ShelfValidationError
from .store import ShelfStoreError


class ShelfError(RuntimeError):
    def __init__(self, command: str, code: str, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.command = command
        self.code = code
        self.hint = hint


__all__ = ["add_subparsers", "ShelfError", "ShelfValidationError", "ShelfStoreError"]
