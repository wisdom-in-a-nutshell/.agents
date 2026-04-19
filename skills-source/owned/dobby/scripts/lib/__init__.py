"""Dobby CLI shared library.

Contains the stable CLI contract (contract.py) and per-group command modules
(memory.py, tasks.py). All command handlers go through contract helpers for
JSON envelope shaping, error codes, and exit code mapping.
"""
