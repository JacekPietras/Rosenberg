from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
from html.parser import HTMLParser
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
HEARTBEAT_TIMEOUT = 20
last_heartbeat = [0.0]
page_seen = threading.Event()
stop_watcher = threading.Event()
family_rebuild_lock = threading.Lock()


class DriveFolderParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.current = None
        self.entry_depth = 0
        self.reading_name = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and attrs.get("id", "").startswith("entry-"):
            self.current = {"id": attrs["id"][6:], "text": []}
            self.entry_depth = 1
        elif self.current is not None and tag == "div":
            self.entry_depth += 1
            if "flip-entry-title" in attrs.get("class", "").split():
                self.reading_name = True

    def handle_data(self, data):
        if self.current is not None and self.reading_name:
            self.current["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "div" and self.current is not None:
            if self.reading_name:
                self.reading_name = False
            self.entry_depth -= 1
        if tag == "div" and self.current is not None and self.entry_depth == 0:
            name = " ".join("".join(self.current["text"]).split())
            if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff")):
                self.items.append({
                    "src": f"https://drive.google.com/thumbnail?id={self.current['id']}&sz=w1600",
                    "name": name,
                })
            self.current = None


class ViewerHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

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
                for folder in (ROOT / "data" / "books", ROOT / "data" / "documents", ROOT / "data" / "notes", ROOT / "data" / "images")
                for path in folder.rglob("*.json")
            ]
            paths.extend(
                {"path": path.relative_to(ROOT).as_posix(), "version": path.stat().st_mtime_ns}
                for path in [ROOT / "data/people.json", ROOT / "data/tree.json", ROOT / "data/places.json", ROOT / "data/names.md", ROOT / "data/titles.md", ROOT / "data/kinship.md", ROOT / "data/matching.json"]
                if path.is_file()
            )
            paths.sort(key=lambda item: item["path"])
            payload = json.dumps(paths).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.split("?", 1)[0] == "/api/document-image":
            image_url = parse_qs(urlparse(self.path).query).get("url", [""])[0]
            parsed_image_url = urlparse(image_url)
            allowed_image_hosts = {
                "api.digitale-sammlungen.de",
                "digi.ub.uni-heidelberg.de",
                "digitalisate-he.arcinsys.de",
                "digitalisate.frankfurt.de",
                "iiif.deutsche-digitale-bibliothek.de",
                "www.historisches-unterfranken.uni-wuerzburg.de",
                "www2.landesarchiv-bw.de",
            }
            if parsed_image_url.scheme not in ("http", "https") or parsed_image_url.hostname not in allowed_image_hosts:
                self.send_json(400, {"error": "Unsupported document image source"})
                return
            query = parse_qs(parsed_image_url.query)
            original_name = query.get("originalBilddatei", [""])[0]
            image_name = Path(original_name or parsed_image_url.path).name
            if not image_name.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")):
                self.send_json(400, {"error": "Could not determine the document image filename"})
                return
            cache_dir = ROOT / "data" / "documents" / "img-temp"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached = cache_dir / image_name
            mime_file = cache_dir / f"{image_name}.mime"
            try:
                if not cached.exists() or cached.stat().st_size == 0:
                    request = Request(image_url, headers={"User-Agent": "Rosenberg research image cache/1.0"})
                    with urlopen(request, timeout=45) as response:
                        image = response.read(80_000_001)
                        mime_type = response.headers.get_content_type()
                    if len(image) > 80_000_000 or not mime_type.startswith("image/"):
                        raise ValueError("The archive did not return a supported image")
                    cached.write_bytes(image)
                    mime_file.write_text(mime_type, encoding="ascii")
                image = cached.read_bytes()
                mime_type = mime_file.read_text(encoding="ascii") if mime_file.exists() else "image/jpeg"
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(image)))
                self.end_headers()
                self.wfile.write(image)
            except Exception as error:
                self.send_json(502, {"error": f"Could not cache document image: {error}"})
            return
        if self.path.split("?", 1)[0] == "/api/drive-thumbnail":
            query = parse_qs(urlparse(self.path).query)
            file_id = query.get("id", [""])[0]
            size = query.get("size", ["w480"])[0]
            scope = query.get("scope", ["images"])[0]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", file_id) or size not in ("w320", "w480", "original") or scope not in ("images", "documents"):
                self.send_json(400, {"error": "Invalid Drive thumbnail request"})
                return
            cache_dir = ROOT / "data" / scope / "img-temp"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached = cache_dir / f"drive-{file_id}-{size}.bin"
            mime_file = cache_dir / f"drive-{file_id}-{size}.mime"
            try:
                if not cached.exists() or cached.stat().st_size == 0:
                    source_url = (
                        f"https://drive.google.com/uc?export=download&id={file_id}"
                        if size == "original"
                        else f"https://drive.google.com/thumbnail?id={file_id}&sz={size}"
                    )
                    request = Request(
                        source_url,
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    with urlopen(request, timeout=30) as response:
                        max_bytes = 80_000_000 if size == "original" else 12_000_000
                        image = response.read(max_bytes + 1)
                        mime_type = response.headers.get_content_type()
                    if len(image) > max_bytes or not mime_type.startswith("image/"):
                        raise ValueError("Drive did not return a supported image")
                    cached.write_bytes(image)
                    mime_file.write_text(mime_type, encoding="ascii")
                image = cached.read_bytes()
                mime_type = mime_file.read_text(encoding="ascii") if mime_file.exists() else "image/jpeg"
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(image)))
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                self.end_headers()
                self.wfile.write(image)
            except Exception as error:
                self.send_json(502, {"error": f"Could not cache Drive thumbnail: {error}"})
            return
        if self.path.split("?", 1)[0] == "/api/drive-folder":
            folder_url = parse_qs(urlparse(self.path).query).get("url", [""])[0]
            parsed = urlparse(folder_url)
            if parsed.hostname != "drive.google.com" or not re.fullmatch(r"/drive/(?:u/\d+/)?folders/[^/]+/?", parsed.path):
                self.send_json(400, {"error": "Expected a Google Drive folder URL"})
                return
            try:
                folder_id = parsed.path.rstrip("/").split("/")[-1]
                request = Request(f"https://drive.google.com/embeddedfolderview?id={folder_id}#list", headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(request, timeout=25) as response:
                    html = response.read(20_000_000).decode("utf-8", "replace")
                parser = DriveFolderParser()
                parser.feed(html)
                self.send_json(200, {"images": parser.items})
            except Exception as error:
                self.send_json(502, {"error": f"Could not read Drive folder: {error}"})
            return
        super().do_GET()

    def do_POST(self):
        if self.path.split("?", 1)[0] == "/api/rebuild-family-tree":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 8192:
                    raise ValueError("Invalid rebuild request size")
                payload = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(payload, dict) or set(payload) - {"searchLimit"}:
                    raise ValueError("Invalid rebuild options")
                with family_rebuild_lock:
                    try:
                        metadata = json.loads((ROOT / "data/tree.json").read_text(encoding="utf-8"))
                    except (FileNotFoundError, ValueError):
                        metadata = {}
                    if not isinstance(metadata, dict):
                        metadata = {}
                    configuration = metadata.get("configuration", {})
                    if not isinstance(configuration, dict):
                        configuration = {}
                    saved_limit = configuration.get("searchLimit")
                    if type(saved_limit) is not int or saved_limit < 1:
                        saved_limit = 10000
                    search_limit = payload.get("searchLimit", saved_limit)
                    if type(search_limit) is not int or search_limit < 1:
                        raise ValueError("Invalid rebuild options")
                    command = [sys.executable, str(ROOT / "scripts/rebuild_family_tree.py"),
                               "--root", str(ROOT), "--apply", "--search-limit", str(search_limit)]
                    # Data edited during a build only requires building again.
                    for _ in range(3):
                        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                                check=False, timeout=120)
                        if result.returncode != 75:
                            break
                    if result.returncode:
                        self.send_json(422, {"error": result.stderr.strip() or result.stdout.strip() or "Could not rebuild family relationships"})
                        return
                self.send_json(200, {"ok": True})
            except (ValueError, TypeError, KeyError, IndexError) as error:
                self.send_json(400, {"error": str(error)})
            except subprocess.TimeoutExpired:
                self.send_json(504, {"error": "Rebuilding family relationships took too long. Please retry."})
            except OSError as error:
                self.send_json(500, {"error": f"Could not rebuild family relationships: {error}"})
            return
        if self.path.split("?", 1)[0] == "/api/save-document":
            print(
                f"Received document save request from {self.client_address[0]} "
                f"({self.headers.get('Content-Length', 'unknown')} bytes)",
                flush=True,
            )
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
            print(f"Document save failed for {locals().get('relative_path', '<unknown>')}: {error}", flush=True)
            self.send_json(400, {"error": str(error)})
        except Exception as error:
            print(f"Unexpected document save failure for {locals().get('relative_path', '<unknown>')}: {error}", flush=True)
            traceback.print_exc()
            self.send_json(500, {"error": "Unexpected server error while saving document"})


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
                print(f"No viewer heartbeat for {HEARTBEAT_TIMEOUT}s; stopping server.", flush=True)
                server.shutdown()
                return

    threading.Thread(target=watch_heartbeat, daemon=True).start()
    server.serve_forever()
    stop_watcher.set()
    server.server_close()
