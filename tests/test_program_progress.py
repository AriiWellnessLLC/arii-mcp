"""Check the program progress tool (AIP-605) in a Redocly JSON bundle of arii.yaml.

The tool reads one patient's active program enrolments. These tests hold the parts agents
build their calls and answers from: the path, the required `userId` that scopes the read to
one patient, and the response fields with their types and nullability, as agreed with
arii-api's `ProgramProgressDto`.
"""

import json
import os
from pathlib import Path
import unittest

PATH = "/api/v2/programs/enrollments/progress"

# Field name -> (type, format, nullable), from the AIP-605 contract for ProgramProgressDto.
EXPECTED_FIELDS = {
    "enrollmentId": ("string", "uuid", False),
    "name": ("string", None, False),
    "startDate": ("string", "date", False),
    "endDate": ("string", "date", True),
    "hasStarted": ("boolean", None, False),
    "lastDay": ("string", "date", True),
    "totalWeeks": ("integer", None, True),
    "currentWeek": ("integer", None, True),
    "tasksDone": ("integer", None, False),
    "tasksDue": ("integer", None, False),
}


class ProgramProgressTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(Path(os.environ["ARII_OPENAPI_BUNDLE"]).read_text())
        cls.operation = cls.spec["paths"][PATH]["get"]
        cls.schema = cls.spec["components"]["schemas"]["ProgramProgressDto"]

    def test_the_tool_sits_on_its_path_as_a_read(self):
        self.assertEqual("get_program_progress", self.operation["operationId"])
        self.assertEqual(["get"], list(self.spec["paths"][PATH]))
        self.assertEqual(
            {"readOnlyHint": True, "idempotentHint": True},
            self.operation["x-mcp-annotations"],
        )

    def test_the_read_is_scoped_to_one_patient_by_a_required_user_id(self):
        # The only parameter is the patient's id, and a call without it is not a valid call.
        parameters = self.operation["parameters"]
        self.assertEqual(1, len(parameters))
        user_id = parameters[0]
        self.assertEqual(("userId", "query"), (user_id["name"], user_id["in"]))
        self.assertTrue(user_id["required"])
        self.assertEqual({"type": "string", "format": "uuid"}, user_id["schema"])

    def test_the_answer_is_a_plain_list_of_program_progress(self):
        schema = self.operation["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual("array", schema["type"])
        self.assertEqual({"$ref": "#/components/schemas/ProgramProgressDto"}, schema["items"])

    def test_the_fields_match_the_contract(self):
        properties = self.schema["properties"]
        self.assertEqual(set(EXPECTED_FIELDS), set(properties))
        for name, (kind, fmt, nullable) in EXPECTED_FIELDS.items():
            with self.subTest(field=name):
                field = properties[name]
                self.assertEqual(kind, field["type"])
                self.assertEqual(fmt, field.get("format"))
                self.assertEqual(nullable, field.get("nullable", False))

    def test_the_description_says_active_only_empty_means_none_and_copy_the_counts(self):
        description = self.operation["description"]
        self.assertIn("Only Active enrolments are returned", description)
        self.assertIn("An empty list means the patient is not enrolled", description)
        self.assertIn("Copy them; never recompute them", description)


if __name__ == "__main__":
    unittest.main()
