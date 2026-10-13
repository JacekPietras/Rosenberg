from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
HEARTBEAT_TIMEOUT = 5
last_heartbeat = [0.0]
page_seen = threading.Event()
stop_watcher = threading.Event()


class ViewerHandler(SimpleHTTPRequestHandler):
    def send_json(self, status, value):
        payload = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/docs/", "/docs/index.html"):
            last_heartbeat[0] = time.monotonic()
            page_seen.set()
        if self.path.split("?", 1)[0] == "/api/local-server":
            self.send_response(204)
            self.end_headers()
            return
        if self.path.split("?", 1)[0] == "/api/git-status":
            result = subprocess.run(
                ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False
            )
            if result.returncode:
                self.send_json(500, {"error": result.stderr.strip() or "Could not read Git status"})
                return
            self.send_json(200, {"changed": bool(result.stdout.strip())})
            return
        if self.path.split("?", 1)[0] == "/api/files":
            paths = [
                {
                    "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "version": path.stat().st_mtime_ns,
                }
                for folder in (ROOT / "data" / "books", ROOT / "data" / "letters", ROOT / "data" / "notes", ROOT / "data" / "images")
                for path in folder.glob("*.json")
            ]
            paths.sort(key=lambda item: item["path"])
            payload = json.dumps(paths).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def do_POST(self):
        if self.path.split("?", 1)[0] == "/api/heartbeat":
            last_heartbeat[0] = time.monotonic()
            page_seen.set()
            self.send_response(204)
            self.end_headers()
            return
        if self.path.split("?", 1)[0] == "/api/save-and-push":
            try:
                staged = subprocess.run(
                    ["git", "add", "-A"], cwd=ROOT, capture_output=True, text=True, check=False
                )
                if staged.returncode:
                    raise RuntimeError(staged.stderr.strip() or "Could not stage changes")
                pending = subprocess.run(
                    ["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False
                )
                if pending.returncode == 0:
                    self.send_json(200, {"ok": True, "changed": False})
                    return
                if pending.returncode != 1:
                    raise RuntimeError("Could not inspect staged changes")
                committed = subprocess.run(
                    ["git", "commit", "-m", "save"], cwd=ROOT, capture_output=True, text=True, check=False
                )
                if committed.returncode:
                    raise RuntimeError(committed.stderr.strip() or committed.stdout.strip() or "Commit failed")
                pushed = subprocess.run(
                    ["git", "push"], cwd=ROOT, capture_output=True, text=True, check=False
                )
                if pushed.returncode:
                    raise RuntimeError(
                        f"Commit created, but push failed: {pushed.stderr.strip() or pushed.stdout.strip()}"
                    )
                self.send_json(200, {"ok": True, "changed": True})
            except (OSError, RuntimeError) as error:
                self.send_json(500, {"error": str(error)})
            return
        if self.path.split("?", 1)[0] == "/api/restart-server":
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()

            def restart_server():
                environment = os.environ.copy()
                environment["ROSENBERG_SERVER_PORT"] = str(server.server_port)
                environment["ROSENBERG_NO_OPEN"] = "1"
                subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve())],
                    cwd=ROOT,
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                server.shutdown()
                server.server_close()

            threading.Thread(target=restart_server, daemon=False).start()
            return
        if self.path.split("?", 1)[0] != "/api/save-document":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            relative_path = payload["path"]
            document = payload["document"]
            target = (ROOT / relative_path).resolve()
            allowed = (target.is_relative_to(ROOT / "data") or target.is_relative_to(ROOT / "docs" / "assets")) and target.suffix == ".json"
            if not allowed or Path(relative_path).as_posix() != relative_path:
                raise ValueError("Invalid document path")
            is_entries_document = isinstance(document, dict) and isinstance(document.get("entries"), list)
            if not isinstance(document, list) and not is_entries_document:
                raise ValueError("Invalid document")
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                temporary = handle.name
            os.replace(temporary, target)
            self.send_json(200, {"ok": True, "version": target.stat().st_mtime_ns})
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError) as error:
            self.send_json(400, {"error": str(error)})


if __name__ == "__main__":
    # Serve from the repository root so both `python3 docs/serve.py` and
    # `cd docs && python3 serve.py` expose the advertised /docs/ URL.
    os.chdir(ROOT)
    port = int(os.environ.get("ROSENBERG_SERVER_PORT", "8000"))
    url = f"http://localhost:{port}/docs/"
    for attempt in range(50):
        try:
            server = ThreadingHTTPServer(("localhost", port), ViewerHandler)
            break
        except OSError as error:
            if attempt == 49:
                raise
            threading.Event().wait(0.1)
    print(f"Rosenberg viewer: {url}")
    if not os.environ.get("ROSENBERG_NO_OPEN"):
        webbrowser.open(url)

    def watch_heartbeat():
        while not stop_watcher.wait(0.25):
            if page_seen.is_set() and time.monotonic() - last_heartbeat[0] >= HEARTBEAT_TIMEOUT:
                server.shutdown()
                return

    threading.Thread(target=watch_heartbeat, daemon=True).start()
    server.serve_forever()
    stop_watcher.set()
    server.server_close()
