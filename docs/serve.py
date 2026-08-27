from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import tempfile

ROOT = Path(__file__).resolve().parent.parent


class ViewerHandler(SimpleHTTPRequestHandler):
    def send_json(self, status, value):
        payload = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/files":
            paths = [
                {
                    "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "version": path.stat().st_mtime_ns,
                }
                for folder in (ROOT / "data" / "books", ROOT / "data" / "letters", ROOT / "data" / "notes")
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
    print("Rosenberg viewer: http://localhost:8000/docs/")
    ThreadingHTTPServer(("localhost", 8000), ViewerHandler).serve_forever()
