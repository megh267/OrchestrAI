import os
import unittest
from unittest.mock import patch

import main


VALID_PAYLOAD = {
    "domain": "software",
    "available_hours": 8,
    "tasks": [
        {
            "title": "Fix login bug",
            "type": "Critical bug",
            "due_in_days": "Today",
            "effort_hours": 3,
        }
    ],
}


class ValidationTests(unittest.TestCase):
    def test_rejects_duplicate_titles(self):
        payload = {**VALID_PAYLOAD, "tasks": VALID_PAYLOAD["tasks"] * 2}
        with self.assertRaisesRegex(main.InputError, "unique"):
            main.validate_payload(payload)

    def test_rejects_unknown_domain(self):
        with self.assertRaisesRegex(main.InputError, "supported domain"):
            main.validate_payload({**VALID_PAYLOAD, "domain": "unknown"})

    def test_rejects_excessive_capacity(self):
        with self.assertRaisesRegex(main.InputError, "between"):
            main.validate_payload({**VALID_PAYLOAD, "available_hours": 500})


class ApiTests(unittest.TestCase):
    def setUp(self):
        main.app.config.update(TESTING=True)
        self.client = main.app.test_client()

    def test_health_does_not_expose_key(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "secret-value"}):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["configured"])
        self.assertNotIn("secret-value", response.get_data(as_text=True))

    def test_invalid_request_returns_400(self):
        response = self.client.post("/prioritise", json={"tasks": []})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    @patch("main.generate")
    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_prioritise_normalises_model_output(self, mock_generate):
        mock_generate.side_effect = [
            {
                "classifications": [
                    {"title": "Fix login bug", "category": "critical_bug"}
                ]
            },
            {
                "ranked_tasks": [
                    {
                        "title": "Fix login bug",
                        "category": "not-a-real-category",
                        "score": 140,
                        "reason": "Restore access for users.",
                    },
                    {
                        "title": "Invented task",
                        "category": "critical_bug",
                        "score": 100,
                        "reason": "Must not survive normalisation.",
                    },
                ],
                "action_plan": [
                    {"day": "Day 1", "tasks": ["Fix login bug", "Invented task"], "hours": 3}
                ],
                "readiness_score": 85,
            },
        ]

        response = self.client.post("/prioritise", json=VALID_PAYLOAD)
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["ranked_tasks"]), 1)
        self.assertEqual(data["ranked_tasks"][0]["category"], "critical_bug")
        self.assertEqual(data["ranked_tasks"][0]["score"], 100)
        self.assertEqual(data["action_plan"][0]["tasks"], ["Fix login bug"])
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    @patch("main.generate", side_effect=main.AIServiceError("The AI service is temporarily unavailable."))
    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_model_failure_returns_502(self, _mock_generate):
        response = self.client.post("/prioritise", json=VALID_PAYLOAD)
        self.assertEqual(response.status_code, 502)
        self.assertIn("request_id", response.get_json())

    @patch.dict(os.environ, {}, clear=True)
    def test_demo_mode_runs_without_api_key(self):
        response = self.client.post("/prioritise", json=VALID_PAYLOAD)
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["mode"], "demo")
        self.assertEqual(data["model"], "Local demo engine")
        self.assertEqual(len(data["ranked_tasks"]), 1)


if __name__ == "__main__":
    unittest.main()
