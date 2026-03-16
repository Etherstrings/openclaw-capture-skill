import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "openclaw-capture" / "scripts" / "runtime"))

from openclaw_capture_skill.notifiers import FanoutNotifier


class FanoutNotifierTest(unittest.TestCase):
    def test_send_from_job_result_fans_out_to_both_outputs(self) -> None:
        telegram_payloads = []
        feishu_payloads = []
        notifier = FanoutNotifier(
            outputs=("telegram", "feishu"),
            telegram_bot_token="token",
            feishu_webhook="https://example.com/webhook",
            legacy_project_root=ROOT.parent / "openclaw_capture_workflow",
            text_renderer=lambda *args, **kwargs: "shared envelope",
            telegram_sender=telegram_payloads.append,
            feishu_sender=feishu_payloads.append,
        )
        notifier.send_from_job_result(
            {
                "chat_id": "-1001",
                "reply_to_message_id": "42",
                "request_id": "job-1",
                "source_kind": "url",
                "source_url": "https://example.com",
                "raw_text": None,
                "image_refs": [],
                "platform_hint": None,
                "requested_output_lang": "zh-CN",
            },
            {
                "status": "done",
                "result": {
                    "summary": {
                        "title": "测试结果",
                        "primary_topic": "测试",
                        "secondary_topics": [],
                        "entities": [],
                        "conclusion": "这是结论。",
                        "bullets": ["事实一"],
                        "evidence_quotes": [],
                        "coverage": "full",
                        "confidence": "high",
                        "note_tags": [],
                        "follow_up_actions": [],
                        "timeliness": "medium",
                        "effectiveness": "medium",
                        "recommendation_level": "recommended",
                        "reader_judgment": "",
                    },
                    "evidence": {
                        "source_kind": "url",
                        "source_url": "https://example.com",
                        "platform_hint": None,
                        "title": "Example",
                        "text": "body",
                        "evidence_type": "web",
                        "coverage": "full",
                        "transcript": None,
                        "keyframes": [],
                        "metadata": {},
                    },
                    "note": {
                        "note_path": "Inbox/OpenClaw/2026/03/test.md",
                        "structure_map": "map",
                        "obsidian_uri": "obsidian://open?path=Inbox/OpenClaw/2026/03/test.md",
                    },
                },
            },
        )
        self.assertEqual(len(telegram_payloads), 1)
        self.assertEqual(telegram_payloads[0]["chat_id"], "-1001")
        self.assertEqual(telegram_payloads[0]["reply_to_message_id"], "42")
        self.assertEqual(feishu_payloads, ["shared envelope"])

    def test_skip_outputs_works(self) -> None:
        telegram_payloads = []
        notifier = FanoutNotifier(
            outputs=("telegram",),
            telegram_bot_token="token",
            legacy_project_root=ROOT.parent / "openclaw_capture_workflow",
            text_renderer=lambda *args, **kwargs: "shared envelope",
            telegram_sender=telegram_payloads.append,
        )
        notifier.send_from_job_result(
            {
                "chat_id": "-1001",
                "request_id": "job-1",
                "source_kind": "url",
                "source_url": "https://example.com",
                "image_refs": [],
                "requested_output_lang": "zh-CN",
            },
            {
                "status": "done",
                "result": {
                    "summary": {"title": "T", "primary_topic": "T", "secondary_topics": [], "entities": [], "conclusion": "C", "bullets": [], "evidence_quotes": [], "coverage": "full", "confidence": "high", "note_tags": [], "follow_up_actions": []},
                    "evidence": {"source_kind": "url", "source_url": "https://example.com", "platform_hint": None, "title": "E", "text": "body", "evidence_type": "web", "coverage": "full", "metadata": {}},
                    "note": {"note_path": "n.md", "structure_map": "", "obsidian_uri": "obsidian://open?path=n.md"},
                },
            },
            skip_outputs={"telegram"},
        )
        self.assertEqual(telegram_payloads, [])


if __name__ == "__main__":
    unittest.main()

