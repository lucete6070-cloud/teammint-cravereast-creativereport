"""서버 방식 전체 시험 (가짜 구글 + 가짜 Meta + 실제 브라우저 2~3명). 실행: python tests/test_server.py"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import mock_google  # noqa: E402
import mock_meta  # noqa: E402

meta = mock_meta.start()
google = mock_google.start(ROOT / "input")
gurl = f"http://127.0.0.1:{google.server_address[1]}"
shots = Path(os.environ.get("SHOTS", tempfile.mkdtemp())); shots.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as d:
    work = Path(d) / "app"; sess_root = Path(d) / "sessions"
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns("input", "images", "images_manual", "output", "reference", ".git", "__pycache__", ".env", "dist", "tests", "tools", "docs", "*.bat", "GUIDE.html"))  # .dockerignore 와 같은 제외 목록
    env = dict(os.environ, PYTHONIOENCODING="utf-8", APP_MODE="server", PUBLIC_URL="http://127.0.0.1:8793", PORT="8793",
               GOOGLE_CLIENT_ID="cid", GOOGLE_CLIENT_SECRET="csecret", ALLOWED_DOMAIN="team-mint.io",
               GOOGLE_AUTH_URL=gurl + "/auth", GOOGLE_TOKEN_URL=gurl + "/token", GOOGLE_USERINFO_URL=gurl + "/userinfo",
               GOOGLE_SHEETS_BASE=gurl + "/v4", APP_WORK_ROOT=str(sess_root),
               GRAPH_BASE_URL=f"http://127.0.0.1:{meta.server_address[1]}", META_ACCESS_TOKEN="SERVERTOKEN",
               META_AD_ACCOUNT_ID_MY="111", META_AD_ACCOUNT_ID_SG="222", META_TOKEN_ISSUED="2026-10-15")
    app = subprocess.Popen([sys.executable, "-W", "ignore", "app.py"], cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen("http://127.0.0.1:8793/healthz", timeout=1); break
            except Exception:
                time.sleep(.2)
        r = subprocess.run(["node", str(ROOT / "tests" / "ui_server.js"), "http://127.0.0.1:8793", gurl, str(shots)],
                           capture_output=True, text=True, env=dict(os.environ, NODE_PATH="/opt/node22/lib/node_modules"))
        print(r.stdout); print(r.stderr[-1000:])
        assert r.returncode == 0 and "FAIL" not in r.stdout, "서버 시험 실패"
        # 로그아웃한 A 의 작업 폴더는 지워지고, B 것만 남아야 한다 (CSV·이미지·결과는 서버에 남기지 않음)
        left = [p for p in (sess_root / "creative-report-sessions").iterdir()] if (sess_root / "creative-report-sessions").exists() else []
        print("남은 작업 폴더:", len(left)); assert len(left) == 1, left
        # 토큰이 어디에도 기록되지 않았는지
        blob = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in sess_root.rglob("*.txt"))
        assert "SERVERTOKEN" not in blob and "tok_" not in blob
        assert not (work / ".env").exists(), "서버 모드에서는 .env 를 만들지 않음"
    finally:
        app.terminate()
        print((app.stdout.read() if app.stdout else "")[-600:])
print("OK", shots)
