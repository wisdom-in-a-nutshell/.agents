"""Dobby CLI shared library.

Contains the stable CLI contract (contract.py) and per-group command modules.
All command handlers go through contract helpers for JSON envelope shaping,
error codes, and exit code mapping.
"""
