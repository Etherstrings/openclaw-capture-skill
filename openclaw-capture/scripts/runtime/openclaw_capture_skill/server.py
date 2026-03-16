"""HTTP listener for the wrapper project."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import queue
import threading
import time
from typing import Callable

from .config import Settings
from .dispatcher import CaptureDispatcher, normalize_payload


class WrapperJobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, job_id: str) -> Path:
        return self.root / f"{job_id}.json"

    def save(self, job: dict) -> None:
        job_id = str(job["job_id"])
        path = self._path(job_id)
        body = json.dumps(job, ensure_ascii=False, indent=2).encode("utf-8")
        tmp_path = path.with_suffix(".json.tmp")
        with self._lock:
            tmp_path.write_bytes(body)
            tmp_path.replace(path)

    def load(self, job_id: str) -> dict | None:
        path = self._path(job_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None


class CaptureWorker:
    def __init__(self, dispatcher: CaptureDispatcher, jobs: WrapperJobStore) -> None:
        self.dispatcher = dispatcher
        self.jobs = jobs
        self._queue: "queue.Queue[dict]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="openclaw-capture-wrapper", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.put({"request_id": "__stop__"})
        if self._thread:
            self._thread.join(timeout=2)

    def enqueue(self, payload: dict) -> dict:
        normalized = normalize_payload(payload)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        job = {
            "job_id": normalized["request_id"],
            "status": "received",
            "created_at": now,
            "updated_at": now,
            "request": normalized,
            "message": "queued",
            "result": None,
            "error": None,
            "warnings": [],
        }
        self.jobs.save(job)
        self._queue.put(normalized)
        return job

    def _run(self) -> None:
        while not self._stop.is_set():
            payload = self._queue.get()
            try:
                if payload.get("request_id") == "__stop__":
                    continue
                job_id = str(payload["request_id"])
                queued = self.jobs.load(job_id) or {}
                queued["status"] = "processing"
                queued["message"] = "processing"
                queued["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self.jobs.save(queued)
                result = self.dispatcher.dispatch(payload)
                self.jobs.save(result)
            except Exception as exc:
                job_id = str(payload.get("request_id", "unknown"))
                failed = self.jobs.load(job_id) or {
                    "job_id": job_id,
                    "request": payload,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                failed["status"] = "failed"
                failed["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                failed["message"] = "failed"
                failed["error"] = str(exc)
                self.jobs.save(failed)
            finally:
                self._queue.task_done()


class RequestHandler(BaseHTTPRequestHandler):
    worker: CaptureWorker
    jobs: WrapperJobStore

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            return self._json(HTTPStatus.OK, {"ok": True})
        if self.path.startswith("/jobs/"):
            job_id = self.path.split("/")[-1]
            job = self.jobs.load(job_id)
            if job is None:
                return self._json(HTTPStatus.NOT_FOUND, {"error": "job not found"})
            return self._json(HTTPStatus.OK, job)
        return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/ingest":
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw)
            job = self.worker.enqueue(payload)
            return self._json(
                HTTPStatus.ACCEPTED,
                {
                    "job_id": job["job_id"],
                    "status": job["status"],
                    "message": "已收到，开始处理",
                },
            )
        except Exception as exc:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def _json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_server(settings: Settings, dispatcher: CaptureDispatcher | None = None) -> tuple[ThreadingHTTPServer, CaptureWorker]:
    state_dir = settings.state_dir
    jobs = WrapperJobStore(state_dir / "jobs")
    worker = CaptureWorker(dispatcher or CaptureDispatcher(settings), jobs)
    handler: Callable[..., RequestHandler] = RequestHandler
    handler.worker = worker
    handler.jobs = jobs
    server = ThreadingHTTPServer((settings.listen_host, settings.listen_port), handler)
    return server, worker


def run_server(settings: Settings | None = None, dispatcher: CaptureDispatcher | None = None) -> int:
    settings = settings or Settings.from_env()
    server, worker = build_server(settings, dispatcher=dispatcher)
    worker.start()
    try:
        print(f"openclaw-capture wrapper listening on http://{settings.listen_host}:{settings.listen_port}")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        worker.stop()
    return 0

