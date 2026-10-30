"""Build the tool list the model sees, from arii.yaml, the way the Airia MCP gateway builds it.

The rules below were read off the gateway's own tool list (fixtures/gateway-tools.json):
- one tool per operation, named the lowercased `x-mcp-tool-prefix`, `_`, and the operationId;
- its description is the operation's `description`; `summary` is not used;
- path and query parameters and the JSON body's properties become one flat object;
- each argument keeps type, description, enum, default and items; `integer` becomes `number`,
  and format, minimum, maximum, minItems and maxItems are dropped;
- `items` is passed on as the spec has it, references resolved;
- `required` lists the required arguments, sorted, and is left out when there are none.
"""

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

REDOCLY = "@redocly/cli@1.25.0"
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
METHODS = ("get", "put", "post", "delete", "patch", "head", "options")
KEPT = ("description", "enum", "default", "items")


def bundle(spec_path):
    """The spec with every reference resolved, from the pinned Redocly CLI."""
    npx = shutil.which("npx")
    if npx is None:
        raise RuntimeError("npx not found: install Node.js to bundle the spec")
    spec_path = Path(spec_path).resolve()
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / "bundle.json"
        result = subprocess.run(
            [npx, "-y", REDOCLY, "bundle", str(spec_path), "--dereferenced", "--ext", "json", "-o", str(out)],
            capture_output=True, text=True,
        )
        if result.returncode != 0 or not out.exists():
            raise RuntimeError(f"Redocly could not bundle {spec_path}:\n{result.stderr or result.stdout}")
        return json.loads(out.read_text())


def tool_prefix(spec):
    return spec["info"]["x-mcp-tool-prefix"].lower() + "_"


def operations(spec):
    """Every operation in the spec, in file order."""
    found = []
    for path, item in spec["paths"].items():
        for method in METHODS:
            if method in item:
                found.append(item[method])
    return found


def argument(schema, description=None):
    """One argument as the gateway shows it."""
    out = {"type": "number" if schema.get("type") == "integer" else schema.get("type")}
    for key in KEPT:
        if key in schema:
            out[key] = schema[key]
    if description is not None:
        out["description"] = description
    if out["type"] is None:
        del out["type"]
    return out


def tool_from_operation(prefix, operation):
    """One tool: name, description and input schema, as the gateway builds it."""
    properties = {}
    required = set()
    for parameter in operation.get("parameters", []):
        if parameter["in"] not in ("path", "query"):
            raise ValueError(f"{operation['operationId']}: {parameter['in']} parameter {parameter['name']} is not supported")
        properties[parameter["name"]] = argument(parameter["schema"], parameter.get("description"))
        if parameter.get("required"):
            required.add(parameter["name"])
    body = operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
    if body is not None:
        for name, schema in body.get("properties", {}).items():
            properties[name] = argument(schema)
        required.update(body.get("required", []))
    input_schema = {"type": "object", "properties": properties}
    if required:
        input_schema["required"] = sorted(required)
    return {
        "name": prefix + operation["operationId"],
        "description": operation.get("description", ""),
        "inputSchema": input_schema,
    }


def build_tools(spec):
    """Every tool, sorted by name. Fails on a name the model API would refuse, or a repeated one."""
    prefix = tool_prefix(spec)
    tools = [tool_from_operation(prefix, operation) for operation in operations(spec)]
    names = [tool["name"] for tool in tools]
    bad = [name for name in names if not NAME_PATTERN.match(name)]
    if bad:
        raise ValueError(f"tool names the model API would refuse: {', '.join(bad)}")
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ValueError(f"tool names used twice: {', '.join(repeated)}")
    return sorted(tools, key=lambda tool: tool["name"])


def as_function(tool):
    """A tool in the Responses API's function format.

    Not strict: the Responses API makes a function strict by default, and a strict function has
    every argument required, so the model fills each one it does not need with "", 0 or [].
    """
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool["description"],
        "parameters": tool["inputSchema"],
        "strict": False,
    }
