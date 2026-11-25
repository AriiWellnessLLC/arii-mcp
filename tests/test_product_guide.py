"""Check the product guide tools (AIP-697) in a Redocly JSON bundle of arii.yaml against arii-api's
content pages routes (arii-api #3612): what the API refuses with 400, the spec must not let the agent send."""

import json
import os
from pathlib import Path
import unittest


class ProductGuideContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = json.loads(Path(os.environ["ARII_OPENAPI_BUNDLE"]).read_text())
        cls.search = spec["paths"]["/api/v1/content-pages"]["get"]
        cls.read = spec["paths"]["/api/v1/content-pages/{slug}"]["get"]
        cls.params = {p["name"]: p for p in cls.search["parameters"]}
        cls.read_params = {p["name"]: p for p in cls.read["parameters"]}
        cls.schemas = spec["components"]["schemas"]

    def test_tool_names_and_read_only_hints(self):
        for op, name in ((self.search, "search_product_guide"), (self.read, "get_product_guide_page")):
            with self.subTest(name):
                self.assertEqual(op["operationId"], name)
                self.assertTrue(op["x-mcp-annotations"]["readOnlyHint"])
                self.assertTrue(op["x-mcp-annotations"]["idempotentHint"])

    def test_q_is_required_and_kept_to_key_words(self):
        q = self.params["q"]
        self.assertTrue(q["required"])
        self.assertIn("Never put a patient's name", " ".join(q["description"].split()))

    def test_kind_audience_and_limit_are_what_the_api_accepts(self):
        self.assertEqual(self.params["kind"]["schema"]["enum"], ["academy", "course"])
        self.assertEqual(self.params["kind"]["schema"]["default"], "academy")
        self.assertEqual(self.read_params["kind"]["schema"]["enum"], ["academy", "course"])
        self.assertEqual(set(self.params["audience"]["schema"]["enum"]),
                         {"admin", "provider", "care", "front", "dev", "patient"})
        limit = self.params["limit"]["schema"]
        self.assertEqual((limit["minimum"], limit["maximum"], limit["default"]), (1, 10, 10))

    def test_every_result_and_page_says_its_kind(self):
        for name in ("ProductGuideSearchResult", "ProductGuidePage"):
            with self.subTest(name):
                self.assertEqual(self.schemas[name]["properties"]["kind"]["enum"], ["academy", "course"])

    def test_only_the_page_carries_the_course_link_so_the_agent_reads_it(self):
        self.assertNotIn("learn", self.schemas["ProductGuideSearchResult"]["properties"])
        self.assertIn("learn", self.schemas["ProductGuidePage"]["properties"])
        self.assertIn("get_product_guide_page", self.search["description"])

    def test_search_says_to_search_both_kinds_every_time(self):
        # When the lessons were only a fallback, the chat skipped them and missed answers only a lesson has
        # ("Show filed", TEST CLINIC 37, 2026-11-25), even with a prompt that said to search both.
        text = " ".join(self.search["description"].split())
        self.assertIn("Search both kinds for every question", text)
        self.assertIn("`score` compares results only within one list", text)
        self.assertNotIn("help pages first", text)
        self.assertNotIn("when the help pages have nothing", text)
        # One empty list of the two is not "not in the guides".
        self.assertIn("When both lists are empty", text)
        self.assertNotIn("An empty list means", text)

    def test_read_takes_the_kind_of_the_chosen_result(self):
        # A lesson read as a help page answers 404.
        self.assertIn("the `kind` that result carries", " ".join(self.read["description"].split()))


if __name__ == "__main__":
    unittest.main()
