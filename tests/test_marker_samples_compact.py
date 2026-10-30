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
        cls.info = spec["info"]["description"]

    def test_the_general_note_explains_both_paging_ways_without_naming_tools(self):
        note = self.info
        self.assertIn("**Page numbers.**", note)
        self.assertIn("**Cursor.**", note)
        self.assertIn("send exactly the same request again with `cursor` set to that value", note)
        self.assertNotIn("get_marker_samples_compact", note.split("**Paging.**", 1)[1].split("**Dates.**", 1)[0])

    def test_a_cursor_goes_back_with_exactly_the_same_request(self):
        text = self.samples["description"]
        self.assertIn("Send exactly the same request again (the same\n  `specificMarkers`, `takePerSource`, `limit` and dates) with `cursor` set to that\n  value.", text)
        self.assertIn("Send only a cursor a reply gave you.", text)

    def test_small_pages_unless_the_request_asks_for_a_size(self):
        self.assertIn("When the request doesn't ask for a particular page\nsize, send `limit=100`", self.samples["description"])
        self.assertIn("Send 100 unless the request asks for a particular page size.", self.params["limit"]["description"])

    def test_splitting_a_long_list_counts_every_id(self):
        self.assertIn("an id you leave out is never read", self.params["specificMarkers"]["description"])
        self.assertIn("ids 1–20, then 21–40, and so on, so every id\nis in exactly one group", self.marker_types["description"])

if __name__ == "__main__":
    unittest.main()
