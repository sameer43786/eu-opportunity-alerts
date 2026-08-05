import tempfile
import unittest
from pathlib import Path

import opportunity_monitor as monitor


CONFIG = {
    "criteria": {
        "minimum_score": 8,
        "require_any_groups": ["audience", "opportunity_type"],
        "require_topic_groups": ["technical_topics", "research"],
        "exclude_terms": ["applications are closed"],
        "age": {
            "reject_explicit_limits": True,
            "no_limit_terms": ["no age limit"],
            "exclude_patterns": [r"\baged?\s+18\s*(?:-|to)\s*30\b"],
        },
        "groups": {
            "audience": {"weight": 4, "terms": ["researcher", "phd student"]},
            "opportunity_type": {"weight": 4, "terms": ["training course"]},
            "technical_topics": {"weight": 5, "terms": ["cybersecurity", "artificial intelligence"]},
            "research": {"weight": 4, "terms": ["research"]},
        },
    }
}


class MonitorTests(unittest.TestCase):
    def item(self, summary):
        return monitor.Opportunity("AI training", "https://example.eu/call/1", "test", summary)

    def test_accepts_relevant_no_age_limit_call(self):
        item = self.item("Training course for PhD students and researchers in cybersecurity. No age limit.")
        result = monitor.evaluate(item, CONFIG, "")
        self.assertIsNotNone(result)
        self.assertEqual(result.age_status, "explicitly no limit")

    def test_rejects_explicit_age_cap(self):
        item = self.item("Cybersecurity training course for researchers aged 18-30.")
        self.assertIsNone(monitor.evaluate(item, CONFIG, ""))

    def test_rejects_closed_call(self):
        item = self.item("Cybersecurity training course for researchers; applications are closed.")
        self.assertIsNone(monitor.evaluate(item, CONFIG, ""))

    def test_state_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seen.json"
            monitor.save_state(path, {"abc", "xyz"})
            self.assertEqual(monitor.load_state(path), {"abc", "xyz"})


if __name__ == "__main__":
    unittest.main()
