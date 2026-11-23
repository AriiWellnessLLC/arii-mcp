"""Check the steering the Airia team corrected by hand for 10.0.0, in a Redocly JSON bundle of arii.yaml.

The corrections lived only in the Airia catalog, so 11.0.0, 12.0.0 and the first draft of 12.1.0 were
built from this file without them and put the old wording back. These tests keep them here:

- the reading count answers reading questions, and a day question goes to `readingDays` on the
  preferred source's row, never summed across sources;
- every Bearer-only compact marker read says so in its operation description, because mcp-link
  does not show response text to the model, and the overview lists all four.
"""

import json
import os
from pathlib import Path
import unittest

COMPACT_READS = (
    "get_marker_summary_compact",
    "get_marker_averages_compact",
    "get_marker_samples_compact",
    "get_marker_samples_compact_count",
)


def load_spec():
    return json.loads(Path(os.environ["ARII_OPENAPI_BUNDLE"]).read_text())


def find_operation(spec, operation_id):
    for item in spec["paths"].values():
        for operation in item.values():
            if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                return operation
    raise AssertionError(f"{operation_id} is not in the spec")


def words(text):
    """The text with every run of spaces and line breaks made one space, so a re-wrapped line still matches."""
    return " ".join(text.split())


class ReadingCountIsNotADayCountTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = load_spec()
        cls.count = words(find_operation(spec, "get_marker_samples_compact_count")["description"])
        cls.samples = words(find_operation(spec, "get_marker_samples_compact")["description"])

    def test_the_count_never_offers_a_day_question_as_its_example(self):
        # The examples are the sentence before the reading-versus-day paragraph; no day question may sit there.
        examples = self.count.split("**It counts readings, not days.**")[0]
        self.assertNotIn("days", examples)
        self.assertIn('"how many glucose readings above 180 this month", "how many blood pressure readings', self.count)

    def test_a_day_question_goes_to_reading_days_on_the_preferred_source_row(self):
        self.assertIn("**It counts readings, not days.**", self.count)
        self.assertIn(
            "read `readingDays` on the `isPreferredSource` row of `get_marker_averages_compact`", self.count)

    def test_reading_days_are_never_added_across_sources(self):
        self.assertIn(
            "Never add `readingDays` across sources: a day logged by two sources is in both rows.", self.count)

    def test_the_value_filter_example_asks_for_readings_not_days(self):
        self.assertNotIn('"days her blood pressure was over 140"', self.samples)
        self.assertIn('"her blood pressure readings over 140"', self.samples)


class BearerOnlyIsInTheOperationDescriptionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load_spec()

    def test_each_compact_read_says_bearer_only_where_the_model_reads_it(self):
        for tool in COMPACT_READS:
            with self.subTest(tool=tool):
                operation = find_operation(self.spec, tool)
                self.assertIn("401", operation["responses"])
                description = words(operation["description"])
                self.assertTrue(
                    "Bearer only: under API Key it returns 401." in description
                    or "This read is Bearer only; under `X-API-Key` it returns 401." in description,
                    description[:200])

    def test_the_overview_lists_all_four_compact_reads_as_bearer_only(self):
        overview = words(self.spec["info"]["description"])
        listed = ", ".join(f"`{tool}`" for tool in COMPACT_READS)
        self.assertIn(f"The four compact marker reads ({listed}) are **Bearer only**", overview)


if __name__ == "__main__":
    unittest.main()
