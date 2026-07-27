"""Adapter registry.

Add an agent by dropping a module here that exports an Adapter subclass and
listing it in ADAPTERS.
"""
from .base import Adapter, Capture, Counter, Section, Tool

ADAPTERS = {}


def _register():
    from .claude import ClaudeAdapter
    from .codex import CodexAdapter
    for cls in (ClaudeAdapter, CodexAdapter):
        ADAPTERS[cls.name] = cls


_register()

DEFAULT = "claude"


def names():
    return sorted(ADAPTERS)


def get(name=DEFAULT) -> Adapter:
    try:
        return ADAPTERS[name]()
    except KeyError:
        raise SystemExit(f"unknown agent {name!r}; known: {', '.join(names())}")
