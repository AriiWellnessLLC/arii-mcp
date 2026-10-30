"""Check that the tool-call tests build the model's tool list the way the Airia MCP gateway does."""

import json
from pathlib import Path
import shutil
import unittest

from toolcalls import definitions

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "toolcalls" / "fixtures" / "gateway-tools.json"


def operation(**fields):
    return {"operationId": "read_thing", "description": "Reads a thing.\n", **fields}


def query(name, schema, **fields):
    return {"name": name, "in": "query", "schema": schema, **fields}


class GatewayToolListTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FIXTURE.exists():
            raise unittest.SkipTest(f"{FIXTURE} is missing: no gateway tool list to compare with")
        cls.fixture = json.loads(FIXTURE.read_text())

    def test_every_tool_is_built_exactly_as_the_gateway_built_it(self):
        prefix = definitions.tool_prefix({"info": {"x-mcp-tool-prefix": self.fixture["toolPrefix"]}})
        for pair in self.fixture["tools"]:
            with self.subTest(tool=pair["tool"]["name"]):
                self.assertEqual(definitions.tool_from_operation(prefix, pair["operation"]), pair["tool"])

    def test_names_are_the_lowercased_prefix_and_the_operation_id(self):
        for pair in self.fixture["tools"]:
            self.assertEqual(pair["tool"]["name"], "arii_mcp_" + pair["operation"]["operationId"])


class ArgumentRulesTest(unittest.TestCase):
    def build(self, **fields):
        return definitions.tool_from_operation("arii_mcp_", operation(**fields))

    def test_description_is_the_operation_description_not_the_summary(self):
        tool = self.build(summary="Short title")
        self.assertEqual(tool["description"], "Reads a thing.\n")

    def test_integer_becomes_number_and_bounds_and_format_are_dropped(self):
        tool = self.build(parameters=[
            query("take", {"type": "integer", "minimum": 1, "maximum": 100, "default": 5}, description="How many."),
            query("day", {"type": "string", "format": "date"}),
        ])
        self.assertEqual(tool["inputSchema"]["properties"], {
            "take": {"type": "number", "default": 5, "description": "How many."},
            "day": {"type": "string"},
        })

    def test_items_are_kept_as_the_spec_has_them(self):
        items = {"type": "string", "format": "uuid", "description": "An id."}
        tool = self.build(parameters=[query("ids", {"type": "array", "minItems": 1, "maxItems": 20, "items": items})])
        self.assertEqual(tool["inputSchema"]["properties"]["ids"], {"type": "array", "items": items})

    def test_parameter_description_wins_over_the_schema_description(self):
        tool = self.build(parameters=[query("source", {"type": "string", "description": "Schema."}, description="Param.")])
        self.assertEqual(tool["inputSchema"]["properties"]["source"]["description"], "Param.")

    def test_path_query_and_body_make_one_object_with_required_sorted(self):
        tool = self.build(
            parameters=[{"name": "userId", "in": "path", "required": True, "schema": {"type": "string"}}],
            requestBody={"content": {"application/json": {"schema": {
                "type": "object", "required": ["query"],
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
            }}}},
        )
        self.assertEqual(sorted(tool["inputSchema"]["properties"]), ["limit", "query", "userId"])
        self.assertEqual(tool["inputSchema"]["required"], ["query", "userId"])

    def test_required_is_left_out_when_nothing_is_required(self):
        tool = self.build(parameters=[query("tag", {"type": "string"})])
        self.assertNotIn("required", tool["inputSchema"])

    def test_a_header_parameter_is_refused(self):
        with self.assertRaises(ValueError):
            self.build(parameters=[{"name": "X-Group", "in": "header", "schema": {"type": "string"}}])


class ToolNamesTest(unittest.TestCase):
    def spec(self, *operation_ids):
        paths = {f"/p{i}": {"get": operation(operationId=op)} for i, op in enumerate(operation_ids)}
        return {"info": {"x-mcp-tool-prefix": "Arii_MCP"}, "paths": paths}

    def test_a_name_the_model_api_refuses_fails_the_build(self):
        with self.assertRaises(ValueError):
            definitions.build_tools(self.spec("read thing"))
        with self.assertRaises(ValueError):
            definitions.build_tools(self.spec("x" * 60))

    def test_a_repeated_name_fails_the_build(self):
        with self.assertRaises(ValueError):
            definitions.build_tools(self.spec("read_thing", "read_thing"))

    def test_function_format_for_the_responses_api_is_not_strict(self):
        tool = definitions.build_tools(self.spec("read_thing"))[0]
        self.assertEqual(definitions.as_function(tool), {
            "type": "function", "name": "arii_mcp_read_thing", "description": "Reads a thing.\n",
            "parameters": {"type": "object", "properties": {}}, "strict": False,
        })


class CurrentSpecTest(unittest.TestCase):
    def test_every_operation_of_arii_yaml_becomes_one_valid_tool(self):
        if shutil.which("npx") is None:
            self.skipTest("npx not found: cannot bundle arii.yaml")
        spec = definitions.bundle(ROOT / "arii.yaml")
        tools = definitions.build_tools(spec)
        self.assertEqual(len(tools), len(definitions.operations(spec)))
        self.assertIn("arii_mcp_get_marker_samples_compact", [tool["name"] for tool in tools])


if __name__ == "__main__":
    unittest.main()
