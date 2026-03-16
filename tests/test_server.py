import json
import sys
import threading
import time
import unittest
from pathlib import Path
from urllib import request as urlrequest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "openclaw-capture" / "scripts" / "runtime"))

from openclaw_capture_skill.config import Settings
from openclaw_capture_skill.server import build_server


class FakeDispatcher:
    def dispatch(self, payload: dict) -> dict:
        return {
            "job_id": payload["request_id"],
            "status": "done",
            "created_at": "2026-03-17T00:00:00Z",
            "updated_at": "2026-03-17T00:00:01Z",
            "request": payload,
            "message": "completed",
            "result": {
                "summary": {"title": "ok"},
            },
            "error": None,
            "warnings": [],
        }


class WrapperServerTest(unittest.TestCase):
    def test_health_and_ingest_endpoints_work(self) -> None:
        settings = Settings(
            skill_root=(ROOT / "openclaw-capture").resolve(),
            project_root=ROOT.resolve(),
            state_dir=(ROOT / ".tmp-test-state").resolve(),
            listen_host="127.0.0.1",
            listen_port=0,
            backend_mode="library",
            backend_url="http://127.0.0.1:8765",
            stt_profile="remote_only",
            local_stt_command="",
            model_profile="aihubmix_gateway",
            model_api_base_url="https://example.com/v1",
            model_api_key="",
            outputs=(),
        )
        server, worker = build_server(settings, dispatcher=FakeDispatcher())
        worker.start()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            with urlrequest.urlopen(f"{base}/health", timeout=10) as resp:
                health = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(health, {"ok": True})

            req = urlrequest.Request(
                f"{base}/ingest",
                data=json.dumps(
                    {
                        "chat_id": "-1001",
                        "request_id": "server-test-001",
                        "source_kind": "pasted_text",
                        "raw_text": "server test",
                        "image_refs": [],
                        "requested_output_lang": "zh-CN",
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlrequest.urlopen(req, timeout=10) as resp:
                accepted = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(accepted["status"], "received")

            deadline = time.time() + 5
            job = None
            while time.time() < deadline:
                with urlrequest.urlopen(f"{base}/jobs/server-test-001", timeout=10) as resp:
                    job = json.loads(resp.read().decode("utf-8"))
                if job["status"] == "done":
                    break
                time.sleep(0.05)
            assert job is not None
            self.assertEqual(job["status"], "done")
        finally:
            server.shutdown()
            server.server_close()
            worker.stop()
            thread.join(timeout=2)
