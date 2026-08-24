from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent


class ViewerHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/files":
            paths = [
                {
                    "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "version": path.stat().st_mtime_ns,
                }
                for folder in (ROOT / "data" / "books", ROOT / "data" / "letters")
                for path in folder.glob("*.json")
            ]
            seals_path = ROOT / "data" / "seals.json"
            if seals_path.is_file():
                paths.append({"path": "data/seals.json", "version": seals_path.stat().st_mtime_ns})
            paths.sort(key=lambda item: item["path"])
            payload = json.dumps(paths).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()


if __name__ == "__main__":
    print("Rosenberg viewer: http://localhost:8000/docs/")
    ThreadingHTTPServer(("localhost", 8000), ViewerHandler).serve_forever()
