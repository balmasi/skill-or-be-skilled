import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "productivity" / "context-audit" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(SCRIPTS))

import adapters  # noqa: E402
from analyze import schema_costs  # noqa: E402


def load_capture():
    return json.loads((FIXTURES / "claude-capture.json").read_text())


class AdapterRegistryTest(unittest.TestCase):
    def test_default_is_claude(self):
        self.assertEqual(adapters.get().name, "claude")

    def test_unknown_agent_is_rejected(self):
        with self.assertRaises(SystemExit):
            adapters.get("nope")

    def test_every_registered_adapter_is_listed(self):
        for name in adapters.names():
            self.assertEqual(adapters.get(name).name, name)


class ClaudeParseTest(unittest.TestCase):
    def setUp(self):
        self.adapter = adapters.get("claude")
        self.capture = self.adapter.parse(load_capture())

    def test_tools_keep_provider_shape(self):
        self.assertEqual([t.name for t in self.capture.tools],
                         ["Bash", "Read", "DeferredToolPlaceholder"])
        # The schema is handed back to the counter verbatim, so it must survive
        # parsing unchanged.
        self.assertIn("input_schema", self.capture.tools[0].schema)

    def test_texts_exclude_blank_blocks(self):
        self.assertEqual(len(self.capture.texts), 3)
        self.assertTrue(self.capture.texts[-1].strip())

    def test_system_is_passed_through(self):
        self.assertEqual(self.capture.system, load_capture()["system"])


class ClaudeSectionsTest(unittest.TestCase):
    def setUp(self):
        self.adapter = adapters.get("claude")
        self.texts = self.adapter.parse(load_capture()).texts
        self.sections = {s.title: s for s in self.adapter.sections()}

    def block(self, title):
        section = self.sections[title]
        return section, next(t for t in self.texts if section.match(t))

    def test_hyphenated_mcp_server_names_are_not_dropped(self):
        # A \w-based regex silently loses every server with a - in its name,
        # which is most of them.
        section, text = self.block("deferred tool names by server")
        rows = dict((label, weight) for label, weight, _ in section.split(text))
        self.assertEqual(set(rows), {"kai-staging-airtable", "kai-prod-n8n-mcp",
                                     "plain", "(built-in)"})

    def test_server_rows_are_weighted_by_name_length_and_counted(self):
        section, text = self.block("deferred tool names by server")
        rows = {label: (weight, note) for label, weight, note in section.split(text)}
        self.assertEqual(rows["kai-staging-airtable"][1], "(2 tools)")
        self.assertEqual(rows["(built-in)"][1], "(2 tools)")
        # Two long names outweigh two short ones.
        self.assertGreater(rows["kai-staging-airtable"][0], rows["(built-in)"][0])

    def test_rows_are_ordered_by_weight(self):
        section, text = self.block("deferred tool names by server")
        weights = [w for _, w, _ in section.split(text)]
        self.assertEqual(weights, sorted(weights, reverse=True))

    def test_skills_are_split_per_skill(self):
        section, text = self.block("skills")
        rows = dict((label, weight) for label, weight, _ in section.split(text))
        self.assertEqual(set(rows), {"co-plan", "context-audit", "reflect"})
        self.assertGreater(rows["context-audit"], rows["reflect"])

    def test_sections_do_not_match_unrelated_blocks(self):
        for section in self.sections.values():
            self.assertFalse(section.match("say ok"))


class SchemaCostTest(unittest.TestCase):
    """The overhead solve, with no network in sight."""

    def test_fixed_overhead_is_recovered_from_solo_prices(self):
        # Three tools truly costing 100/200/300 with a 50-token per-request
        # tool-block overhead: each solo price carries the overhead once, the
        # combined request carries it once in total.
        solo = [("a", 150), ("b", 250), ("c", 350)]
        overhead, costs = schema_costs(
            solo, allt=650, base=0, leave_one_out=lambda name: 0)
        self.assertAlmostEqual(overhead, 50)
        self.assertAlmostEqual(costs["a"], 100)
        self.assertAlmostEqual(costs["b"], 200)
        self.assertAlmostEqual(costs["c"], 300)

    def test_unpriceable_tool_falls_back_to_leave_one_out(self):
        solo = [("a", 150), ("b", 250), ("pseudo", None)]
        asked = []

        def leave_one_out(name):
            asked.append(name)
            return 42

        overhead, costs = schema_costs(solo, allt=350, base=0,
                                       leave_one_out=leave_one_out)
        self.assertEqual(asked, ["pseudo"])
        # The fallback is a difference of two full requests, so it carries no
        # overhead and must not be corrected for one.
        self.assertEqual(costs["pseudo"], 42)
        self.assertAlmostEqual(overhead, 50)
        self.assertAlmostEqual(costs["a"], 100)

    def test_single_tool_has_no_solvable_overhead(self):
        overhead, costs = schema_costs([("a", 150)], allt=150, base=0,
                                       leave_one_out=lambda name: 0)
        self.assertEqual(overhead, 0)
        self.assertEqual(costs["a"], 150)


if __name__ == "__main__":
    unittest.main()
