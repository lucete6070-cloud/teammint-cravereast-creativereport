"""웹 화면(로컬): 더블클릭(start_app.bat)하면 브라우저에 화면이 열린다.

CSV 올리기 → 담당 국가 고르기 → [생성하기] → 결과 내려받기. 점검·이미지 수집·생성 코드는 run_all.py 와 같은 것을 쓴다.
기본은 이 PC 안(127.0.0.1)에서만 접속된다. 서버로 올릴 때는 로그인 등 접근 제한을 따로 붙여야 한다 (지금은 PC 안에서만 쓰는 용도).
"""
import argparse
import contextlib
import io
import json
import re
import sys
import threading
import webbrowser
import zipfile
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import check  # noqa: E402
import run_all  # noqa: E402
from meta_api import load_env  # noqa: E402
from run import PERIOD, TAB, find_inputs  # noqa: E402
from sheet import EncodingProblem, read_csv  # noqa: E402
from version import VERSION, VERSION_DATE  # noqa: E402

MAX_UPLOAD = 20 * 1024 * 1024
COUNTRIES = ["MY", "SG", "ID", "PH"]
client_factory = None     # 테스트용: 가짜 Meta 서버 연결


def input_dir():
    return ROOT / "input"


def output_dir():
    return ROOT / "output"


def list_inputs():
    items = []
    for p in sorted(input_dir().glob("*.csv")):
        m = TAB.search(p.name)
        per = PERIOD.search(p.name)
        item = dict(name=p.name, size=p.stat().st_size, cc=m.group("cc").upper() if m else None,
                    kind=("OG" if m.group("tab").upper().startswith("OG") else "PR") if m else None,
                    period=("%s/%s ~ %s/%s" % per.groups()) if per else None, ok=True, error=None)
        if not m:
            item.update(ok=False, error="파일 이름 끝이 MY_OG&TEST.csv 형태가 아닙니다 / Tên file phải kết thúc dạng MY_OG&TEST.csv")
        else:
            try:
                read_csv(p)
            except EncodingProblem as e:
                item.update(ok=False, error=str(e))
        items.append(item)
    return items


def env_state():
    env = load_env(ROOT / ".env")
    return dict(has_env=(ROOT / ".env").is_file(), has_token=bool(env.get("META_ACCESS_TOKEN")),
                issued=env.get("META_TOKEN_ISSUED", ""),
                accounts={c: bool(env.get(f"META_AD_ACCOUNT_ID_{c}")) for c in COUNTRIES},
                shared_account=bool(env.get("META_AD_ACCOUNT_ID")))


def list_outputs():
    out = output_dir()
    if not out.exists():
        return []
    return [dict(name=p.name, size=p.stat().st_size) for p in sorted(out.iterdir())
            if p.is_file() and p.suffix.lower() in (".pptx", ".html", ".txt")]


