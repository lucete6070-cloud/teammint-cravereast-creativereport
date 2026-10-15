"""웹 화면 전체 시험: 가짜 Meta 서버 + 앱 서버(격리 복사본) + 실제 브라우저 조작. 실행: python tests/test_app.py"""
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
import mock_meta  # noqa: E402

meta = mock_meta.start()
shots = Path(os.environ.get("SHOTS", tempfile.mkdtemp()))
shots.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as d:
    work = Path(d) / "creative-report"
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns("input", "images", "output", "reference", ".git", "__pycache__", ".env", "dist", "tests"))
    csvs = Path(d) / "csv"; csvs.mkdir()
    for f in (ROOT / "input").glob("*.csv"):
        shutil.copy(f, csvs / f.name)
    env = dict(os.environ, GRAPH_BASE_URL=f"http://127.0.0.1:{meta.server_address[1]}", PYTHONIOENCODING="utf-8")
    app = subprocess.Popen([sys.executable, "-W", "ignore", "app.py", "--no-browser", "--port", "8791"], cwd=work, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen("http://127.0.0.1:8791/api/state", timeout=1); break
            except Exception:
                time.sleep(.2)
        r = subprocess.run(["node", str(ROOT / "tests" / "ui_e2e.js"), "http://127.0.0.1:8791/", str(csvs), str(shots)],
                           capture_output=True, text=True, cwd="/opt/node22/lib/node_modules" if Path("/opt/node22/lib/node_modules").exists() else None,
                           env=dict(os.environ, NODE_PATH="/opt/node22/lib/node_modules"))
        print(r.stdout); print(r.stderr[-800:])
        assert r.returncode == 0 and "FAIL" not in r.stdout, "UI 시험 실패"
        env_text = (work / ".env").read_text(encoding="utf-8")
        assert "META_ACCESS_TOKEN=SECRETTOKEN123" in env_text and "META_AD_ACCOUNT_ID_MY=111" in env_text
        assert not any("SECRETTOKEN123" in p.read_text(encoding="utf-8") for p in (work / "output").glob("*.txt"))
    finally:
        app.terminate()
print("OK", shots)
