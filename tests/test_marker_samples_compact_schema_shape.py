"""Check the shape of the compact readings read and its count, in a Redocly JSON bundle.

These tests read the schema structure, not the description text: the paths, the parameter
names and types, the page-size maximum, and which fields can be null. Agents build their
calls from this structure, so renaming `nextCursor`, making it non-nullable, changing the
500 maximum or moving the count path breaks them even when every sentence still reads well.
"""

import json
import os
from pathlib import Path
import unittest

SAMPLES_PATH = "/api/v2/Marker/samples-compact/{userId}"
COUNT_PATH = "/api/v2/Marker/samples-compact/{userId}/count"


def resolve(spec, node):
    """Follow a local $ref, such as #/components/schemas/X, to the object it names."""
    while isinstance(node, dict) and "$ref" in node:
        target = spec
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def parameters(spec, operation):
    resolved = (resolve(spec, p) for p in operation["parameters"])
    return {(p["name"], p["in"]): p for p in resolved}


def response_schema(spec, operation):
    content = operation["responses"]["200"]["content"]["application/json"]
    return resolve(spec, content["schema"])


def item_schema(spec, array_schema):
    return resolve(spec, array_schema["items"])


class MarkerSamplesCompactShapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(Path(os.environ["ARII_OPENAPI_BUNDLE"]).read_text())
        paths = cls.spec["paths"]
        cls.samples = paths[SAMPLES_PATH]["get"]
        cls.count = paths[COUNT_PATH]["get"]
        cls.samples_params = parameters(cls.spec, cls.samples)
        cls.count_params = parameters(cls.spec, cls.count)

    def test_both_tools_sit_on_their_paths(self):
        self.assertEqual("get_marker_samples_compact", self.samples["operationId"])
        self.assertEqual("get_marker_samples_compact_count", self.count["operationId"])

    def test_the_patient_is_a_required_path_parameter_on_both(self):
        for params in (self.samples_params, self.count_params):
            user_id = params[("userId", "path")]
            self.assertTrue(user_id["required"])

    def test_cursor_is_an_optional_string_query_parameter(self):
        cursor = self.samples_params[("cursor", "query")]
        self.assertFalse(cursor.get("required", False))
        self.assertEqual("string", cursor["schema"]["type"])

    def test_limit_is_an_integer_of_at_most_500_with_no_declared_default(self):
        limit = self.samples_params[("limit", "query")]["schema"]
        self.assertEqual("integer", limit["type"])
        self.assertEqual(500, limit["maximum"])
        # A declared default of 500 contradicts the description's advice to send 100.
        self.assertNotIn("default", limit)

    def test_the_count_does_not_page(self):
        names = {name for name, _ in self.count_params}
        self.assertNotIn("cursor", names)
        self.assertNotIn("limit", names)

    def test_both_take_the_same_filters(self):
        filters = {
            ("specificMarkers", "query"),
            ("recordStartDate", "query"),
            ("recordEndDate", "query"),
            ("latestPerSource", "query"),
            ("takePerSource", "query"),
            ("select", "query"),
            ("valueAbove", "query"),
            ("valueBelow", "query"),
            ("dataSources", "query"),
        }
        self.assertLessEqual(filters, set(self.samples_params))
        self.assertLessEqual(filters, set(self.count_params))
        self.assertEqual(20, self.samples_params[("specificMarkers", "query")]["schema"]["maxItems"])

    def test_next_cursor_is_a_nullable_string(self):
        result = response_schema(self.spec, self.samples)
        next_cursor = result["properties"]["nextCursor"]
        self.assertEqual("string", next_cursor["type"])
        self.assertTrue(next_cursor["nullable"])

    def test_the_count_returns_a_count_and_whether_it_was_capped(self):
        result = response_schema(self.spec, self.count)
        self.assertEqual("integer", result["properties"]["count"]["type"])
        self.assertEqual("boolean", result["properties"]["countCapped"]["type"])

    def test_the_applied_range_declares_bands_for_each_value(self):
        result = response_schema(self.spec, self.samples)
        reading = item_schema(self.spec, result["properties"]["items"])
        applied = resolve(self.spec, reading["properties"]["appliedReferenceRange"]["allOf"][0])
        segment = self.spec["components"]["schemas"]["ReferenceRangeSegment"]
        for name in ("segments", "secondValueSegments"):
            bands = applied["properties"][name]
            self.assertEqual("array", bands["type"], name)
            self.assertTrue(bands["nullable"], name)
            self.assertIs(segment, item_schema(self.spec, bands), name)

    def test_out_of_range_component_names_first_second_or_both(self):
        result = response_schema(self.spec, self.samples)
        reading = item_schema(self.spec, result["properties"]["items"])
        component = reading["properties"]["outOfRangeComponent"]
        self.assertEqual(["First", "Second", "Both"], component["enum"])


if __name__ == "__main__":
    unittest.main()
