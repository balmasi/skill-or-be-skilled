#!/usr/bin/env python3
"""Discover and normalize local agent session records."""

import argparse
from collections import Counter
from datetime import datetime, time, timezone
import json
from pathlib import Path
import tempfile
from typing import Any


def read_jsonl(path: Path):
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error


def event(timestamp: str | None, kind: str, **fields: Any) -> dict[str, Any]:
    result = {"timestamp": timestamp, "kind": kind}
    result.update({key: value for key, value in fields.items() if value is not None})
    return result


def normalize_claude(path: Path) -> dict[str, Any]:
    session_id = path.stem
    project = None
    events = []

    for record in read_jsonl(path):
        record_type = record.get("type")
        timestamp = record.get("timestamp")
        session_id = record.get("sessionId") or session_id
        project = record.get("cwd") or project

        if record_type == "user":
            if record.get("isMeta"):
                continue
            content = record.get("message", {}).get("content")
            if isinstance(content, str):
                events.append(event(timestamp, "user_message", text=content))
                continue
            if isinstance(content, list):
                text = text_blocks(content)
                if text:
                    events.append(event(timestamp, "user_message", text=text))
                for block in content:
                    if block.get("type") != "tool_result":
                        continue
                    events.append(
                        event(
                            timestamp,
                            "tool_error" if block.get("is_error") else "tool_result",
                            call_id=block.get("tool_use_id"),
                            text=stringify(block.get("content")),
                        )
                    )

        if record_type == "assistant":
            content = record.get("message", {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") == "text" and block.get("text"):
                    events.append(event(timestamp, "assistant_message", text=block["text"]))
                elif block.get("type") == "tool_use":
                    events.append(
                        event(
                            timestamp,
                            "tool_call",
                            tool=block.get("name"),
                            call_id=block.get("id"),
                            input=block.get("input"),
                        )
                    )

    timestamps = [item["timestamp"] for item in events if item.get("timestamp")]
    return {
        "provider": "claude",
        "id": session_id,
        "project": project,
        "started_at": min(timestamps) if timestamps else None,
        "ended_at": max(timestamps) if timestamps else None,
        "source": str(path),
        "events": events,
    }


def text_blocks(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if block.get("type") in {"input_text", "output_text", "text"} and text:
            parts.append(text)
    return "\n".join(parts)


def is_platform_context(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith(
        (
            "<environment_context>",
            "<permissions instructions>",
            "<app-context>",
            "<collaboration_mode>",
            "<skill>",
        )
    )


def parse_json_or_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def normalize_codex(path: Path) -> dict[str, Any]:
    session_id = path.stem
    project = None
    events = []
    usage = None

    for record in read_jsonl(path):
        timestamp = record.get("timestamp")
        record_type = record.get("type")
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue

        if record_type == "session_meta":
            session_id = payload.get("id") or session_id
            project = payload.get("cwd") or project
            continue

        if record_type == "response_item":
            payload_type = payload.get("type")
            if payload_type == "message":
                text = text_blocks(payload.get("content"))
                if (
                    text
                    and payload.get("role") in {"user", "assistant"}
                    and not (
                        payload.get("role") == "user" and is_platform_context(text)
                    )
                ):
                    events.append(
                        event(timestamp, f"{payload['role']}_message", text=text)
                    )
            elif payload_type in {"function_call", "custom_tool_call"}:
                events.append(
                    event(
                        timestamp,
                        "tool_call",
                        tool=payload.get("name"),
                        call_id=payload.get("call_id"),
                        input=parse_json_or_text(
                            payload.get("arguments", payload.get("input"))
                        ),
                    )
                )
            elif payload_type in {"function_call_output", "custom_tool_call_output"}:
                output = payload.get("output")
                events.append(
                    event(
                        timestamp,
                        "tool_error" if is_error_output(output) else "tool_result",
                        call_id=payload.get("call_id"),
                        text=stringify(output),
                    )
                )
            continue

        if record_type == "event_msg" and payload.get("type") == "token_count":
            info = payload.get("info")
            if isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict):
                usage = info["total_token_usage"]

    timestamps = [item["timestamp"] for item in events if item.get("timestamp")]
    result = {
        "provider": "codex",
        "id": session_id,
        "project": project,
        "started_at": min(timestamps) if timestamps else None,
        "ended_at": max(timestamps) if timestamps else None,
        "source": str(path),
        "events": events,
    }
    if usage:
        result["usage"] = usage
    return result


def is_error_output(value: Any) -> bool:
    text = stringify(value).lower()
    return "process exited with code 0" not in text and (
        "process exited with code " in text
        or text.startswith("error:")
        or '"is_error":true' in text.replace(" ", "")
    )


def stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def normalize_command(args: argparse.Namespace) -> int:
    normalizer = {"claude": normalize_claude, "codex": normalize_codex}[args.provider]
    document = {
        "schema_version": 1,
        "sessions": [normalizer(Path(filename)) for filename in args.files],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    return 0


def parse_boundary(value: str, end_of_day: bool = False) -> datetime:
    if "T" not in value:
        date = datetime.fromisoformat(value).date()
        return datetime.combine(
            date,
            time.max if end_of_day else time.min,
            tzinfo=timezone.utc,
        )
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def discover_files(provider: str, claude_home: Path, codex_home: Path):
    if provider in {"all", "claude"}:
        for path in claude_home.glob("projects/*/*.jsonl"):
            yield "claude", path
    if provider in {"all", "codex"}:
        for path in codex_home.glob("sessions/**/*.jsonl"):
            yield "codex", path
        for path in codex_home.glob("archived_sessions/*.jsonl"):
            yield "codex", path


def compact_text(value: str, limit: int = 500) -> str:
    collapsed = " ".join(value.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def summarize_session(session: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(item["kind"] for item in session["events"])
    tool_counts = Counter(
        item.get("tool", "unknown")
        for item in session["events"]
        if item["kind"] == "tool_call"
    )
    result = {
        key: session.get(key)
        for key in (
            "provider",
            "id",
            "project",
            "started_at",
            "ended_at",
            "source",
        )
    }
    result["metrics"] = {
        "user_messages": counts["user_message"],
        "assistant_messages": counts["assistant_message"],
        "tool_calls": counts["tool_call"],
        "tool_errors": counts["tool_error"],
        "tool_counts": dict(tool_counts.most_common()),
    }
    result["user_messages"] = [
        {
            "event_index": index,
            "timestamp": item.get("timestamp"),
            "text": compact_text(item.get("text", "")),
        }
        for index, item in enumerate(session["events"])
        if item["kind"] == "user_message" and item.get("text")
    ]
    result["tool_errors"] = [
        {
            "event_index": index,
            "timestamp": item.get("timestamp"),
            "text": compact_text(item.get("text", "")),
        }
        for index, item in enumerate(session["events"])
        if item["kind"] == "tool_error"
    ]
    if session.get("usage"):
        result["usage"] = session["usage"]
    return result


def collect_command(args: argparse.Namespace) -> int:
    since = parse_boundary(args.since)
    until = parse_boundary(args.until, end_of_day=True)
    if since > until:
        raise SystemExit("--since must be before or equal to --until")

    normalizers = {"claude": normalize_claude, "codex": normalize_codex}
    sessions = []
    for provider, path in discover_files(
        args.provider,
        Path(args.claude_home).expanduser(),
        Path(args.codex_home).expanduser(),
    ):
        session = normalizers[provider](path)
        started_at = parse_timestamp(session.get("started_at"))
        ended_at = parse_timestamp(session.get("ended_at"))
        if started_at is None and ended_at is None:
            continue
        session_start = started_at if started_at is not None else ended_at
        session_end = ended_at if ended_at is not None else started_at
        if session_start is None or session_end is None:
            continue
        if session_end < since or session_start > until:
            continue
        if args.project and session.get("project") not in args.project:
            continue
        sessions.append(session)

    sessions.sort(key=lambda session: session.get("started_at") or "")
    document = {
        "schema_version": 1,
        "period": {"since": args.since, "until": args.until},
        "projects": args.project or [],
        "sessions": sessions,
    }

    if args.output:
        output = Path(args.output).expanduser()
        if output.suffix.lower() != ".json":
            output = output / "normalized.json"
    else:
        output = Path(tempfile.mkdtemp(prefix="reflect-")) / "normalized.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")

    compact_sessions = [summarize_session(session) for session in sessions]
    summary = {
        "schema_version": 1,
        "period": document["period"],
        "projects": document["projects"],
        "totals": {
            "sessions": len(sessions),
            "user_messages": sum(
                session["metrics"]["user_messages"] for session in compact_sessions
            ),
            "assistant_messages": sum(
                session["metrics"]["assistant_messages"] for session in compact_sessions
            ),
            "tool_calls": sum(
                session["metrics"]["tool_calls"] for session in compact_sessions
            ),
            "tool_errors": sum(
                session["metrics"]["tool_errors"] for session in compact_sessions
            ),
        },
        "sessions": compact_sessions,
    }
    summary_output = output.with_name("summary.json")
    summary_output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "summary": str(summary_output),
                "session_count": len(sessions),
            }
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    normalize = subparsers.add_parser("normalize")
    normalize.add_argument("--provider", choices=["claude", "codex"], required=True)
    normalize.add_argument("--output", required=True)
    normalize.add_argument("files", nargs="+")
    normalize.set_defaults(func=normalize_command)

    collect = subparsers.add_parser("collect")
    collect.add_argument("--since", required=True)
    collect.add_argument("--until", required=True)
    collect.add_argument("--project", action="append")
    collect.add_argument(
        "--provider",
        choices=["all", "claude", "codex"],
        default="all",
    )
    collect.add_argument("--claude-home", default="~/.claude")
    collect.add_argument("--codex-home", default="~/.codex")
    collect.add_argument("--output")
    collect.set_defaults(func=collect_command)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
