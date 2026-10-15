"""테스트용 가짜 Meta Graph 서버 (모든 광고명에 이미지 1장, 계정 조회 OK)."""
import colorsys
import io
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from zlib import crc32

from PIL import Image


def png(seed):
    r, g, b = (int(255 * c) for c in colorsys.hsv_to_rgb((crc32(seed.encode()) % 360) / 360, .6, .9))
    buf = io.BytesIO(); Image.new("RGB", (1080, 1080), (r, g, b)).save(buf, "PNG"); return buf.getvalue()


STATE = {"expired": False}


def start():
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def send(self, code, body, ctype="application/json"):
            self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
            if u.path.startswith("/cdn/"):
                return self.send(200, png(urllib.parse.unquote(u.path[5:])), "image/png")
            if STATE["expired"]:
                return self.send(401, b'{"error":{"code":190,"message":"Session has expired"}}')
            if u.path.endswith("/ads"):
                v = json.loads(q["filtering"][0])[0]["value"]
                return self.send(200, json.dumps({"data": [{"name": v + "_260823_260829", "effective_status": "ACTIVE",
                                  "creative": {"image_url": f"http://127.0.0.1:{srv.server_address[1]}/cdn/{urllib.parse.quote(v)}"}}]}).encode())
            self.send(200, b'{"name":"Mock Account"}')

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
