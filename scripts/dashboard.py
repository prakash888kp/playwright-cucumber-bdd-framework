"""Local execution dashboard — run mode 4.

  python scripts/dashboard.py   →  http://localhost:4444

Pure standard library (http.server). Provides:
  GET  /                  dashboard UI (scripts/dashboard/index.html)
  GET  /api/scenarios     rows from config/execution-control.xlsx
  GET  /api/history       reports/run-history.json (newest first)
  GET  /api/status        { running, mode, startedAt }
  GET  /api/logs          SSE stream of the live run's console output
  POST /api/run           { mode, tags[], profile, env, browser, headless, screenshots }
  POST /api/stop          kill the in-flight run
  GET  /reports/*         static serving of report archives

Runs are spawned through scripts/run.py (same funnel as every other mode),
so timestamped archives + run-history keep working identically.
"""
import json
import mimetypes
import os
import queue
import subprocess
import sys
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.helpers.excel_reader import read_sheet  # noqa: E402

REPORTS_DIR = ROOT / "reports"
CONTROL_XLSX = ROOT / "config" / "execution-control.xlsx"
UI_FILE = Path(__file__).parent / "dashboard" / "index.html"
PORT = int(os.environ.get("DASHBOARD_PORT", 4444))
MAX_BUFFER = 500

# ---------------------------------------------------------------- run state
state_lock = threading.Lock()
child: subprocess.Popen | None = None
run_info: dict | None = None
log_buffer: list[str] = []
sse_clients: list[queue.Queue] = []


def broadcast(event: str, data):
    payload = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    with state_lock:
        for q in sse_clients:
            q.put(payload)


def push_log(line: str):
    with state_lock:
        log_buffer.append(line)
        del log_buffer[:-MAX_BUFFER]
    broadcast("log", line)


def _pump(proc: subprocess.Popen):
    global child, run_info
    for raw in proc.stdout:
        line = raw.rstrip()
        if line:
            push_log(line)
    code = proc.wait()
    push_log(f">>> Run finished with exit code {code}")
    broadcast("done", {"code": code})
    with state_lock:
        child = None
        run_info = None


def start_run(body: dict):
    global child, run_info, log_buffer
    with state_lock:
        if child is not None:
            raise RuntimeError("A run is already in progress")

    mode = body.get("mode", "tags")
    run_script = str(ROOT / "scripts" / "run.py")
    if mode == "excel":
        args = [sys.executable, run_script, "--excel"]
        label = "Excel control sheet (Run = YES)"
    elif mode == "profile":
        profile = body.get("profile", "smoke")
        args = [sys.executable, run_script, "--profile", profile]
        label = f"Profile: {profile}"
    else:
        tags = body.get("tags") or []
        if not tags:
            raise ValueError("No scenarios selected")
        expr = " or ".join(t if t.startswith("@") else f"@{t}" for t in tags)
        args = [sys.executable, run_script, "--tags", expr]
        label = f"Selected: {', '.join(tags)}"

    env = {**os.environ}
    if body.get("env"):
        env["ENV"] = body["env"]
    if body.get("browser"):
        env["BROWSER"] = body["browser"]
    if "headless" in body:
        env["HEADLESS"] = str(bool(body["headless"])).lower()
    if body.get("screenshots"):
        env["STEP_SCREENSHOTS"] = body["screenshots"]
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"

    with state_lock:
        log_buffer = []
        run_info = {"mode": mode, "label": label, "startedAt": datetime.now(UTC).isoformat()}
    push_log(
        f">>> {label}  [ENV={env.get('ENV', 'qa')} BROWSER={env.get('BROWSER', 'chromium')} "
        f"HEADLESS={env.get('HEADLESS', 'true')}]"
    )
    proc = subprocess.Popen(
        args, cwd=ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    with state_lock:
        child = proc
    threading.Thread(target=_pump, args=(proc,), daemon=True).start()


def stop_run() -> bool:
    with state_lock:
        proc = child
    if proc is None:
        return False
    push_log(">>> Stop requested — killing run...")
    if os.name == "nt":
        subprocess.run(["taskkill", "/pid", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()
    return True


# ---------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # silence per-request noise
        pass

    def _json(self, code: int, body):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _static(self, base_dir: Path, rel_path: str):
        file_path = (base_dir / rel_path).resolve()
        if not str(file_path).startswith(str(base_dir.resolve())):
            return self._json(403, {"error": "Forbidden"})
        if not file_path.is_file():
            return self._json(404, {"error": "Not found"})
        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/":
                return self._static(UI_FILE.parent, "index.html")
            if path == "/api/scenarios":
                return self._json(200, read_sheet(CONTROL_XLSX, "ExecutionControl"))
            if path == "/api/history":
                file = REPORTS_DIR / "run-history.json"
                history = json.loads(file.read_text(encoding="utf-8")) if file.exists() else []
                return self._json(200, list(reversed(history)))
            if path == "/api/status":
                with state_lock:
                    return self._json(200, {"running": child is not None, **(run_info or {})})
            if path == "/api/logs":
                return self._sse()
            if path.startswith("/reports/"):
                return self._static(REPORTS_DIR, unquote(path[len("/reports/"):]))
            self._json(404, {"error": "Not found"})
        except Exception as exc:
            self._json(400, {"error": str(exc)})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/run":
                with state_lock:
                    busy = child is not None
                if busy:
                    return self._json(409, {"error": "A run is already in progress"})
                start_run(body)
                return self._json(200, {"started": True})
            if path == "/api/stop":
                return self._json(200, {"stopped": stop_run()})
            self._json(404, {"error": "Not found"})
        except Exception as exc:
            self._json(400, {"error": str(exc)})

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        q: queue.Queue = queue.Queue()
        with state_lock:
            backlog = list(log_buffer)
            sse_clients.append(q)
        try:
            for line in backlog:
                self.wfile.write(f"event: log\ndata: {json.dumps(line)}\n\n".encode())
            self.wfile.flush()
            while True:
                try:
                    payload = q.get(timeout=15)
                    self.wfile.write(payload.encode())
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionError, OSError):
            pass
        finally:
            with state_lock:
                if q in sse_clients:
                    sse_clients.remove(q)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("=" * 60)
    print(f"  Test Automation Dashboard  ->  http://localhost:{PORT}")
    print("=" * 60)
    server.serve_forever()
