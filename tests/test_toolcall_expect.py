"""Check the tool-call tests' argument checks: each passes on a right call and fails on a wrong one."""

import datetime
import unittest

from toolcalls import expect
from toolcalls.expect import MISSING

PREFIX = "arii_mcp_"


def failures(value, **checks):
    return expect.check_argument("arg", value, checks)


def call(name, **arguments):
    return {"name": PREFIX + name, "arguments": arguments}


class ArgumentCheckTest(unittest.TestCase):
    def assertPasses(self, value, **checks):
        self.assertEqual(failures(value, **checks), [])

    def assertFails(self, value, check, **checks):
        found = failures(value, **checks)
        self.assertTrue(found, f"{check} should fail on {value!r}")
        self.assertIn(f"arg: {check} failed", found[0])

    def test_equals_is_exact(self):
        self.assertPasses(True, equals=True)
        self.assertPasses(5.0, equals=5)
        self.assertFails("true", "equals", equals=True)
        self.assertFails(1, "equals", equals=True)
        self.assertFails("Apple Health", "equals", equals="AppleHealth")
        self.assertFails(["a", "b"], "equals", equals=["b", "a"])
        self.assertFails(MISSING, "equals", equals=True)

    def test_equals_reads_a_toml_date_as_its_text(self):
        self.assertPasses("2026-01-01", equals=datetime.date(2026, 1, 1))
        self.assertFails("2026-01-02", "equals", equals=datetime.date(2026, 1, 1))

    def test_absent(self):
        self.assertPasses(MISSING, absent=True)
        self.assertFails(False, "absent", absent=True)

    def test_present(self):
        self.assertPasses(False, present=True)
        self.assertFails(MISSING, "present", present=True)

    def test_contains(self):
        self.assertPasses(["labresult", "vital"], contains="labresult")
        self.assertPasses("ab-cd", contains=["ab", "cd"])
        self.assertFails(["vital"], "contains", contains="labresult")
        self.assertFails(["a"], "contains", contains=["a", "b"])
        self.assertFails(5, "contains", contains="5")

    def test_not_contains(self):
        self.assertPasses(["vital"], not_contains="labresult")
        self.assertFails(["labresult"], "not_contains", not_contains=["labresult", "x"])
        self.assertFails("cursor=c1", "not_contains", not_contains="c1")

    def test_one_of(self):
        self.assertPasses("Week", one_of=["Week", "Month"])
        self.assertFails("None", "one_of", one_of=["Week", "Month"])
        self.assertFails(MISSING, "one_of", one_of=["Week"])

    def test_range_on_numbers_and_dates(self):
        self.assertPasses(180, range={"min": 179, "max": 181})
        self.assertPasses("2026-03-01", range={"min": datetime.date(2026, 3, 1), "max": "2026-03-31"})
        self.assertFails(200, "range", range={"max": 181})
        self.assertFails("2026-02-28", "range", range={"min": "2026-03-01"})
        self.assertFails("180", "range", range={"min": 0})
        self.assertFails(True, "range", range={"min": 0})

    def test_len(self):
        self.assertPasses(["a"] * 20, len={"max": 20})
        self.assertPasses(["a", "b"], len=2)
        self.assertFails(["a"] * 21, "len", len={"max": 20})
        self.assertFails([], "len", len={"min": 1})
        self.assertFails(3, "len", len=1)

    def test_matches_the_whole_text(self):
        self.assertPasses("2026-03-01", matches=r"\d{4}-\d{2}-\d{2}")
        self.assertFails("2026-03-01T00:00:00Z", "matches", matches=r"\d{4}-\d{2}-\d{2}")
        self.assertFails(20260301, "matches", matches=r"\d+")

    def test_same_as_call(self):
        self.assertEqual(expect.check_argument("arg", ["x"], {"same_as_call": 1}, ["x"]), [])
        self.assertEqual(expect.check_argument("arg", MISSING, {"same_as_call": 1}, MISSING), [])
        self.assertTrue(expect.check_argument("arg", ["y"], {"same_as_call": 1}, ["x"]))
        self.assertTrue(expect.check_argument("arg", MISSING, {"same_as_call": 1}, ["x"]))

    def test_an_unknown_check_is_refused(self):
        with self.assertRaises(ValueError):
            failures(True, equal=True)


