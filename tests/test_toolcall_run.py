"""Check the tool-call tests' turn loop, case checks and system-message guard, with a fake model."""

import json
from pathlib import Path
import shutil
import threading
import unittest

from toolcalls import definitions, run

PREFIX = "arii_mcp_"
PATIENT = "11111111-2222-4333-8444-555555555555"
TOOLS = [
    {"name": PREFIX + "get_marker_samples_compact", "description": "Readings.",
     "inputSchema": {"type": "object", "properties": {"userId": {"type": "string"}, "cursor": {"type": "string"},
                                                       "specificMarkers": {"type": "array"}}}},
    {"name": PREFIX + "get_user_marker_types_with_data", "description": "Markers.",
     "inputSchema": {"type": "object", "properties": {"userId": {"type": "string"}, "tags": {"type": "array"}}}},
]


def case(**fields):
    base = {
        "id": "paging",
        "questions": [f"question {i}" for i in range(1, 6)],
        "context": {"patient_id": PATIENT, "today": "2026-03-14"},
        "expect": [{"tool": "get_marker_samples_compact"}],
    }
    base.update(fields)
    return base


def function_call(name, n, **arguments):
    return {"type": "function_call", "name": PREFIX + name, "arguments": json.dumps(arguments), "call_id": f"c{n}"}


class FakeModel:
    """Answers each turn from a script, the same for every wording, and keeps what it was sent."""

    def __init__(self, *turns):
        self.turns = turns
        self.sent = []
        self.lock = threading.Lock()

    def respond(self, items, functions):
        with self.lock:
            self.sent.append((list(items), functions))
        turn = sum(1 for item in items if item.get("type") == "function_call_output")
        output = self.turns[turn] if turn < len(self.turns) else [{"type": "message", "content": []}]
        return {"output": output, "usage": {"input_tokens": 100, "output_tokens": 10}}


PAGING = case(
    replies=[
        {"tool": "get_marker_samples_compact", "when": {"cursor": {"absent": True}}, "reply": {"nextCursor": "c1"}},
        {"tool": "get_marker_samples_compact", "when": {"cursor": {"equals": "c1"}}, "reply": {"nextCursor": None}},
    ],
    expect=[{"tool": "get_marker_samples_compact", "call": 2, "same_as_call": 1, "args": {"cursor": {"equals": "c1"}}}],
)


class TurnLoopTest(unittest.TestCase):
    def test_a_paging_case_passes_when_the_cursor_is_sent_back(self):
        model = FakeModel(
            [function_call("get_marker_samples_compact", 1, userId=PATIENT, specificMarkers=["m"])],
            [function_call("get_marker_samples_compact", 2, userId=PATIENT, specificMarkers=["m"], cursor="c1")],
        )
        result = run.run_case(PAGING, TOOLS, model, PREFIX)
        self.assertTrue(result["passed"], result["answers"][0]["failures"])
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["answers"]), 5)
        self.assertEqual(result["answers"][0]["stopped"], "answered")
        self.assertEqual(len(result["answers"][0]["usage"]), 3)

    def test_the_canned_reply_goes_back_with_its_call_id(self):
        model = FakeModel([function_call("get_marker_samples_compact", 1, specificMarkers=["m"])])
        run.ask(PAGING, "q", [], model, PREFIX)
        second_turn = model.sent[1][0]
        self.assertEqual(second_turn[-1], {"type": "function_call_output", "call_id": "c1",
                                           "output": json.dumps({"nextCursor": "c1"})})

    def test_a_paging_case_fails_when_the_filters_change(self):
        model = FakeModel(
            [function_call("get_marker_samples_compact", 1, specificMarkers=["m"])],
            [function_call("get_marker_samples_compact", 2, specificMarkers=["other"], cursor="c1")],
        )
        result = run.run_case(PAGING, TOOLS, model, PREFIX)
        self.assertFalse(result["passed"])
        self.assertIn("specificMarkers: same_as_call failed", result["answers"][0]["failures"][0])

    def test_a_call_without_a_canned_reply_stops_the_loop(self):
        model = FakeModel([function_call("get_user_marker_types_with_data", 1, tags=["labresult"])])
        answer = run.ask(case(expect=[{"tool": "get_user_marker_types_with_data"}]), "q", [], model, PREFIX)
        self.assertEqual(answer["stopped"], "no canned reply for arii_mcp_get_user_marker_types_with_data")
        self.assertTrue(answer["passed"])
        self.assertEqual(len(model.sent), 1)

    def test_a_reply_given_as_json_text_can_carry_null(self):
        model = FakeModel([function_call("get_marker_samples_compact", 1)])
        text = case(replies=[{"tool": "get_marker_samples_compact", "reply": '{"nextCursor": null}'}])
        run.ask(text, "q", [], model, PREFIX)
        self.assertEqual(model.sent[1][0][-1]["output"], '{"nextCursor": null}')

    def test_arguments_that_are_not_json_fail(self):
        broken = {"type": "function_call", "name": PREFIX + "get_marker_samples_compact", "arguments": "{", "call_id": "c1"}
        answer = run.ask(case(), "q", [], FakeModel([broken]), PREFIX)
        self.assertIn("arguments are not JSON", answer["failures"][0])

    def test_a_model_still_calling_at_max_turns_fails(self):
        model = FakeModel(*[[function_call("get_marker_samples_compact", 1, specificMarkers=["m"])]] * 3)
        endless = case(max_turns=1, replies=[{"tool": "get_marker_samples_compact", "reply": {"nextCursor": "c1"}}])
        answer = run.ask(endless, "q", [], model, PREFIX)
        self.assertIn("still calling tools after max_turns 1", answer["failures"])

    def test_one_failing_wording_fails_the_case(self):
        model = FakeModel([function_call("get_user_marker_types_with_data", 1)])
        result = run.run_case(case(), TOOLS, model, PREFIX)
        self.assertFalse(result["passed"])

    def test_one_wording_is_never_a_complete_run(self):
        model = FakeModel([function_call("get_marker_samples_compact", 1)])
        result = run.run_case(case(), TOOLS, model, PREFIX, questions=1)
        self.assertTrue(result["passed"])
        self.assertFalse(result["complete"])
        self.assertEqual(len(model.sent), 1)

    def test_only_the_listed_tools_are_offered(self):
        model = FakeModel([function_call("get_marker_samples_compact", 1)])
        run.run_case(case(tools=["get_marker_samples_compact"]), TOOLS, model, PREFIX, questions=1)
        self.assertEqual([f["name"] for f in model.sent[0][1]], [PREFIX + "get_marker_samples_compact"])


