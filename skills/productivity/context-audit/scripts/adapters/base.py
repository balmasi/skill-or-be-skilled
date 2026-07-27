#!/usr/bin/env python3
"""Adapter contract: everything that differs between coding agents.

An adapter answers three questions the generic pipeline cannot:

  drive   how do I launch this agent against a capture proxy, know when it is
          ready, and hand it one prompt?
  parse   the recorded request body is in some provider's wire format — what are
          its tools, its system text, and its message blocks?
  price   how many tokens is a given (tools, system, messages) triple?

capture.py, analyze.py and sweep.py contain no agent-specific logic; all of it
lives in an Adapter subclass. See reference/adding-an-adapter.md.
"""
from dataclasses import dataclass, field
import re
from typing import Callable, List, Optional, Sequence, Tuple


@dataclass
class Tool:
    """One tool as the provider serialises it."""
    name: str
    schema: dict            # the raw object, passed back to the counter verbatim


@dataclass
class Capture:
    """A recorded request, normalised."""
    tools: List[Tool]
    system: object          # provider-shaped; opaque to the pipeline
    messages: list          # provider-shaped; opaque to the pipeline
    texts: List[str] = field(default_factory=list)  # message text blocks, priced individually


@dataclass
class Section:
    """A named breakdown of one message block into weighted rows.

    e.g. the deferred-tool-name list split per MCP server. `match` picks the
    block out of Capture.texts; `split` turns it into (label, weight, note)
    rows whose weights apportion that block's measured token cost.
    """
    title: str
    match: Callable[[str], bool]
    split: Callable[[str], Sequence[Tuple[str, float, str]]]
    limit: Optional[int] = None      # show only the top N rows


def split_skill_rows(text: str):
    """Aggregate Agent Skills list entries by public skill name."""
    weights = {}
    for part in re.split(r'\n(?=- [\w:-]+: )', text):
        match = re.match(r'- ([\w:-]+):', part.strip())
        if match:
            weights[match.group(1)] = weights.get(match.group(1), 0) + len(part)
    return [(name, size, "")
            for name, size in sorted(weights.items(), key=lambda x: -x[1])]


class Counter:
    """Prices token counts. Subclasses may hit an API or tokenise locally."""

    def count(self, tools=None, system=None, messages=None) -> int:
        raise NotImplementedError

    def tool_price(self, tool: Tool, base: int) -> Optional[int]:
        """Solo cost of one tool including per-request tool-block overhead.
        Return None if the provider rejects the tool in isolation — the caller
        falls back to leave-one-out."""
        try:
            return self.count(tools=[tool.schema]) - base
        except Exception:
            return None

    def save(self):
        """Persist any cross-run cache. Optional."""

    # Reporting only.
    calls = 0
    cached = 0


class Adapter:
    name = "?"
    #: how the agent is invoked, for error messages
    binary = "?"

    # --- drive -----------------------------------------------------------
    def env(self, base_env: dict, port: int, tool_search: str) -> dict:
        """Environment for the agent process, pointed at the capture proxy."""
        raise NotImplementedError

    def command(self, logpath: str, tool_search: str, extra: List[str]) -> List[str]:
        """argv for the agent, configured to log enough to detect readiness."""
        raise NotImplementedError

    def send_prompt(self, proc, text: str) -> None:
        """Deliver one user turn. Only called once readiness is reported."""
        raise NotImplementedError

    def wait_ready(self, logpath: str, timeout: float):
        """Block until the agent has finished loading everything that will
        appear in the request. Return (ok, started, done) for reporting."""
        raise NotImplementedError

    def self_check(self, request: dict, log: str) -> Optional[str]:
        """Return an error string if the capture is demonstrably incomplete
        (e.g. it raced ahead of MCP registration). None means it looks sound."""
        return None

    def capture_headers(self, headers: dict) -> dict:
        """Headers to persist beside the request. Drop credentials when pricing
        does not need them."""
        return headers

    def disable_tools_args(self, names: Sequence[str]) -> List[str]:
        """CLI args that strip the given tools' schemas from the request."""
        raise NotImplementedError

    # --- parse -----------------------------------------------------------
    def parse(self, request: dict) -> Capture:
        raise NotImplementedError

    def sections(self) -> List[Section]:
        """Extra per-block breakdowns to report. May be empty."""
        return []

    # --- price -----------------------------------------------------------
    def counter(self, headers: dict, jobs: int = 16) -> Counter:
        raise NotImplementedError

    # --- apply -----------------------------------------------------------
    def deny_scopes(self, project_dir: str) -> List[Tuple[str, str, str]]:
        """(scope, path, when-to-use) rows for where a denial can be written."""
        return []

    def deny_patch(self, names: Sequence[str]) -> dict:
        """JSON to merge into a settings file to strip those tools."""
        raise NotImplementedError
