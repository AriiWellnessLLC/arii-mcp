"""Check the agent-facing contract in a Redocly JSON bundle of arii.yaml."""

import json
import os
from pathlib import Path
import unittest


class ObservationSamplesContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(Path(os.environ["ARII_OPENAPI_BUNDLE"]).read_text())
        cls.operation = cls.spec["paths"]["/api/v3/Observation/healthkit/all-samples"]["get"]
        cls.parameters = {p["name"]: p for p in cls.operation["parameters"]}
        cls.schemas = cls.spec["components"]["schemas"]

    def test_observation_filter_is_an_optional_query_uuid(self):
        parameter = self.parameters["observationId"]
        self.assertEqual(parameter["in"], "query")
        self.assertFalse(parameter.get("required", False))
        self.assertEqual(parameter["schema"], {"type": "string", "format": "uuid"})

    def test_marker_filter_is_repeated_nonempty_and_optional(self):
        parameter = self.parameters["markerTypeIds"]
        self.assertEqual(parameter["in"], "query")
        self.assertFalse(parameter.get("required", False))
        self.assertEqual(parameter["style"], "form")
        self.assertIs(parameter["explode"], True)
        self.assertEqual(parameter["schema"], {
            "type": "array", "minItems": 1,
            "items": {"type": "string", "format": "uuid"},
        })
        self.assertIn("Combine with `observationId`", parameter["description"])

    def test_dates_allow_an_observation_read_without_a_window(self):
        for name in ("recordStartDate", "recordEndDate"):
            with self.subTest(parameter=name):
                parameter = self.parameters[name]
                self.assertFalse(parameter.get("required", False))
                self.assertEqual(parameter["schema"], {"type": "string", "format": "date"})
                self.assertIn("both dates may be omitted", parameter["description"])
                self.assertIn("`observationId` is present", parameter["description"])
        self.assertIn(
            "Otherwise both `recordStartDate` and `recordEndDate` are required",
            self.operation["description"],
        )

    def test_partial_date_pair_does_not_claim_to_narrow_an_observation(self):
        description = " ".join(self.operation["description"].split())
        self.assertIn("Send both dates or neither", description)
        self.assertIn("a partial pair does not narrow the observation-scoped read", description)

    def test_paging_keeps_the_agent_page_limit_and_defaults(self):
        self.assertEqual(self.parameters["pageNumber"]["schema"], {
            "type": "integer", "default": 0,
        })
        self.assertEqual(self.parameters["pageSize"]["schema"], {
            "type": "integer", "minimum": 1, "maximum": 100, "default": 100,
        })
        self.assertEqual(self.parameters["maxSamplesPerMarker"]["schema"]["type"], "integer")

    def test_response_keeps_paging_parent_observation_and_resolved_range(self):
        response = self.operation["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(response, {"$ref": "#/components/schemas/PagedObservationSamples"})
        page = self.schemas["PagedObservationSamples"]["properties"]
        self.assertEqual(page["items"], {
            "type": "array", "items": {"$ref": "#/components/schemas/ObservationSample"},
        })
        self.assertEqual(page["hasNextPage"], {"type": "boolean"})
        self.assertEqual(page["totalCount"], {"type": "integer"})
        sample = self.schemas["ObservationSample"]["properties"]
        self.assertEqual(sample["observation"]["type"], "object")
        self.assertEqual(sample["appliedReferenceRange"]["allOf"], [
            {"$ref": "#/components/schemas/AppliedReferenceRange"},
        ])

    def test_reference_range_provenance_and_null_guidance_are_preserved(self):
        source = self.schemas["AppliedReferenceRange"]["properties"]["source"]
        self.assertEqual(source["type"], "string")
        self.assertEqual(source["enum"], ["Platform", "Org", "Cohort", "Patient"])
        description = " ".join(self.operation["description"].split())
        self.assertIn("filtered by sex and converted to the sample's unit", description)
        self.assertIn("Null alone does not mean the marker has no range", description)
        self.assertIn("range printed on the lab report", description)

    def test_read_only_hints_and_failure_guidance_are_preserved(self):
        self.assertEqual(self.operation["x-mcp-annotations"], {
            "readOnlyHint": True, "idempotentHint": True,
        })
        responses = self.operation["responses"]
        self.assertIn("required unless observationId is provided", responses["400"]["description"])
        self.assertIn("marker filter", responses["400"]["description"])
        self.assertEqual(responses["403"]["description"],
                         "Requester is not permitted to read this user's samples")
        self.assertIn("A failure is never evidence that the person has none.",
                      " ".join(self.operation["description"].split()))

    def test_history_guidance_points_to_existing_compact_tools(self):
        operation_ids = {
            operation["operationId"]
            for path in self.spec["paths"].values()
            for method, operation in path.items()
            if method in ("get", "post")
        }
        for name in ("get_marker_averages_compact", "get_marker_samples_compact"):
            with self.subTest(tool=name):
                self.assertIn(name, operation_ids)
                self.assertIn(f"`{name}`", self.operation["description"])
        self.assertNotIn("`get_marker_averages`", self.operation["description"])
        self.assertNotIn("`get_marker_samples`", self.operation["description"])