class SystemMessageTest(unittest.TestCase):
    def test_holds_only_the_facts(self):
        message = run.system_message({"patient_id": PATIENT, "today": "2026-03-14",
                                      "known_markers": {"Glucose": "m-1"}})
        self.assertEqual(message, f"The patient in this conversation is Arii user {PATIENT}.\n"
                                  "Today's date: 2026-03-14.\n"
                                  "Marker types already known for this patient: Glucose (m-1).")
        self.assertEqual(run.guard(message, TOOLS, PREFIX), [])

    def test_guard_finds_tool_and_argument_names_in_any_case(self):
        self.assertEqual(run.guard("Always send Tags and a cursor.", TOOLS, PREFIX), ["Tags", "cursor"])
        self.assertEqual(run.guard("Start with get_user_marker_types_with_data.", TOOLS, PREFIX),
                         ["get_user_marker_types_with_data"])
        self.assertEqual(run.guard("Use arii_mcp_get_marker_samples_compact.", TOOLS, PREFIX),
                         ["arii_mcp_get_marker_samples_compact"])

    def test_a_case_whose_system_message_names_an_argument_does_not_start(self):
        model = FakeModel()
        named = case(context={"patient_id": PATIENT, "today": "2026-03-14", "known_markers": {"cursor": "m-1"}})
        with self.assertRaises(run.CaseError):
            run.run_case(named, TOOLS, model, PREFIX)
        self.assertEqual(model.sent, [])


class ValidateTest(unittest.TestCase):
    def assertRefused(self, bad):
        with self.assertRaises(run.CaseError):
            run.validate(bad, TOOLS, PREFIX)

    def test_a_good_case_is_accepted(self):
        run.validate(PAGING, TOOLS, PREFIX)

    def test_refuses_anything_but_five_different_questions(self):
        self.assertRefused(case(questions=["a", "b", "c", "d"]))
        self.assertRefused(case(questions=["a", "b", "c", "d", "d"]))

    def test_refuses_unknown_tools_keys_and_checks(self):
        self.assertRefused(case(expect=[{"tool": "get_nothing"}]))
        self.assertRefused(case(never_tools=["get_nothing"]))
        self.assertRefused(case(expectt=[]))
        self.assertRefused(case(expect=[{"tool": "get_marker_samples_compact", "args": {"cursor": {"equal": "x"}}}]))
        self.assertRefused(case(expect=[{"tool": "get_marker_samples_compact", "call": 0}]))
        self.assertRefused(case(context={"patient_id": PATIENT}))
        self.assertRefused(case(expect=[]))

    def test_refuses_a_reply_text_that_is_not_json(self):
        self.assertRefused(case(replies=[{"tool": "get_marker_samples_compact", "reply": "{nextCursor: null}"}]))

    def test_refuses_a_system_message_that_names_an_argument(self):
        self.assertRefused(case(context={"patient_id": PATIENT, "today": "2026-03-14", "known_markers": {"tags": "m"}}))


class CaseFilesTest(unittest.TestCase):
    def test_every_case_file_is_valid_against_arii_yaml(self):
        if shutil.which("npx") is None:
            self.skipTest("npx not found: cannot bundle arii.yaml")
        root = Path(__file__).resolve().parents[1]
        spec = definitions.bundle(root / "arii.yaml")
        tools = definitions.build_tools(spec)
        cases = run.load_cases(root / "toolcalls" / "cases")
        self.assertTrue(cases)
        for tool, found in cases:
            with self.subTest(case=f"{tool}/{found.get('id')}"):
                run.validate(found, tools, definitions.tool_prefix(spec))
                self.assertTrue(any(e["tool"] == tool for e in found["expect"]), "a case checks a call to its own tool")


if __name__ == "__main__":
    unittest.main()
