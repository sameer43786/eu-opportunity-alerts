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

    def test_extracts_future_named_deadline(self):
        text = "Applications are open. Application deadline: 30 September 2099."
        self.assertEqual(monitor.extract_deadline(text), "2099-09-30")

    def test_extracts_rolling_status(self):
        text = "Applications are accepted on a rolling basis with no fixed deadline."
        self.assertEqual(monitor.extract_deadline(text), "Rolling; no fixed deadline stated")

    def test_dashboard_append_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "opportunities.json"
            path.write_text(
                '{"watch_title":"Test","updated_at":null,"source":"test","opportunities":[]}\n',
                encoding="utf-8",
            )
            item = self.item("Funded cybersecurity training course for researchers.")
            item.deadline = "2099-09-30"
            item.funding_evidence = ["stipend", "travel support"]
            item.score = 14
            item.matches = {"funding_support": ["stipend", "travel support"]}

            self.assertEqual(monitor.append_dashboard_items(path, [item]), 1)
            self.assertEqual(monitor.append_dashboard_items(path, [item]), 0)
            data = monitor.load_dashboard_data(path)
            self.assertEqual(len(data["opportunities"]), 1)
            self.assertEqual(data["opportunities"][0]["canonical_url"], item.url)
            self.assertIsNotNone(data["updated_at"])



if __name__ == "__main__":
    unittest.main()
