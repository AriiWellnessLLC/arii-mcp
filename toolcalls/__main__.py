"""python3.11 -m toolcalls [--spec arii.yaml] [--tool X] [--case Y] [--questions 1]

Exit codes: 0 every case passed on all five wordings; 1 a case failed; 2 the run could not start;
3 every wording asked passed, but --questions asked fewer than five, which is never a pass.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from . import definitions, model, run

HERE = Path(__file__).resolve().parent


def arguments(argv):
    parser = argparse.ArgumentParser(prog="python3.11 -m toolcalls",
                                     description="Ask the model each case's questions and check the tool calls it makes.")
    parser.add_argument("--spec", default="arii.yaml", help="the OpenAPI spec to build the tools from (default arii.yaml)")
    parser.add_argument("--tool", help="only the cases of this operationId")
    parser.add_argument("--case", help="only the case with this id")
    parser.add_argument("--questions", type=int, default=run.QUESTIONS, choices=range(1, run.QUESTIONS + 1),
                        help="ask only the first N wordings, for quick work; fewer than 5 is never a pass")
    parser.add_argument("--out", default=str(HERE / "out"), help="where the full results go (gitignored)")
    return parser.parse_args(argv)


def tokens(result):
    used = [usage for answer in result["answers"] for usage in answer["usage"]]
    return sum(u.get("input_tokens", 0) for u in used), sum(u.get("output_tokens", 0) for u in used), len(used)


def report(tool, result):
    asked = len(result["answers"])
    failed = [(i, answer) for i, answer in enumerate(result["answers"], 1) if not answer["passed"]]
    tokens_in, tokens_out, calls = tokens(result)
    status = "pass" if result["passed"] else "FAIL"
    print(f"{status} {tool}/{result['id']}: {asked - len(failed)}/{asked} wordings passed, {result['seconds']}s, "
          f"{calls} model calls, {tokens_in} tokens in, {tokens_out} out")
    for i, answer in failed:
        order = " -> ".join(call["name"] for call in answer["calls"]) or "(no calls)"
        print(f"  wording {i}: {answer['question']}")
        print(f"    calls: {order} ({answer['stopped']})")
        for call in answer["calls"]:
            print(f"      turn {call['turn']} {call['name']} {json.dumps(call['arguments'], sort_keys=True)}")
        for failure in answer["failures"]:
            print(f"    {failure}")


def main(argv=None):
    options = arguments(argv)
    try:
        config = model.load_config(HERE / "config.toml")
        key, endpoint = model.credentials(Path.cwd(), config)
        spec = definitions.bundle(options.spec)
        tools = definitions.build_tools(spec)
        prefix = definitions.tool_prefix(spec)
        cases = run.load_cases(HERE / "cases", options.tool, options.case)
        if not cases:
            raise run.CaseError("no case matches --tool and --case")
        for _, case in cases:
            run.validate(case, tools, prefix)
    except (model.ModelError, run.CaseError, RuntimeError, ValueError, OSError) as error:
        print(f"toolcalls: {error}", file=sys.stderr)
        return 2

    client = model.Model(endpoint, key, config["model"])
    started = time.monotonic()
    results = []
    for tool, case in cases:
        try:
            result = run.run_case(case, tools, client, prefix, options.questions)
        except model.ModelError as error:
            print(f"toolcalls: {tool}/{case['id']}: {error}", file=sys.stderr)
            return 2
        result["tool"] = tool
        results.append(result)
        report(tool, result)

    out = Path(options.out) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(
        {"spec": options.spec, "model": config["model"], "questions": options.questions, "results": results},
        indent=1) + "\n")

    passed = sum(result["passed"] for result in results)
    totals = [tokens(result) for result in results]
    print(f"\n{passed}/{len(results)} cases passed in {round(time.monotonic() - started, 1)}s; "
          f"{sum(t[2] for t in totals)} model calls, {sum(t[0] for t in totals)} tokens in, "
          f"{sum(t[1] for t in totals)} out. Full results: {out / 'results.json'}")
    if passed < len(results):
        return 1
    if options.questions < run.QUESTIONS:
        print(f"Only {options.questions} of {run.QUESTIONS} wordings asked: not a pass.")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
