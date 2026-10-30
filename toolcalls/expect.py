"""Argument checks for a tool call, and the case-level expectations built on them.

Values are compared exactly: "true" is not true, and 1 is not true. Numbers compare by value,
so 5 and 5.0 are equal. A TOML date is compared as its YYYY-MM-DD text, which is how the
model sends a date.
"""

import datetime
import re

CHECKS = ("equals", "absent", "present", "contains", "not_contains", "one_of", "range", "len", "matches",
          "same_as_call")
MISSING = object()


def plain(value):
    """TOML values as the model would send them: dates become YYYY-MM-DD text."""
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    return value


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def same(a, b):
    """Exact equality, except that numbers compare by value."""
    if is_number(a) and is_number(b):
        return a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b


def show(value):
    return "(absent)" if value is MISSING else repr(value)


def bounds(rule):
    if isinstance(rule, dict):
        unknown = set(rule) - {"min", "max"}
        if unknown or not rule:
            raise ValueError(f"expected min and/or max, got {sorted(rule)}")
        return rule.get("min"), rule.get("max")
    return rule, rule


def check_argument(name, value, checks, earlier=MISSING):
    """Failures for one argument. `value` is MISSING when the call left it out.
    `earlier` is the same argument in the call named by same_as_call."""
    failures = []

    def fail(check, expected):
        failures.append(f"{name}: {check} failed, expected {expected}, got {show(value)}")

    for check, rule in checks.items():
        if check not in CHECKS:
            raise ValueError(f"{name}: unknown check '{check}'")
        rule = plain(rule)
        if check == "absent":
            if rule is not True:
                raise ValueError(f"{name}: absent takes true")
            if value is not MISSING:
                fail(check, "no value")
            continue
        if check == "present":
            if rule is not True:
                raise ValueError(f"{name}: present takes true")
            if value is MISSING:
                fail(check, "a value")
            continue
        if check == "same_as_call":
            if not same(value, earlier) and not (value is MISSING and earlier is MISSING):
                fail(check, f"{show(earlier)} as in call {rule}")
            continue
        if value is MISSING:
            fail(check, f"a value for {check}")
            continue
        if check == "equals":
            if not same(value, rule):
                fail(check, repr(rule))
        elif check == "one_of":
            if not any(same(value, option) for option in rule):
                fail(check, f"one of {rule!r}")
        elif check in ("contains", "not_contains"):
            wanted = rule if isinstance(rule, list) else [rule]
            if isinstance(value, str):
                hits = [w for w in wanted if isinstance(w, str) and w in value]
            elif isinstance(value, list):
                hits = [w for w in wanted if any(same(item, w) for item in value)]
            else:
                fail(check, "a list or text")
                continue
            if check == "contains" and len(hits) != len(wanted):
                fail(check, f"to contain {[w for w in wanted if w not in hits]!r}")
            if check == "not_contains" and hits:
                fail(check, f"not to contain {hits!r}")
        elif check == "range":
            low, high = bounds(rule)
            comparable = (is_number(value) and all(b is None or is_number(b) for b in (low, high))) or (
                isinstance(value, str) and all(b is None or isinstance(b, str) for b in (low, high)))
            if not comparable or (low is not None and value < low) or (high is not None and value > high):
                fail(check, f"between {low} and {high}")
        elif check == "len":
            low, high = bounds(rule)
            if not isinstance(value, (list, str)):
                fail(check, "a list or text")
            elif (low is not None and len(value) < low) or (high is not None and len(value) > high):
                fail(check, f"length between {low} and {high}")
        elif check == "matches":
            if not isinstance(value, str) or re.fullmatch(rule, value) is None:
                fail(check, f"text matching {rule!r}")
    return failures


def merged(calls):
    """Every call's arguments as one: each argument's values from all calls, lists joined."""
    out = {}
    for call in calls:
        for name, value in call["arguments"].items():
            out.setdefault(name, []).extend(value if isinstance(value, list) else [value])
    return out


def check_expectation(expectation, calls, prefix):
    """Failures for one [[case.expect]] against the calls the model made, in order."""
    name = prefix + expectation["tool"]
    of_tool = [call for call in calls if call["name"] == name]
    which = expectation.get("call", 1)
    order = " -> ".join(call["name"] for call in calls) or "(no calls)"
    if not of_tool:
        return [f"expected a call to {name}, got: {order}"]
    if which == "all":
        targets = [("all calls", merged(of_tool))]
    elif which == "each":
        targets = [(f"call {i}", call["arguments"]) for i, call in enumerate(of_tool, 1)]
    else:
        if len(of_tool) < which:
            return [f"expected call {which} of {name}, it was called {len(of_tool)} time(s): {order}"]
        targets = [(f"call {which}", of_tool[which - 1]["arguments"])]

    def earlier_of(n):
        if n is None:
            return {}
        if len(of_tool) < n:
            raise LookupError(n)
        return of_tool[n - 1]["arguments"]

    reference = expectation.get("same_as_call")
    failures = []
    for label, arguments in targets:
        for argument, checks in expectation.get("args", {}).items():
            try:
                earlier = earlier_of(checks.get("same_as_call")).get(argument, MISSING)
            except LookupError as missing:
                failures.append(f"{name} {label}: {argument}: same_as_call failed, there is no call {missing}")
                continue
            for failure in check_argument(argument, arguments.get(argument, MISSING), checks, earlier):
                failures.append(f"{name} {label}: {failure}")
        if reference is not None:
            # Every argument not checked above must be exactly as in the reference call.
            try:
                before = earlier_of(reference)
            except LookupError:
                failures.append(f"{name} {label}: same_as_call failed, there is no call {reference}")
                continue
            for argument in sorted((set(before) | set(arguments)) - set(expectation.get("args", {}))):
                old, new = before.get(argument, MISSING), arguments.get(argument, MISSING)
                if not same(old, new) and not (old is MISSING and new is MISSING):
                    failures.append(f"{name} {label}: {argument}: same_as_call failed, expected {show(old)} "
                                    f"as in call {reference}, got {show(new)}")
    return failures


def check_run(case, calls, prefix, stopped):
    """Failures for the whole run: every expectation, plus never_tools, max_calls and max_turns."""
    failures = []
    for expectation in case.get("expect", []):
        failures.extend(check_expectation(expectation, calls, prefix))
    for tool in case.get("never_tools", []):
        if any(call["name"] == prefix + tool for call in calls):
            failures.append(f"{prefix + tool} was called, and this case never allows it")
    if "max_calls" in case and len(calls) > case["max_calls"]:
        failures.append(f"{len(calls)} calls, more than max_calls {case['max_calls']}")
    if stopped == "max_turns":
        failures.append(f"still calling tools after max_turns {case['max_turns']}")
    return failures
