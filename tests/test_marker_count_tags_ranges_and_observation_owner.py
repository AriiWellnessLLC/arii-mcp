"""Check the 9.0.0 contract changes in a Redocly JSON bundle of arii.yaml.

Covers the reading count tool, the tag filter on the marker list, the applied range on each
reading, and the required owner on list_observations. Each test reads what the spec declares,
so a later edit that drops one of these changes fails here.
"""

import json
import os
from pathlib import Path
import unittest


def load_spec():
    return json.loads(Path(os.environ["ARII_OPENAPI_BUNDLE"]).read_text())


def find_operation(spec, operation_id):
    for item in spec["paths"].values():
        for operation in item.values():
            if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                return operation
    raise AssertionError(f"{operation_id} is not in the spec")


def named_parameters(operation):
    # Shared parameters stay as a $ref in the bundle and have no name here.
    return {p["name"]: p for p in operation["parameters"] if "name" in p}


class MarkerSamplesCompactCountTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = load_spec()
        cls.count = find_operation(spec, "get_marker_samples_compact_count")
        cls.samples = find_operation(spec, "get_marker_samples_compact")
        cls.schemas = spec["components"]["schemas"]

    def test_the_count_takes_the_read_parameters_without_cursor_and_limit(self):
        read = named_parameters(self.samples)
        count = named_parameters(self.count)
        self.assertEqual(set(count), set(read) - {"cursor", "limit"})
        for name, parameter in count.items():
            with self.subTest(parameter=name):
                self.assertEqual(parameter["in"], read[name]["in"])
                self.assertEqual(parameter.get("required", False), read[name].get("required", False))
                self.assertEqual(parameter["schema"], read[name]["schema"])
        self.assertEqual(self.count["parameters"][0], self.samples["parameters"][0])
        self.assertIn("for the same parameters without `cursor` and `limit`", self.count["description"])

    def test_the_count_answers_with_count_and_whether_it_was_capped(self):
        response = self.count["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(response, {"$ref": "#/components/schemas/MarkerSamplesCompactCount"})
        properties = self.schemas["MarkerSamplesCompactCount"]["properties"]
        self.assertEqual(properties["count"]["type"], "integer")
        self.assertEqual(properties["countCapped"]["type"], "boolean")

    def test_the_count_stops_at_one_thousand(self):
        description = self.count["description"]
        self.assertIn("**The count stops at 1,000.**", description)
        self.assertIn("`count` is 1,000\nand `countCapped` is true", description)
        self.assertIn("at most 1,000", self.schemas["MarkerSamplesCompactCount"]["properties"]["count"]["description"])


class MarkerTypesTagFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.operation = find_operation(load_spec(), "get_user_marker_types_with_data")
        cls.tags = named_parameters(cls.operation)["tags"]

    def test_tags_is_an_optional_repeated_list_of_strings(self):
        self.assertEqual(self.tags["in"], "query")
        self.assertFalse(self.tags.get("required", False))
        self.assertEqual(self.tags["style"], "form")
        self.assertIs(self.tags["explode"], True)
        self.assertEqual(self.tags["schema"], {"type": "array", "items": {"type": "string"}})

    def test_blank_tags_are_refused_and_labresult_names_the_labs(self):
        description = self.tags["description"]
        self.assertIn("`labresult` is the tag of lab markers.", description)
        self.assertIn("A request whose every tag is blank is a 400.", description)
        self.assertIn("compared trimmed and ignoring case", description)
        self.assertEqual(self.operation["responses"]["400"]["description"], "Every tag sent is blank")
        self.assertIn("Call this with `tags=labresult`", self.operation["description"])


class ObservationListOwnerTest(unittest.TestCase):
    def test_list_observations_requires_the_user_id(self):
        parameter = named_parameters(find_operation(load_spec(), "list_observations"))["UserId"]
        self.assertEqual(parameter["in"], "query")
        self.assertIs(parameter["required"], True)
        self.assertEqual(parameter["schema"], {"type": "string", "format": "uuid"})
        self.assertIn("Always send it", parameter["description"])


class MarkerSampleRangesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = load_spec()
        cls.properties = spec["components"]["schemas"]["MarkerSampleCompact"]["properties"]
        cls.description = find_operation(spec, "get_marker_samples_compact")["description"]

    def test_range_status_is_low_high_or_in_range_and_can_be_null(self):
        for name in ("rangeStatus", "appliedRangeStatus"):
            with self.subTest(field=name):
                field = self.properties[name]
                self.assertEqual(field["type"], "string")
                self.assertIs(field["nullable"], True)
                self.assertEqual(field["enum"], ["L", "H", "InRange"])

    def test_a_reading_carries_the_range_that_applies_to_the_patient(self):
        self.assertEqual(
            self.properties["appliedReferenceRange"]["allOf"],
            [{"$ref": "#/components/schemas/AppliedReferenceRange"}],
        )
        self.assertEqual(self.properties["appliedOutOfRange"]["type"], "boolean")
        self.assertIs(self.properties["appliedOutOfRange"]["nullable"], True)
        self.assertIn("`appliedReferenceRange`,\n`appliedRangeStatus` and `appliedOutOfRange`", self.description)


if __name__ == "__main__":
    unittest.main()
