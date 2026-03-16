from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "openclaw-capture" / "scripts" / "runtime"))

from openclaw_capture_skill.config import Settings
from openclaw_capture_skill.dispatcher import CaptureDispatcher


class RecordingFanout:
    def __init__(self) -> None:
        self.calls = []

    def send_from_job_result(self, payload, job, skip_outputs=None) -> str:
        self.calls.append({"payload": payload, "job": job, "skip_outputs": skip_outputs})
        return "ok"


class _Handler(BaseHTTPRequestHandler):
    post_payloads = []

    def do_POST(self):  # noqa: N802
        if self.path != "/ingest":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        _Handler.post_payloads.append(payload)
        body = json.dumps({"job_id": payload["request_id"], "status": "received"}).encode("utf-8")
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if not self.path.startswith("/jobs/"):
            self.send_response(404)
            self.end_headers()
            return
        job_id = self.path.split("/")[-1]
        body = json.dumps(
            {
                "job_id": job_id,
                "status": "done",
                "warnings": [],
                "result": {
                    "summary": {
                        "title": "HTTP 包装测试",
                        "primary_topic": "测试",
                        "secondary_topics": [],
                        "entities": [],
                        "conclusion": "HTTP 兼容模式可用。",
                        "bullets": ["调用了旧服务"],
                        "evidence_quotes": [],
                        "coverage": "full",
                        "confidence": "high",
                        "note_tags": [],
                        "follow_up_actions": [],
                    },
                    "evidence": {
                        "source_kind": "url",
                        "source_url": "https://example.com",
                        "platform_hint": None,
                        "title": "Example",
                        "text": "body",
                        "evidence_type": "web",
                        "coverage": "full",
                        "metadata": {},
                    },
                    "note": {
                        "note_path": "Inbox/OpenClaw/2026/03/http.md",
                        "structure_map": "map",
                        "obsidian_uri": "obsidian://open?path=Inbox/OpenClaw/2026/03/http.md",
                    },
                },
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A003
        return


class DispatcherHttpTest(unittest.TestCase):
    def test_http_mode_polls_job_and_skips_telegram_fanout(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                fanout = RecordingFanout()
                settings = Settings(
                    skill_root=(ROOT / "openclaw-capture").resolve(),
                    project_root=ROOT.resolve(),
                    state_dir=Path(tmp) / "state",
                    backend_mode="http",
                    backend_url=f"http://127.0.0.1:{server.server_address[1]}",
                    stt_profile="remote_only",
                    local_stt_command="",
                    model_profile="aihubmix_gateway",
                    model_api_base_url="https://example.com/v1",
                    model_api_key="key",
                    outputs=("telegram", "feishu"),
                    telegram_bot_token="token",
                    feishu_webhook="https://example.com/hook",
                    legacy_project_root=(ROOT.parent / "openclaw_capture_workflow").resolve(),
                    legacy_config_path=None,
                )
                dispatcher = CaptureDispatcher(settings, fanout_notifier=fanout)
                payload = {
                    "chat_id": "-10010003",
                    "request_id": "wrapper-http-test",
                    "source_kind": "url",
                    "source_url": "https://example.com",
                    "image_refs": [],
                    "requested_output_lang": "zh-CN",
                }
                job = dispatcher.dispatch(payload)
                self.assertEqual(job["status"], "done")
                self.assertTrue(job["result"]["open_url"].startswith("obsidian://"))
                self.assertEqual(_Handler.post_payloads[0]["request_id"], "wrapper-http-test")
                self.assertEqual(len(fanout.calls), 1)
                self.assertEqual(fanout.calls[0]["skip_outputs"], {"telegram"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

