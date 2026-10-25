from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jarvis import api

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
MAX_BODY = 64 * 1024
mimetypes.add_type("text/javascript", ".js")


class Handler(BaseHTTPRequestHandler):
    server_version = "JARVIS/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[jarvis] " + (fmt % args) + "\n")

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj, allow_nan=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/dataset":
            return self._json(200, api.dataset_info())
        if path == "/api/performance":
            return self._json(200, api.performance())
        if path == "/docs/case_study_source.md":
            src = ROOT / "docs" / "case_study_source.md"
            if src.is_file():
                return self._send(200, src.read_bytes(), "text/markdown; charset=utf-8")
        if path == "/":
            path = "/index.html"
        target = (WEB / path.lstrip("/")).resolve()
        if WEB.resolve() not in target.parents or not target.is_file():
            return self._json(404, {"ok": False, "error": "not found"})
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/run":
            return self._json(404, {"ok": False, "error": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._json(413, {"ok": False, "error": "request too large"})
        try:
            params = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(params, dict):
                raise ValueError("body must be a JSON object")
        except ValueError as e:
            return self._json(400, {"ok": False, "error": f"invalid JSON: {e}"})
        try:
            result = api.run(params)
        except Exception as e:
            return self._json(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})
        self._json(200, result)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="JARVIS Mission Console (web frontend)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8085)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"JARVIS Mission Console running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
