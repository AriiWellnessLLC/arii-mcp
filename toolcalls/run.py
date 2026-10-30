"""Load cases, build the system message, run the turn loop and judge the calls."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import time
import tomllib

from . import definitions, expect

QUESTIONS = 5
DEFAULT_MAX_TURNS = 4
CASE_KEYS = {"id", "questions", "context", "tools", "replies", "expect", "never_tools", "max_calls", "max_turns"}
CONTEXT_KEYS = {"patient_id", "today", "known_markers"}
EXPECT_KEYS = {"tool", "call", "args", "same_as_call"}
REPLY_KEYS = {"tool", "when", "reply"}


class CaseError(ValueError):
    """A case file that cannot run as written."""


def load_cases(folder, tool=None, case_id=None):
    """Every case in cases/<operationId>.toml, as (operationId, case), filtered by --tool and --case."""
    found = []
    for path in sorted(Path(folder).glob("*.toml")):
        if tool and path.stem != tool:
            continue
        with path.open("rb") as handle:
            cases = tomllib.load(handle).get("case", [])
        for case in cases:
            if case_id and case.get("id") != case_id:
                continue
            found.append((path.stem, case))
    return found


def validate(case, tools, prefix):
    """Refuse a case that is malformed, names a tool or check that does not exist, or whose
    system message names a tool or argument."""
    where = f"case {case.get('id', '(no id)')}"
    tool_names = {tool["name"] for tool in tools}

    def known(tool):
        if prefix + tool not in tool_names:
            raise CaseError(f"{where}: no tool {prefix + tool} in the spec")

    if set(case) - CASE_KEYS:
        raise CaseError(f"{where}: unknown keys {sorted(set(case) - CASE_KEYS)}")
    if not isinstance(case.get("id"), str) or not case["id"]:
        raise CaseError(f"{where}: needs an id")
    questions = case.get("questions", [])
    if len(questions) != QUESTIONS or len(set(questions)) != QUESTIONS:
        raise CaseError(f"{where}: needs exactly {QUESTIONS} different questions, has {len(set(questions))}")
    context = case.get("context", {})
    if set(context) - CONTEXT_KEYS or not {"patient_id", "today"} <= set(context):
        raise CaseError(f"{where}: context takes patient_id, today and optional known_markers")
    offered = case.get("tools", "all")
    if offered != "all":
        for tool in offered:
            known(tool)
    if not case.get("expect"):
        raise CaseError(f"{where}: needs at least one [[case.expect]]")
    for expectation in case["expect"]:
        if set(expectation) - EXPECT_KEYS or "tool" not in expectation:
            raise CaseError(f"{where}: expect takes tool, call, args and same_as_call")
        known(expectation["tool"])
        which = expectation.get("call", 1)
        if which not in ("all", "each") and not (isinstance(which, int) and which >= 1):
            raise CaseError(f"{where}: call is a number from 1, \"each\" or \"all\"")
        for argument, checks in expectation.get("args", {}).items():
            unknown = set(checks) - set(expect.CHECKS)
            if unknown:
                raise CaseError(f"{where}: {argument}: unknown checks {sorted(unknown)}")
    for reply in case.get("replies", []):
        if set(reply) - REPLY_KEYS or "tool" not in reply or "reply" not in reply:
            raise CaseError(f"{where}: a reply takes tool, reply and optional when")
        known(reply["tool"])
        if isinstance(reply["reply"], str):
            try:
                json.loads(reply["reply"])
            except json.JSONDecodeError as error:
                raise CaseError(f"{where}: a reply given as text must be JSON: {error}") from None
    for tool in case.get("never_tools", []):
        known(tool)
    named = guard(system_message(context), tools, prefix)
    if named:
        raise CaseError(f"{where}: the system message names a tool or argument: {', '.join(named)}")


def system_message(context):
    """Only made-up facts: who the patient is, today's date, and markers already known."""
    lines = [
        f"The patient in this conversation is Arii user {context['patient_id']}.",
        f"Today's date: {expect.plain(context['today'])}.",
    ]
    known = context.get("known_markers", {})
    if known:
        listed = "; ".join(f"{label} ({marker})" for label, marker in known.items())
        lines.append(f"Marker types already known for this patient: {listed}.")
    return "\n".join(lines)


