"""Check the 10.0.0 contract changes in a Redocly JSON bundle of arii.yaml.

Covers the reading count tool, the tag filter on the marker list, the ranges on each reading,
and the owner on list_observations. Each test reads what the spec declares,
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

    def test_a_capped_count_is_reported_as_at_least_the_count(self):
        # A capped count is a lower bound for both causes, so the spec never says "more than 1,000".
        properties = self.schemas["MarkerSamplesCompactCount"]["properties"]
        texts = {
            "description": self.count["description"],
            "200": self.count["responses"]["200"]["description"],
            "count": properties["count"]["description"],
            "countCapped": properties["countCapped"]["description"],
        }
        for name, text in texts.items():
            with self.subTest(text=name):
                self.assertIn("at least", text)
                self.assertNotIn("more than 1,000", text)
        self.assertIn('**When `countCapped` is true, say "at least N", where N is `count`.**', texts["description"])
        self.assertIn('Say "at least N", where N is `count`.', texts["countCapped"])
        self.assertIn("at most 1,000", texts["count"])

    def test_a_filtered_count_stops_after_judging_five_thousand_readings(self):
        # arii-api stops a filtered count after 5,000 readings (CompactSamplesScanLimit) and sets
        # countCapped with the matches found so far, which can be far below 1,000.
        description = self.count["description"]
        self.assertIn("stopped early: at 1,000 matches, or, for a count with `select`, `valueAbove` or\n`valueBelow`, after judging 5,000 readings.", description)
        self.assertIn("When the exact number matters, count again over a narrower window.", description)
        capped = self.schemas["MarkerSamplesCompactCount"]["properties"]["countCapped"]["description"]
        self.assertIn("after judging 5,000 readings", capped)
        self.assertIn("which can be well under 1,000", capped)
        self.assertIn("count again over a narrower window", capped)


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
    def test_the_user_id_is_optional_and_says_it_falls_back_to_the_caller(self):
        # arii-api reads the caller's own record when UserId is missing; it never refuses the call.
        parameter = named_parameters(find_operation(load_spec(), "list_observations"))["UserId"]
        self.assertEqual(parameter["in"], "query")
        self.assertFalse(parameter.get("required", False))
        self.assertEqual(parameter["schema"], {"type": "string", "format": "uuid"})
        self.assertIn("Left out, the API reads the caller's own record", parameter["description"])
        self.assertIn("Send it on every patient read.", parameter["description"])


def words(text):
    """The text with every run of spaces and line breaks made one space, so a re-wrapped line still matches."""
    return " ".join(text.split())


class ObservationCountTest(unittest.TestCase):
    """list_observations and get_observation_samples return totalCount and totalPages, but neither is a
    count of the rows the person has. An agent that quoted them gave wrong workout and appointment
    counts, so the spec tells it to read every page and count the rows, in the general rules and on
    both tools."""

    @classmethod
    def setUpClass(cls):
        cls.spec = load_spec()

    def test_the_general_rules_say_the_two_reads_carry_no_count(self):
        info = words(self.spec["info"]["description"])
        self.assertIn("Two paged reads carry no count: `list_observations` and `get_observation_samples`.** "
                      "Never use their `totalCount` or `totalPages`. For how many, read every page — the largest "
                      "`PageSize`, then the next `PageNumber`, until `hasNextPage` is false — and count the rows "
                      "you received.", info)
        self.assertIn("For \"how many\", quote `totalCount` rather than counting rows, except on `list_observations` "
                      "and `get_observation_samples`: read every page of those and count the rows.", info)

    def test_each_of_the_two_reads_says_it_carries_no_count(self):
        for operation_id in ("list_observations", "get_observation_samples"):
            with self.subTest(operation=operation_id):
                description = words(find_operation(self.spec, operation_id)["description"])
                self.assertIn("The response carries no count: never use `totalCount` or `totalPages`.", description)
                self.assertIn("`hasNextPage`", description)


class SharedNotesOwnerTest(unittest.TestCase):
    def test_the_user_id_is_optional_and_says_it_falls_back_to_the_caller(self):
        # Like list_observations: arii-api reads the caller's own shared notes when userId is missing.
        parameter = named_parameters(find_operation(load_spec(), "get_shared_notes"))["userId"]
        self.assertEqual(parameter["in"], "query")
        self.assertFalse(parameter.get("required", False))
        self.assertIn("Left out, the API reads the caller's own shared notes.", words(parameter["description"]))


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

    def test_out_of_range_false_can_mean_no_printed_range(self):
        description = self.properties["outOfRange"]["description"]
        self.assertEqual(self.properties["outOfRange"]["type"], "boolean")
        self.assertIn("False also means the reading has no printed range that can judge it", description)
        self.assertIn("look at `appliedOutOfRange`", description)

    def test_a_two_value_reading_names_the_value_out_of_range_as_a_string(self):
        # MarkerSampleCompactDto.OutOfRangeComponent carries JsonStringEnumConverter and is not
        # written when null, so it is a string enum that is absent rather than null.
        field = self.properties["outOfRangeComponent"]
        self.assertEqual(field["type"], "string")
        self.assertEqual(field["enum"], ["First", "Second", "Both"])
        self.assertNotIn("nullable", field)
        self.assertIn("`First` is `value`", field["description"])
        self.assertIn("`Second` is `secondValue`", field["description"])
        self.assertIn("On blood pressure `value` is systolic", field["description"])
        self.assertIn("Absent on a one-value reading", field["description"])


if __name__ == "__main__":
    unittest.main()
