import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "openclaw-capture" / "scripts" / "runtime"))

from openclaw_capture_skill.config import Settings
from openclaw_capture_skill.dispatcher import CaptureDispatcher


LEGACY_SRC = ROOT.parent / "openclaw_capture_workflow" / "src"
sys.path.insert(0, str(LEGACY_SRC))

from openclaw_capture_workflow.models import EvidenceBundle, SummaryResult


class StaticExtractor:
    def extract(self, request) -> EvidenceBundle:
        return EvidenceBundle(
            source_kind=request.source_kind,
            source_url=request.source_url,
            platform_hint=request.platform_hint,
            title="回放证据",
            text=(
                "这是稳定的本地测试证据，用于验证 mixed payload 不会丢失 URL、文字和图片，"
                "同时保证证据文本长度足够通过旧 workflow 的最小门控规则。"
            ),
            evidence_type="raw_text",
            coverage="full",
            metadata={"content_profile": {"kind": "general_capture"}, "signal_requirements": {}, "evidence_sources": ["test_fixture"]},
        )


class FakeSummaryEngine:
    def summarize(self, evidence) -> SummaryResult:
        return SummaryResult(
            title="本地包装测试",
            primary_topic="测试",
            secondary_topics=[],
            entities=[],
            conclusion="包装层成功复用了旧 workflow。",
            bullets=["保留了 mixed payload", "写入了 Obsidian 笔记"],
            evidence_quotes=["stable evidence"],
            coverage="full",
            confidence="high",
            note_tags=[],
            follow_up_actions=["检查输出"],
        )


class FakeNoteRenderer:
    def render(self, materials):
        return "# 包装测试\n\n本地包装测试\n"


class RecordingFanout:
    def __init__(self) -> None:
        self.calls = []

    def send_from_job_result(self, payload, job, skip_outputs=None) -> str:
        self.calls.append({"payload": payload, "job": job, "skip_outputs": skip_outputs})
        return "ok"