def guard(message, tools, prefix):
    """Words in the system message that name a tool or an argument. A rule cannot hide behind them.
    Compared as whole words, ignoring case."""
    words = set()
    for tool in tools:
        words.add(tool["name"])
        words.add(tool["name"][len(prefix):])
        words.update(tool["inputSchema"]["properties"])
    lowered = {word.lower() for word in words}
    return sorted({word for word in re.findall(r"[A-Za-z0-9_]+", message) if word.lower() in lowered})


def reply_for(case, call, prefix):
    """The first canned reply whose tool and conditions match the call, or None. A reply given as
    text is JSON, for what TOML cannot say, such as null."""
    for reply in case.get("replies", []):
        if prefix + reply["tool"] != call["name"]:
            continue
        conditions = reply.get("when", {})
        if all(not expect.check_argument(name, call["arguments"].get(name, expect.MISSING), checks)
               for name, checks in conditions.items()):
            given = reply["reply"]
            return json.loads(given) if isinstance(given, str) else expect.plain(given)
    return None


def ask(case, question, functions, model, prefix):
    """One wording, turn by turn. Stops when the model answers, a call has no canned reply,
    or max_turns is reached."""
    items = [
        {"role": "system", "content": system_message(case["context"])},
        {"role": "user", "content": question},
    ]
    calls, usage, failures = [], [], []
    stopped = "max_turns"
    started = time.monotonic()
    for turn in range(1, case.get("max_turns", DEFAULT_MAX_TURNS) + 1):
        response = model.respond(items, functions)
        usage.append(response.get("usage", {}))
        output = response.get("output", [])
        made = [item for item in output if item.get("type") == "function_call"]
        if not made:
            stopped = "answered"
            break
        items.extend(output)
        unanswered = None
        for item in made:
            try:
                arguments = json.loads(item.get("arguments") or "{}")
            except json.JSONDecodeError:
                failures.append(f"{item['name']}: arguments are not JSON: {item.get('arguments')!r}")
                arguments = {}
            call = {"turn": turn, "name": item["name"], "arguments": arguments}
            calls.append(call)
            reply = reply_for(case, call, prefix)
            if reply is None:
                unanswered = unanswered or item["name"]
                continue
            items.append({"type": "function_call_output", "call_id": item["call_id"], "output": json.dumps(reply)})
        if unanswered:
            stopped = f"no canned reply for {unanswered}"
            break
    failures.extend(expect.check_run(case, calls, prefix, stopped))
    return {
        "question": question,
        "passed": not failures,
        "failures": failures,
        "calls": calls,
        "stopped": stopped,
        "usage": usage,
        "seconds": round(time.monotonic() - started, 2),
    }


def run_case(case, tools, model, prefix, questions=QUESTIONS):
    """Ask the first `questions` wordings, in parallel. The case passes only if every wording asked
    passes, and it only counts as a pass when all five were asked."""
    message = system_message(case["context"])
    named = guard(message, tools, prefix)
    if named:
        raise CaseError(f"case {case['id']}: the system message names a tool or argument: {', '.join(named)}")
    offered = tools if case.get("tools", "all") == "all" else [
        tool for tool in tools if tool["name"][len(prefix):] in case["tools"]]
    functions = [definitions.as_function(tool) for tool in offered]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=questions) as pool:
        answers = list(pool.map(lambda q: ask(case, q, functions, model, prefix), case["questions"][:questions]))
    return {
        "id": case["id"],
        "passed": all(answer["passed"] for answer in answers),
        "complete": questions == QUESTIONS,
        "answers": answers,
        "seconds": round(time.monotonic() - started, 2),
    }
