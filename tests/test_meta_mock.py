"""가짜 Graph 서버로 fetch_images 전 과정을 검증 (실제 Meta 호출 없음). 실행: python tests/test_meta_mock.py"""
import io
import json
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import fetch_images  # noqa: E402
from meta_api import MetaClient  # noqa: E402

PNG = io.BytesIO(); Image.new("RGB", (40, 30), "red").save(PNG, "PNG"); PNG = PNG.getvalue()
JPG = io.BytesIO(); Image.new("RGB", (30, 40), "blue").save(JPG, "JPEG"); JPG = JPG.getvalue()
SEEN = {"auth": set(), "cdn_auth": set(), "flaky": 0}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path.startswith("/cdn/"):
            SEEN["cdn_auth"].add(self.headers.get("Authorization"))
            return self._send(200, PNG if u.path.endswith("png") else JPG, "image/png" if u.path.endswith("png") else "image/jpeg")
        SEEN["auth"].add(self.headers.get("Authorization"))
        if u.path.endswith("/act_123/ads"):
            val = json.loads(q["filtering"][0])[0]["value"]
            if val.endswith("_IMGAD"):
                return self._send(200, json.dumps({"data": [{"name": val + "_240824_240920", "creative": {"image_url": f"http://127.0.0.1:{PORT}/cdn/a.png"}}]}).encode())
            if val.endswith("_VIDAD"):
                return self._send(200, json.dumps({"data": [{"name": val + "_x", "creative": {"video_id": "v1", "thumbnail_url": f"http://127.0.0.1:{PORT}/cdn/small.jpg"}}]}).encode())
            if val.endswith("_FLAKY") and SEEN["flaky"] < 1:
                SEEN["flaky"] += 1
                return self._send(429, b'{"error":{"code":17,"message":"rate"}}')
            if val.endswith("_FLAKY"):
                return self._send(200, json.dumps({"data": [{"name": val, "creative": {"thumbnail_url": f"http://127.0.0.1:{PORT}/cdn/t.jpg"}}]}).encode())
            return self._send(200, b'{"data":[]}')
        if u.path.endswith("/v1/thumbnails"):
            return self._send(200, json.dumps({"data": [{"uri": f"http://127.0.0.1:{PORT}/cdn/s.jpg", "width": 64, "height": 64},
                                                        {"uri": f"http://127.0.0.1:{PORT}/cdn/big.png", "width": 1080, "height": 1080}]}).encode())
        self._send(404, b"{}")


srv = HTTPServer(("127.0.0.1", 0), H)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

names = ["N1_IMGAD", "N2_VIDAD", "N3_FLAKY", "N4_NONE"]
fetch_images.needed_names = lambda _d: names
with tempfile.TemporaryDirectory() as d:
    client = MetaClient("SECRETTOKEN", "123", base=f"http://127.0.0.1:{PORT}", sleep=lambda s: None)
    rc = fetch_images.main(["--images", d, "--input", d], client=client)
    files = sorted(p.name for p in Path(d).iterdir())
    print("files:", files, "rc:", rc)
    assert rc == 3, "N4 는 실패로 보고되어야 함"
    assert files == ["N1_IMGAD.png", "N2_VIDAD.png", "N3_FLAKY.jpg"], files   # 영상은 큰 썸네일(png) 선택, 429 재시도 후 성공
    assert SEEN["auth"] == {"Bearer SECRETTOKEN"}
    assert SEEN["cdn_auth"] == {None}, "이미지 CDN 요청에는 토큰을 보내면 안 됨"
    # 다시 실행하면 이미 있는 건 건너뜀
    rc2 = fetch_images.main(["--images", d, "--input", d], client=client)
    assert len(list(Path(d).iterdir())) == 3
print("OK")
