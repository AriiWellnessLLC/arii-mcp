"""Run the Release workflow's "Resolve the commit and its version" step against this checkout (AIP-697).

The step pipes `git show <sha>:arii.yaml` into awk. An awk that exits at the version closes the pipe
while git show is still writing the file, git show dies of SIGPIPE, and `set -o pipefail` fails the
step with exit 141: every Release run failed that way before a tag was ever made. These tests run the
step's own script, so they fail if it comes back. They need no bundle, only git and bash.
"""

from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
STEP = "Resolve the commit and its version"


def step_script(name: str) -> str:
    """The `run: |` block of the named step, dedented. Plain text, so the test needs no YAML package."""
    lines = WORKFLOW.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {name}")
    run = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    body = []
    for line in lines[run + 1:]:
        if line.strip() and not line.startswith(" " * 10):
            break
        body.append(line[10:])
    return "\n".join(body) + "\n"


def spec_version() -> str:
    """info.version of the committed arii.yaml: the file the step reads (HEAD), not the working tree."""
    text = subprocess.run(["git", "show", "HEAD:arii.yaml"], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout
    info = text[text.index("\ninfo:\n"):]
    return re.search(r'^  version:\s*"?([^"\s]+)"?\s*$', info, re.M).group(1)


class ReleaseResolveStepTest(unittest.TestCase):
    def test_step_reads_the_spec_version_and_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, summary = Path(tmp, "output"), Path(tmp, "summary")
            env = {**os.environ, "REF": "HEAD", "GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summary)}
            result = subprocess.run(["bash", "-e", "-c", step_script(STEP)], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, f"exit {result.returncode}: {result.stdout}{result.stderr}")
            outputs = dict(line.split("=", 1) for line in out.read_text().splitlines())
        version = spec_version()
        self.assertEqual(outputs["version"], version)
        self.assertEqual(outputs["tag"], f"v{version}")

    def test_no_awk_in_the_workflow_exits_before_its_input_ends(self):
        # The notes step reads the older release's version the same way; it is only reached with a
        # published release, so this checks the text of every awk program instead of running it.
        programs = re.findall(r"awk '([^']*)'", WORKFLOW.read_text())
        self.assertTrue(programs)
        for program in programs:
            with self.subTest(program):
                self.assertNotRegex(program, r"\bexit\b")


if __name__ == "__main__":
    unittest.main()
