from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import hashlib
from datetime import datetime, timezone
from html.parser import HTMLParser
import os
import queue
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
HEARTBEAT_TIMEOUT = 20
last_heartbeat = [0.0]
heartbeat_count = [0]
last_received_heartbeat = [None, 0.0]
last_heartbeat_sent = [None]
heartbeat_hosts = set()
last_request = [None, 0.0]
activity_lock = threading.Lock()
page_seen = threading.Event()
stop_watcher = threading.Event()
family_rebuild_lock = threading.Lock()
family_rebuild_status = {'active': False, 'stage': ''}
family_rebuild_status_lock = threading.Lock()
shutdown_reason = ['server stopped']
kev_process = [None]
kev_start_lock = threading.Lock()
KEV_URL = 'http://127.0.0.1:8009'


def ensure_kev_server():
    """Use an existing Kev server, or start one owned by this viewer server."""
    with kev_start_lock:
        try:
            with urlopen(f'{KEV_URL}/v1/models', timeout=2):
                return
        except Exception:
            pass
        if kev_process[0] is None or kev_process[0].poll() is not None:
            launcher = ROOT / 'scripts' / 'run_kev_local.sh'
            kev_process[0] = subprocess.Popen(
                [str(launcher)], cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        process = kev_process[0]
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Kev server exited during startup (exit {process.returncode})')
            try:
                with urlopen(f'{KEV_URL}/v1/models', timeout=2):
                    return
            except Exception:
                time.sleep(1)
        raise TimeoutError('Kev server did not become ready within 240 seconds')


def stop_owned_kev_server():
    process = kev_process[0]
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def record_event(reason):
    message = f"{datetime.now(timezone.utc).isoformat()} pid={os.getpid()} {reason}"
    print(f"Server log: {message}", flush=True)
    try:
        with (ROOT / 'server.log').open('a', encoding='utf-8') as log:
            log.write(message + '\n')
        return True
    except OSError as error:
        print(f"Could not write server log: {error}", file=sys.stderr, flush=True)
        return False


class ServerSignal(BaseException):
    pass


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
    def record_activity(self):
        path = self.path.split("?", 1)[0]
        now = time.monotonic()
        gap = None
        new_heartbeat_host = None
        with activity_lock:
            last_request[:] = [f'{self.command} {path}', now]
            if path in ('/docs/', '/docs/index.html') and self.command == 'GET':
                last_heartbeat[0] = now
                page_seen.set()
            elif path == '/api/heartbeat' and self.command == 'POST':
                host = self.headers.get('Host', '<missing>')
                if host not in heartbeat_hosts:
                    heartbeat_hosts.add(host)
                    new_heartbeat_host = host
                if last_received_heartbeat[0] and now - last_received_heartbeat[1] >= 20:
                    gap = now - last_received_heartbeat[1]
                last_heartbeat[0] = now
                heartbeat_count[0] += 1
                last_received_heartbeat[:] = [datetime.now(timezone.utc).isoformat(), now]
                page_seen.set()
        if gap is not None:
            record_event(f'heartbeat reception resumed after {gap:.1f}s gap')
        if new_heartbeat_host is not None:
            record_event(f'heartbeat received at host: {new_heartbeat_host}')

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
        self.record_activity()
        if self.path.split("?", 1)[0] == "/api/local-server":
            self.send_response(204)
            self.end_headers()
            return
        if self.path.split("?", 1)[0] == "/api/rebuild-status":
            with family_rebuild_status_lock:
                status = dict(family_rebuild_status)
            self.send_json(200, status)
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
            if parsed_image_url.scheme not in ("http", "https") or not parsed_image_url.hostname:
                self.send_json(400, {"error": "Unsupported document image source"})
                return
            query = parse_qs(parsed_image_url.query)
            original_name = query.get("originalBilddatei", [""])[0]
            image_name = Path(original_name or unquote(parsed_image_url.path)).name
            if not image_name.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")):
                self.send_json(400, {"error": "Could not determine the document image filename"})
                return
            cache_dir = ROOT / "data" / "documents" / "img-temp"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_key = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
            cached = cache_dir / f"{cache_key}{Path(image_name).suffix.lower()}"
            mime_file = cache_dir / f"{cached.name}.mime"
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
        self.record_activity()
        if self.path.split("?", 1)[0] == "/api/classify-document":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError("Invalid classification request size")
                payload = json.loads(self.rfile.read(length))
                relative_path = payload.get("path") if isinstance(payload, dict) else None
                if not isinstance(relative_path, str) or not re.fullmatch(r"data/documents/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.json", relative_path):
                    raise ValueError("Invalid document path")
                document_path = (ROOT / relative_path).resolve()
                if not document_path.is_relative_to(ROOT / "data" / "documents") or not document_path.is_file():
                    raise ValueError("Document not found")
                command = [sys.executable, str(ROOT / "scripts/kev_classify_documents.py"), "--document", relative_path]
                ensure_kev_server()
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=240, check=False)
                match = re.search(r"^.+?:\s+([a-z]+)\s+\(([0-9.]+)\)$", result.stderr, re.MULTILINE)
                if result.returncode or not match:
                    self.send_json(422, {"error": result.stderr.strip() or "Classification failed"})
                else:
                    self.send_json(200, {"result": f"{match.group(1)} {round(float(match.group(2)) * 100)}%"})
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json(400, {"error": str(error)})
            except subprocess.TimeoutExpired:
                self.send_json(504, {"error": "Classification timed out"})
            except OSError as error:
                self.send_json(500, {"error": str(error)})
            except RuntimeError as error:
                self.send_json(503, {"error": str(error)})
            return
        if self.path.split("?", 1)[0] == "/api/heartbeat-diagnostics":
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192:
                    raise ValueError('Invalid diagnostic size')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or not isinstance(payload.get('message'), str):
                    raise ValueError('Invalid diagnostic')
                message = payload['message'].replace('\n', ' ').replace('\r', ' ')[:6000]
                saved = record_event(f'browser heartbeat diagnostic: {message}')
                self.send_response(204 if saved else 500)
                self.end_headers()
            except (ValueError, TypeError, json.JSONDecodeError):
                self.send_error(400, 'Invalid diagnostic')
            return
        if self.path.split("?", 1)[0] == "/api/rebuild-family-tree":
            status_started = False
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 8192:
                    raise ValueError("Invalid rebuild request size")
                payload = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(payload, dict) or set(payload) - {"searchLimit"}:
                    raise ValueError("Invalid rebuild options")
                with family_rebuild_lock:
                    with family_rebuild_status_lock:
                        family_rebuild_status.update(active=True, stage='Starting family graph rebuild')
                    status_started = True
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
                    output = []
                    for _attempt in range(3):
                        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                                   stderr=subprocess.STDOUT, text=True, bufsize=1)
                        lines = queue.Queue()
                        def read_output():
                            for line in process.stdout:
                                lines.put(line.rstrip())
                            lines.put(None)
                        reader = threading.Thread(target=read_output, daemon=True)
                        reader.start()
                        deadline = time.monotonic() + 120
                        finished_reading = False
                        while process.poll() is None or not finished_reading:
                            if time.monotonic() >= deadline:
                                process.kill()
                                process.wait()
                                raise subprocess.TimeoutExpired(command, 120)
                            try:
                                line = lines.get(timeout=0.1)
                            except queue.Empty:
                                continue
                            if line is None:
                                finished_reading = True
                            else:
                                output.append(line)
                                if line.startswith('PROGRESS:'):
                                    with family_rebuild_status_lock:
                                        family_rebuild_status['stage'] = line[len('PROGRESS:'):]
                        reader.join(timeout=1)
                        if process.returncode != 75:
                            break
                        output.clear()
                    if process.returncode:
                        self.send_json(422, {"error": "\n".join(output).strip() or "Could not rebuild family relationships"})
                        return
                self.send_json(200, {"ok": True})
            except (ValueError, TypeError, KeyError, IndexError) as error:
                self.send_json(400, {"error": str(error)})
            except subprocess.TimeoutExpired:
                self.send_json(504, {"error": "Rebuilding family relationships took too long. Please retry."})
            except OSError as error:
                self.send_json(500, {"error": f"Could not rebuild family relationships: {error}"})
            finally:
                if status_started:
                    with family_rebuild_status_lock:
                        family_rebuild_status.update(active=False, stage='')
            return
        if self.path.split("?", 1)[0] == "/api/save-document":
            print(
                f"Received document save request from {self.client_address[0]} "
                f"({self.headers.get('Content-Length', 'unknown')} bytes)",
                flush=True,
            )
        if self.path.split("?", 1)[0] == "/api/heartbeat":
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if 0 < length <= 1024:
                    payload = json.loads(self.rfile.read(length))
                    sent_at = payload.get('sentAt') if isinstance(payload, dict) else None
                    if isinstance(sent_at, str) and len(sent_at) <= 64:
                        with activity_lock:
                            last_heartbeat_sent[0] = sent_at.replace('\n', ' ').replace('\r', ' ')
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
            self.send_response(204)
            origin = self.headers.get('Origin', '')
            allowed_origins = {f'http://localhost:{self.server.server_port}',
                               f'http://127.0.0.1:{self.server.server_port}'}
            if self.server.server_port == 80:
                allowed_origins.update(('http://localhost', 'http://127.0.0.1'))
            if origin in allowed_origins:
                self.send_header('Access-Control-Allow-Origin', origin)
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
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                shutdown_reason[0] = 'restart requested by viewer'
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
            with activity_lock:
                now = time.monotonic()
                timed_out = page_seen.is_set() and now - last_heartbeat[0] >= HEARTBEAT_TIMEOUT
                if timed_out:
                    request, request_time = last_request
                    heartbeat_time, heartbeat_monotonic = last_received_heartbeat
                    detail = (f'heartbeats received: {heartbeat_count[0]}; '
                              f'last heartbeat: {heartbeat_time or "none"}'
                              + (f' ({now - heartbeat_monotonic:.1f}s ago)' if heartbeat_time else '')
                              + f'; browser send time of last heartbeat received: {last_heartbeat_sent[0] or "unknown"}; '
                              f'last request: {request or "none"}'
                              + (f' ({now - request_time:.1f}s ago)' if request else ''))
            if timed_out:
                shutdown_reason[0] = f'no viewer heartbeat for {HEARTBEAT_TIMEOUT}s; {detail}'
                server.shutdown()
                return

    def handle_signal(signum, _frame):
        shutdown_reason[0] = f'received {signal.Signals(signum).name}'
        raise ServerSignal()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    threading.Thread(target=watch_heartbeat, daemon=True).start()
    try:
        server.serve_forever()
    except ServerSignal:
        pass
    except BaseException as error:
        shutdown_reason[0] = f'unexpected {type(error).__name__}: {error}'
        raise
    finally:
        stop_watcher.set()
        stop_owned_kev_server()
        server.server_close()
        record_event(shutdown_reason[0])
