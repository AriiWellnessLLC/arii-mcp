"""Tool-call tests: does the model call each Arii MCP tool right from its description alone?"""

import sys

# Case files are TOML, read with tomllib, which Python has from 3.11.
if sys.version_info < (3, 11):
    sys.exit(
        "toolcalls needs Python 3.11 or newer; this is "
        + sys.version.split()[0]
        + ". Run it with a newer interpreter, for example: python3.11 -m toolcalls"
    )