class ExpectationTest(unittest.TestCase):
    def test_the_first_call_of_the_tool_by_default(self):
        calls = [call("get_marker_type"), call("get_marker_samples_compact", latestPerSource=True)]
        rule = {"tool": "get_marker_samples_compact", "args": {"latestPerSource": {"equals": True}}}
        self.assertEqual(expect.check_expectation(rule, calls, PREFIX), [])

    def test_a_missing_tool_names_the_calls_made(self):
        found = expect.check_expectation({"tool": "get_marker_samples_compact"}, [call("get_marker_type")], PREFIX)
        self.assertEqual(found, ["expected a call to arii_mcp_get_marker_samples_compact, got: arii_mcp_get_marker_type"])

    def test_a_missing_nth_call_fails(self):
        found = expect.check_expectation({"tool": "list_notes", "call": 2}, [call("list_notes")], PREFIX)
        self.assertIn("expected call 2", found[0])

    def test_each_checks_every_call(self):
        calls = [call("get_marker_samples_compact", specificMarkers=["a"] * 20),
                 call("get_marker_samples_compact", specificMarkers=["b"] * 21)]
        rule = {"tool": "get_marker_samples_compact", "call": "each", "args": {"specificMarkers": {"len": {"max": 20}}}}
        found = expect.check_expectation(rule, calls, PREFIX)
        self.assertEqual(len(found), 1)
        self.assertIn("call 2: specificMarkers: len failed", found[0])

    def test_all_joins_every_call(self):
        calls = [call("get_marker_samples_compact", specificMarkers=["a", "b"]),
                 call("get_marker_samples_compact", specificMarkers=["c"])]
        rule = {"tool": "get_marker_samples_compact", "call": "all",
                "args": {"specificMarkers": {"contains": ["a", "b", "c"], "len": 3}}}
        self.assertEqual(expect.check_expectation(rule, calls, PREFIX), [])
        rule["args"]["specificMarkers"]["contains"].append("d")
        self.assertTrue(expect.check_expectation(rule, calls, PREFIX))

    def test_same_as_call_on_the_expectation_covers_every_unchecked_argument(self):
        first = call("get_marker_samples_compact", specificMarkers=["a"], latestPerSource=True)
        rule = {"tool": "get_marker_samples_compact", "call": 2, "same_as_call": 1,
                "args": {"cursor": {"equals": "c1"}}}
        same = call("get_marker_samples_compact", specificMarkers=["a"], latestPerSource=True, cursor="c1")
        self.assertEqual(expect.check_expectation(rule, [first, same], PREFIX), [])
        changed = call("get_marker_samples_compact", specificMarkers=["a"], cursor="c1")
        found = expect.check_expectation(rule, [first, changed], PREFIX)
        self.assertEqual(found, ["arii_mcp_get_marker_samples_compact call 2: latestPerSource: same_as_call failed, "
                                 "expected True as in call 1, got (absent)"])
        extra = call("get_marker_samples_compact", specificMarkers=["a"], latestPerSource=True, cursor="c1", limit=5)
        self.assertTrue(expect.check_expectation(rule, [first, extra], PREFIX))

    def test_same_as_call_naming_a_call_that_was_not_made_fails(self):
        rule = {"tool": "list_notes", "args": {"search": {"same_as_call": 3}}}
        found = expect.check_expectation(rule, [call("list_notes", search="x")], PREFIX)
        self.assertIn("there is no call 3", found[0])


class RunCheckTest(unittest.TestCase):
    def test_never_tools(self):
        case = {"never_tools": ["get_marker_samples_compact"]}
        self.assertEqual(expect.check_run(case, [call("get_marker_type")], PREFIX, "answered"), [])
        found = expect.check_run(case, [call("get_marker_samples_compact")], PREFIX, "answered")
        self.assertIn("never allows it", found[0])

    def test_max_calls(self):
        case = {"max_calls": 1}
        self.assertEqual(expect.check_run(case, [call("a")], PREFIX, "answered"), [])
        self.assertIn("more than max_calls", expect.check_run(case, [call("a"), call("b")], PREFIX, "answered")[0])

    def test_max_turns(self):
        case = {"max_turns": 2}
        self.assertEqual(expect.check_run(case, [], PREFIX, "answered"), [])
        self.assertIn("after max_turns 2", expect.check_run(case, [], PREFIX, "max_turns")[0])


if __name__ == "__main__":
    unittest.main()
