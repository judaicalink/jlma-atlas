#!/usr/bin/env python3
"""Preview a build locally: dist/ at the base path, /kit/1/ from a checkout of judaicalink-mannheim, and a plain
stand-in for the platform bar (nginx includes the real one by SSI).

    python3 tools/serve.py [--dist dist] [--platform ../judaicalink-mannheim] [--port 8120]
"""

import argparse
import http.server
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SSI = b'<!--# include virtual="/kit/1/header.html" -->'
BAR = (b'<div style="padding:14px 16px;border-bottom:1px solid #8884;font:15px system-ui">'
       b'<a href="/">JudaicaLink Mannheim</a> (platform bar, local preview)</div>')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dist", type=Path, default=ROOT / "dist")
    ap.add_argument("--platform", type=Path, default=ROOT.parent / "judaicalink-mannheim")
    ap.add_argument("--base", default="/atlas/")
    ap.add_argument("--port", type=int, default=8120)
    args = ap.parse_args()
    kit = args.platform / "site" / "static" / "kit"

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            path = path.split("?", 1)[0].split("#", 1)[0]
            if path.startswith(args.base):
                return str(args.dist / path[len(args.base):])
            if path.startswith("/kit/"):
                return str(kit / path[len("/kit/"):])
            return str(args.dist / "__missing__")

        def send_head(self):
            p = Path(self.translate_path(self.path))
            if p.is_dir():
                p = p / "index.html"
            if p.suffix == ".html" and p.exists():
                body = p.read_bytes().replace(SSI, BAR)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                import io
                return io.BytesIO(body)
            return super().send_head()

    print(f"http://localhost:{args.port}{args.base}")
    http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