def save_settings(data):
    """토큰·국가별 광고계정을 .env 에 저장 (다른 줄은 그대로). 토큰은 화면에 돌려주지 않는다."""
    updates = {}
    tok = (data.get("token") or "").strip()
    if tok:
        if re.search(r"\s", tok):
            raise ValueError("토큰에 띄어쓰기나 줄바꿈이 있습니다 / Token có khoảng trắng hoặc xuống dòng")
        updates["META_ACCESS_TOKEN"] = tok
        updates["META_TOKEN_ISSUED"] = date.today().isoformat()
    for cc, v in (data.get("accounts") or {}).items():
        v = (v or "").strip()
        if cc in COUNTRIES and v:
            if not re.fullmatch(r"(act_)?\d[\d,\s;]*", v):
                raise ValueError(f"{cc} 광고계정 ID 는 숫자여야 합니다 / ID tài khoản {cc} phải là số")
            updates[f"META_AD_ACCOUNT_ID_{cc}"] = v
    if not updates:
        return
    path = ROOT / ".env"
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.is_file() else \
        ((ROOT / ".env.example").read_text(encoding="utf-8").splitlines() if (ROOT / ".env.example").is_file() else [])
    done = set()
    for i, ln in enumerate(lines):
        k = ln.split("=", 1)[0].strip()
        if "=" in ln and not ln.lstrip().startswith("#") and k in updates:
            lines[i] = f"{k}={updates[k]}"
            done.add(k)
    lines += [f"{k}={v}" for k, v in updates.items() if k not in done]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class Job:
    """한 번에 하나만 실행한다 (같은 폴더를 쓰기 때문)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.state, self.rc, self.log, self.step = "idle", None, [], 0
        self.images = dict(done=0, total=0)

    def start(self, countries, skip_fetch):
        if not self.lock.acquire(blocking=False):
            return False
        self.reset()
        self.state = "running"
        threading.Thread(target=self._run, args=(countries, skip_fetch), daemon=True).start()
        return True

    def _feed(self, text):
        for ln in text.splitlines():
            self.log.append(ln)
            m = re.match(r"=== (\d)/3", ln)
            if m:
                self.step = int(m.group(1))
            m = re.search(r"이미지 필요 (\d+)개", ln)
            if m:
                self.images["total"] = int(m.group(1))
            if ln.lstrip().startswith(("받음", "실패:")):
                self.images["done"] += 1

    def _run(self, countries, skip_fetch):
        job = self

        class W(io.TextIOBase):
            buf = ""

            def write(self, s):
                self.buf += s
                while "\n" in self.buf:
                    ln, self.buf = self.buf.split("\n", 1)
                    job._feed(ln)
                return len(s)

        argv = (["--countries", ",".join(countries)] if countries else []) + (["--skip-fetch"] if skip_fetch else [])
        try:
            with contextlib.redirect_stdout(W()):
                self.rc = run_all.main(argv, client_factory=client_factory, open_folder=False)
        except Exception as e:  # noqa: BLE001  (화면에 이유를 보여 주려고 모두 잡는다)
            self.log.append(f"[오류/LỖI] {type(e).__name__}: {e}")
            self.rc = 1
        self.state = "done" if self.rc == 0 else "error"
        self.lock.release()

    def snapshot(self, tail=400):
        return dict(state=self.state, rc=self.rc, step=self.step, images=self.images, log=(self.log[-tail:] if tail else []),
                    outputs=list_outputs() if self.state in ("done", "error") else [])


JOB = Job()


class Handler(BaseHTTPRequestHandler):
    server_version = "CreativeReport"

    def log_message(self, *a):
        pass

    # ---- 보안: 이 PC 의 주소로만, 그리고 이 화면이 보낸 요청만
    def _guard(self, write=False):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            self._json(403, dict(error="forbidden host"))
            return False
        if write and self.headers.get("X-App") != "1":
            self._json(403, dict(error="forbidden"))
            return False
        return True

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD:
            raise ValueError("파일이 너무 큽니다 / File quá lớn")
        return self.rfile.read(n)

    def state(self):
        return dict(version=VERSION, version_date=VERSION_DATE, env=env_state(), inputs=list_inputs(),
                    outputs=list_outputs(), countries=COUNTRIES, job=JOB.snapshot(0))

    def do_GET(self):
        if not self._guard():
            return
        u = urlparse(self.path)
        if u.path == "/":
            html = (ROOT / "web" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        elif u.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        elif u.path == "/api/state":
            self._json(200, self.state())
        elif u.path == "/api/job":
            self._json(200, JOB.snapshot())
        elif u.path == "/download-all.zip":
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for f in list_outputs():
                    if f["name"].endswith((".pptx", ".html")):
                        z.write(output_dir() / f["name"], f["name"])
            data = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="creative-report.zip"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif u.path.startswith("/download/"):
            name = Path(unquote(u.path[len("/download/"):])).name     # 경로 이동 방지
            p = output_dir() / name
            if not p.is_file() or p.parent.resolve() != output_dir().resolve():
                self._json(404, dict(error="not found"))
                return
            data = p.read_bytes()
            ctype = {".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                     ".html": "text/html; charset=utf-8"}.get(p.suffix.lower(), "text/plain; charset=utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + __import__("urllib.parse").parse.quote(p.name))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self._json(404, dict(error="not found"))

    def do_POST(self):
        if not self._guard(write=True):
            return
        u = urlparse(self.path)
        try:
            if u.path == "/api/upload":
                name = Path(unquote(parse_qs(u.query).get("name", [""])[0])).name
                if not name.lower().endswith(".csv"):
                    return self._json(400, dict(error="CSV 파일만 올릴 수 있습니다 / Chỉ tải được file CSV"))
                if JOB.state == "running":
                    return self._json(409, dict(error="실행 중에는 파일을 바꿀 수 없습니다 / Đang chạy, không thể đổi file"))
                data = self._body()
                input_dir().mkdir(exist_ok=True)
                dest = input_dir() / name
                dest.write_bytes(data)
                try:
                    read_csv(dest)
                except EncodingProblem as e:
                    dest.unlink()
                    return self._json(400, dict(error=str(e)))
                return self._json(200, self.state())
            if u.path == "/api/inputs/clear":
                if JOB.state == "running":
                    return self._json(409, dict(error="실행 중입니다 / Đang chạy"))
                for p in input_dir().glob("*.csv"):
                    p.unlink()
                return self._json(200, self.state())
            if u.path == "/api/settings":
                save_settings(json.loads(self._body() or b"{}"))
                return self._json(200, self.state())
            if u.path == "/api/check":
                data = json.loads(self._body() or b"{}")
                res = check.run_checks(online=bool(data.get("online")), client_factory=client_factory,
                                       countries=data.get("countries") or None)
                return self._json(200, dict(results=[dict(level=a, ko=b, vi=c) for a, b, c in res],
                                            ok=not any(a == check.ERR for a, _, _ in res)))
            if u.path == "/api/run":
                data = json.loads(self._body() or b"{}")
                countries = [c for c in data.get("countries", []) if c in COUNTRIES]
                if not JOB.start(countries, bool(data.get("skip_fetch"))):
                    return self._json(409, dict(error="이미 실행 중입니다 / Đang chạy"))
                return self._json(200, dict(started=True))
            self._json(404, dict(error="not found"))
        except (ValueError, json.JSONDecodeError) as e:
            self._json(400, dict(error=str(e)))


def make_server(port=8765):
    for p in range(port, port + 20):
        try:
            return ThreadingHTTPServer(("127.0.0.1", p), Handler)
        except OSError:
            continue
    raise OSError("사용 가능한 포트를 찾지 못했습니다")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    srv = make_server(a.port)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"Creative Report 웹 화면 v{VERSION} — {url}\n이 창을 닫으면 화면도 종료됩니다. / Đóng cửa sổ này thì màn hình cũng tắt.")
    if not a.no_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
