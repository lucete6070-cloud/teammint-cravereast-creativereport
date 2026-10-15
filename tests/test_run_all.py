"""보조 PC 와 같은 조건(코드만 복사 + CSV + .env)에서 run_all 을 가짜 Meta 서버로 끝까지 실행해 본다. 실행: python tests/test_run_all.py"""
import colorsys
import io
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from zlib import crc32

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def png(seed):
    r, g, b = (int(255 * c) for c in colorsys.hsv_to_rgb((crc32(seed.encode()) % 360) / 360, .6, .9))
    buf = io.BytesIO(); Image.new("RGB", (1080, 1080), (r, g, b)).save(buf, "PNG"); return buf.getvalue()


STATE = {"expired": False, "seen_token": set()}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path.startswith("/cdn/"):
            return self.send(200, png(urllib.parse.unquote(u.path[5:])), "image/png")
        STATE["seen_token"].add(self.headers.get("Authorization"))
        if STATE["expired"]:
            return self.send(401, b'{"error":{"code":190,"message":"Session has expired"}}')
        if u.path.endswith("/ads"):
            v = json.loads(q["filtering"][0])[0]["value"]
            return self.send(200, json.dumps({"data": [{"name": v + "_260823_260829", "effective_status": "ACTIVE",
                              "creative": {"image_url": f"http://127.0.0.1:{PORT}/cdn/{urllib.parse.quote(v)}"}}]}).encode())
        self.send(200, b'{"name":"Mock Account"}')


srv = HTTPServer(("127.0.0.1", 0), H); PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def run(cwd, env_extra=None):
    import os
    env = dict(os.environ, GRAPH_BASE_URL=f"http://127.0.0.1:{PORT}", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-W", "ignore", "run_all.py"], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8")


with tempfile.TemporaryDirectory() as d:
    work = Path(d) / "creative-report"
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns("input", "images", "output", "reference", ".git", "__pycache__", ".env", "dist", "tests"))
    (work / "input").mkdir()
    for f in (ROOT / "input").glob("*.csv"):
        shutil.copy(f, work / "input" / f.name)
    # 1) .env 없음 → 멈춤
    r = run(work); print(r.stdout[-400:]); assert r.returncode == 1 and ".env" in r.stdout
    # 2) 정상
    (work / ".env").write_text("META_ACCESS_TOKEN=SECRETTOKEN\nMETA_AD_ACCOUNT_ID_MY=111\nMETA_AD_ACCOUNT_ID_SG=222\nMETA_TOKEN_ISSUED=2026-10-15\n", encoding="utf-8")
    r = run(work)
    print(r.stdout[-900:]); print(r.stderr[-500:])
    assert r.returncode == 0, r.stdout
    outs = sorted(p.name for p in (work / "output").iterdir())
    print(outs)
    assert sum(n.endswith(".pptx") for n in outs) == 4 and sum(n.endswith(".html") for n in outs) == 4 and any(n.startswith("실행기록_") for n in outs)
    assert len(list((work / "images").iterdir())) == 38
    assert "SECRETTOKEN" not in r.stdout and "SECRETTOKEN" not in "".join(p.read_text(encoding="utf-8") for p in (work / "output").glob("실행기록_*.txt"))
    assert "이미지 없음" not in (work / "output" / "생성로그.txt").read_text(encoding="utf-8")
    # 3) 수동 교체본은 덮어쓰지 않음
    name = sorted((work / "images").iterdir())[0]
    (work / "images_manual").mkdir(); Image.new("RGB", (50, 50), "black").save(work / "images_manual" / name.name)
    before = (work / "images" / name.name).read_bytes()
    r = run(work); assert r.returncode == 0
    assert (work / "images" / name.name).read_bytes() == before, "수동 교체 소재는 자동 수집이 다시 받으면 안 됨"
    # 4) 지난달 CSV 가 섞이면 멈춤
    shutil.copy(next((work / "input").glob("*MY_OG*")), work / "input" / "8월 리포트 (07_20-08_23) - MY_OG&TEST.csv")
    r = run(work); assert r.returncode == 1 and "서로 다른" in r.stdout
    (work / "input" / "8월 리포트 (07_20-08_23) - MY_OG&TEST.csv").unlink()
    # 5) 토큰 만료 → 점검에서 멈춤
    STATE["expired"] = True
    r = run(work); print(r.stdout[-500:]); assert r.returncode == 1 and "토큰" in r.stdout
    # 6) 글자 깨진 CSV → 멈춤
    STATE["expired"] = False
    bad = next((work / "input").glob("*SG_PR*")); bad.write_bytes(bad.read_bytes()[:200] + b"\xff\xfe\x80" + bad.read_bytes()[200:])
    r = run(work); assert r.returncode == 1 and ("UTF-8" in r.stdout or "깨진" in r.stdout), r.stdout[-300:]
print("OK")
