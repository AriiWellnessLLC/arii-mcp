"""Check how the agent-facing spec tells a model to read many markers, in a Redocly JSON bundle.

Agents read every lab by listing them with `tags=labresult` and reading the ids 20 at a time,
following `nextCursor`. The pre-visit prompt points at these descriptions instead of repeating
them, so they must keep saying it. Seen on AIP139 on 2026-10-30: full 500-reading pages were
reported as not retrievable, and ids were dropped when a long list was split.
"""

import json
import os
from pathlib import Path
import unittest


class MarkerSamplesCompactReadingManyMarkersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = json.loads(Path(os.environ["ARII_OPENAPI_BUNDLE"]).read_text())
        cls.samples = spec["paths"]["/api/v2/Marker/samples-compact/{userId}"]["get"]
        cls.params = {p["name"]: p for p in cls.samples["parameters"] if "name" in p}
        cls.marker_types = spec["paths"]["/api/v2/Users/{userId}/DataDictionary/MarkerTypes"]["get"]

    def test_a_cursor_goes_back_with_exactly_the_same_parameters(self):
        text = self.samples["description"]
        self.assertIn("call again\nwith exactly the same parameters (the same `specificMarkers`, `takePerSource`, `limit`\nand dates) plus `cursor=<nextCursor>`", text)
        self.assertIn("Never send a cursor a reply did not give you.", text)

    def test_a_read_across_many_markers_or_sources_asks_for_small_pages(self):
        self.assertIn("send\n`limit=100` and follow more, smaller pages", self.samples["description"])
        self.assertIn("Send 100 when the read spans many markers or many sources.", self.params["limit"]["description"])

    def test_splitting_a_long_list_counts_every_id(self):
        self.assertIn("an id left out of every group is never read", self.params["specificMarkers"]["description"])
        self.assertIn("group 1 is ids 1–20, group 2 ids 21–40", self.marker_types["description"])
        self.assertIn("every id in exactly one group", self.marker_types["description"])


if __name__ == "__main__":
    unittest.main()