class DispatcherLibraryTest(unittest.TestCase):
    def test_library_mode_runs_legacy_workflow_in_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(
                skill_root=(ROOT / "openclaw-capture").resolve(),
                project_root=ROOT.resolve(),
                state_dir=Path(tmp) / "state",
                backend_mode="library",
                backend_url="http://127.0.0.1:8765",
                stt_profile="remote_only",
                local_stt_command="",
                model_profile="aihubmix_gateway",
                model_api_base_url="https://example.com/v1",
                model_api_key="key",
                outputs=("feishu",),
                telegram_bot_token="",
                feishu_webhook="https://example.com/hook",
                legacy_project_root=(ROOT.parent / "openclaw_capture_workflow").resolve(),
                legacy_config_path=None,
                vault_path_override=str(Path(tmp) / "vault"),
            )
            fanout = RecordingFanout()
            dispatcher = CaptureDispatcher(
                settings,
                extractor_override=StaticExtractor(),
                summary_engine=FakeSummaryEngine(),
                note_renderer=FakeNoteRenderer(),
                fanout_notifier=fanout,
            )
            payload = {
                "chat_id": "-10010002",
                "reply_to_message_id": "302",
                "request_id": "wrapper-library-test",
                "source_kind": "mixed",
                "source_url": "https://www.xiaohongshu.com/explore/69a3032400000000150305bb",
                "raw_text": "帮我把这条内容归档，重点看 Skill 名、安装方式和仓库链接。",
                "image_refs": ["/tmp/sample-xhs-skill.png"],
                "platform_hint": "xiaohongshu",
                "requested_output_lang": "zh-CN",
            }
            job = dispatcher.dispatch(payload)
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["request"]["source_kind"], "mixed")
            self.assertEqual(job["request"]["source_url"], payload["source_url"])
            self.assertEqual(job["request"]["raw_text"], payload["raw_text"])
            self.assertEqual(job["request"]["image_refs"], payload["image_refs"])
            self.assertTrue(job["result"]["open_url"].startswith("obsidian://"))
            self.assertEqual(len(fanout.calls), 1)

    def test_library_mode_uses_fallback_note_renderer_without_model_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(
                skill_root=(ROOT / "openclaw-capture").resolve(),
                project_root=ROOT.resolve(),
                state_dir=Path(tmp) / "state",
                backend_mode="library",
                backend_url="http://127.0.0.1:8765",
                stt_profile="remote_only",
                local_stt_command="",
                model_profile="aihubmix_gateway",
                model_api_base_url="https://example.com/v1",
                model_api_key="",
                outputs=(),
                telegram_bot_token="",
                feishu_webhook="",
                legacy_project_root=(ROOT.parent / "openclaw_capture_workflow").resolve(),
                legacy_config_path=None,
                vault_path_override=str(Path(tmp) / "vault"),
            )
            dispatcher = CaptureDispatcher(
                settings,
                extractor_override=StaticExtractor(),
                summary_engine=FakeSummaryEngine(),
            )
            payload = {
                "chat_id": "-10010002",
                "request_id": "wrapper-library-dry-run",
                "source_kind": "pasted_text",
                "raw_text": "OpenClaw Capture Skill 用于把内容送进本地工作流。",
                "image_refs": [],
                "requested_output_lang": "zh-CN",
                "dry_run": True,
            }
            job = dispatcher.dispatch(payload)
            self.assertEqual(job["status"], "done")
            note_preview = job["result"]["note_preview"]
            self.assertIn("content", note_preview)
            self.assertIn("一句话总结", note_preview["content"])

    def test_library_mode_uses_local_summary_engine_without_model_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(
                skill_root=(ROOT / "openclaw-capture").resolve(),
                project_root=ROOT.resolve(),
                state_dir=Path(tmp) / "state",
                backend_mode="library",
                backend_url="http://127.0.0.1:8765",
                stt_profile="remote_only",
                local_stt_command="",
                model_profile="aihubmix_gateway",
                model_api_base_url="https://example.com/v1",
                model_api_key="",
                outputs=(),
                telegram_bot_token="",
                feishu_webhook="",
                legacy_project_root=(ROOT.parent / "openclaw_capture_workflow").resolve(),
                legacy_config_path=None,
                vault_path_override=str(Path(tmp) / "vault"),
            )
            dispatcher = CaptureDispatcher(settings)
            payload = {
                "chat_id": "-10010002",
                "request_id": "wrapper-installed-like-dry-run",
                "source_kind": "pasted_text",
                "raw_text": "安装后的 skill 会在没有模型 key 时退回本地稳定摘要。",
                "image_refs": [],
                "requested_output_lang": "zh-CN",
                "dry_run": True,
            }
            job = dispatcher.dispatch(payload)
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["result"]["summary"]["conclusion"], "已基于输入文字生成本地可读摘要。")

    def test_library_mode_uses_local_summary_engine_for_dry_run_even_with_model_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(
                skill_root=(ROOT / "openclaw-capture").resolve(),
                project_root=ROOT.resolve(),
                state_dir=Path(tmp) / "state",
                backend_mode="library",
                backend_url="http://127.0.0.1:8765",
                stt_profile="remote_only",
                local_stt_command="",
                model_profile="aihubmix_gateway",
                model_api_base_url="https://example.com/v1",
                model_api_key="looks-like-a-real-key",
                outputs=(),
                telegram_bot_token="",
                feishu_webhook="",
                legacy_project_root=(ROOT.parent / "openclaw_capture_workflow").resolve(),
                legacy_config_path=None,
                vault_path_override=str(Path(tmp) / "vault"),
            )
            dispatcher = CaptureDispatcher(settings)
            payload = {
                "chat_id": "-10010002",
                "request_id": "wrapper-installed-like-dry-run-model-key",
                "source_kind": "pasted_text",
                "raw_text": "dry-run 应该始终走本地稳定摘要。",
                "image_refs": [],
                "requested_output_lang": "zh-CN",
                "dry_run": True,
            }
            job = dispatcher.dispatch(payload)
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["result"]["summary"]["conclusion"], "已基于输入文字生成本地可读摘要。")
            self.assertIn("content", job["result"]["note_preview"])


if __name__ == "__main__":
    unittest.main()
