import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "productivity" / "reflect" / "scripts" / "sessions.py"
FIXTURES = ROOT / "tests" / "fixtures"


class ReflectSessionsCliTest(unittest.TestCase):
    def run_normalize(self, provider, fixture):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        output = Path(temp_dir.name) / "normalized.json"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "normalize",
                "--provider",
                provider,
                "--output",
                str(output),
                str(FIXTURES / fixture),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(output.read_text())

    def test_normalizes_a_claude_session_into_compact_events(self):
        document = self.run_normalize("claude", "claude-session.jsonl")
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(len(document["sessions"]), 1)

        session = document["sessions"][0]
        self.assertEqual(session["provider"], "claude")
        self.assertEqual(session["id"], "claude-session-1")
        self.assertEqual(session["project"], "/projects/demo")
        self.assertEqual(
            [event["kind"] for event in session["events"]],
            [
                "user_message",
                "assistant_message",
                "tool_call",
                "tool_result",
                "assistant_message",
            ],
        )
        self.assertNotIn("/clear", json.dumps(document))

    def test_normalizes_codex_without_double_counting_mirrored_events(self):
        document = self.run_normalize("codex", "codex-session.jsonl")
        session = document["sessions"][0]

        self.assertEqual(session["provider"], "codex")
        self.assertEqual(session["id"], "codex-session-1")
        self.assertEqual(session["project"], "/projects/demo")
        self.assertEqual(
            [event["kind"] for event in session["events"]],
            [
                "user_message",
                "assistant_message",
                "tool_call",
                "tool_result",
                "assistant_message",
            ],
        )
        self.assertEqual(session["usage"]["total_tokens"], 1320)
        self.assertEqual(
            sum(event["kind"] == "user_message" for event in session["events"]),
            1,
        )

    def test_collects_selected_projects_and_period_into_a_temporary_run(self):
        with tempfile.TemporaryDirectory() as home_dir:
            home = Path(home_dir)
            claude_project = home / "claude" / "projects" / "demo"
            codex_sessions = home / "codex" / "sessions" / "2026" / "06" / "11"
            claude_project.mkdir(parents=True)
            codex_sessions.mkdir(parents=True)
            shutil.copy(
                FIXTURES / "claude-session.jsonl",
                claude_project / "claude-session.jsonl",
            )
            shutil.copy(
                FIXTURES / "codex-session.jsonl",
                codex_sessions / "codex-session.jsonl",
            )

            other = (FIXTURES / "claude-session.jsonl").read_text().replace(
                "/projects/demo", "/projects/other"
            )
            (claude_project / "other-session.jsonl").write_text(other)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "collect",
                    "--since",
                    "2026-06-01",
                    "--until",
                    "2026-06-30",
                    "--project",
                    "/projects/demo",
                    "--claude-home",
                    str(home / "claude"),
                    "--codex-home",
                    str(home / "codex"),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            output = Path(summary["output"])
            summary_output = Path(summary["summary"])
            self.addCleanup(shutil.rmtree, output.parent, True)
            self.assertEqual(summary["session_count"], 2)
            self.assertTrue(output.is_file())
            self.assertTrue(summary_output.is_file())
            self.assertTrue(output.is_relative_to(Path(tempfile.gettempdir())))
            self.assertFalse(output.is_relative_to(ROOT))

            document = json.loads(output.read_text())
            self.assertEqual(
                {session["provider"] for session in document["sessions"]},
                {"claude", "codex"},
            )
            self.assertEqual(
                {session["project"] for session in document["sessions"]},
                {"/projects/demo"},
            )

            compact = json.loads(summary_output.read_text())
            self.assertEqual(len(compact["sessions"]), 2)
            self.assertEqual(
                compact["totals"],
                {
                    "sessions": 2,
                    "user_messages": 2,
                    "assistant_messages": 4,
                    "tool_calls": 2,
                    "tool_errors": 0,
                },
            )
            self.assertEqual(
                compact["sessions"][0]["user_messages"][0]["text"],
                "Add analytics to every page.",
            )


if __name__ == "__main__":
    unittest.main()
