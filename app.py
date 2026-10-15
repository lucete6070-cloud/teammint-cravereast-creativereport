"""웹 화면. 두 가지 방식으로 쓴다.

  로컬 (기본)   python app.py  또는 start_app.bat → 이 PC 안(127.0.0.1)에서만 접속. 로그인 없음. 토큰은 .env.
  서버          APP_MODE=server → 팀민트 구글 계정 로그인 필수, 사용자마다 작업 폴더 분리, 토큰은 서버 환경변수,
                구글 시트 주소로 국가 탭을 바로 읽기. 배포 방법은 docs/서버_배포.md.

화면(web/index.html)과 점검·이미지 수집·생성 코드(run_all.py)는 두 방식이 같다. 생성은 별도 프로세스로 돌려서 여러 명이 동시에 써도 섞이지 않는다.
"""
import argparse
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from datetime import date
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import check  # noqa: E402
from meta_api import load_env  # noqa: E402
from run import PERIOD, TAB  # noqa: E402
from sheet import EncodingProblem, read_csv  # noqa: E402
from sheets_source import SheetError, fetch_tabs, parse_id  # noqa: E402
from version import VERSION, VERSION_DATE  # noqa: E402

MAX_UPLOAD = 20 * 1024 * 1024
COUNTRIES = ["MY", "SG", "ID", "PH"]
SERVER = os.environ.get("APP_MODE", "local").lower() == "server"
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
ALLOWED_DOMAIN = os.environ.get("ALLOWED_DOMAIN", "team-mint.io").lower().lstrip("@")
SESSION_TTL = float(os.environ.get("SESSION_TTL_HOURS", "3")) * 3600
WORK_ROOT = Path(os.environ.get("APP_WORK_ROOT", "") or tempfile.gettempdir()) / "creative-report-sessions"
G_AUTH = os.environ.get("GOOGLE_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth")
G_TOKEN = os.environ.get("GOOGLE_TOKEN_URL", "https://oauth2.googleapis.com/token")
G_USERINFO = os.environ.get("GOOGLE_USERINFO_URL", "https://openidconnect.googleapis.com/v1/userinfo")
G_SCOPE = "openid email https://www.googleapis.com/auth/spreadsheets.readonly"
client_factory = None     # 테스트용


# ------------------------------------------------------------------ 작업(생성) 실행
class Job:
    """사용자마다 하나씩. 생성은 별도 프로세스(run_all.py)로 돌려서 서로 영향을 주지 않는다."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.state, self.rc, self.log, self.step = "idle", None, [], 0
        self.images = dict(done=0, total=0)

    def start(self, workdir, countries, skip_fetch):
        if not self.lock.acquire(blocking=False):
            return False
        self.reset()
        self.state = "running"
        args = [sys.executable, "-u", str(ROOT / "run_all.py"), "--no-open", "--workdir", str(workdir)]
        if countries:
            args += ["--countries", ",".join(countries)]
        if skip_fetch:
            args += ["--skip-fetch"]
        threading.Thread(target=self._run, args=(args,), daemon=True).start()
        return True

    def _feed(self, ln):
        ln = ln.rstrip("\r\n")
        self.log.append(ln)
        m = re.match(r"=== (\d)/3", ln)
        if m:
            self.step = int(m.group(1))
        m = re.search(r"이미지 필요 (\d+)개", ln)
        if m:
            self.images["total"] = int(m.group(1))
        if ln.lstrip().startswith(("받음", "실패:")):
            self.images["done"] += 1

    def _run(self, args):
        try:
            proc = subprocess.Popen(args, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            for ln in proc.stdout:
                self._feed(ln)
            self.rc = proc.wait()
        except Exception as e:  # noqa: BLE001
            self.log.append(f"[오류/LỖI] {type(e).__name__}: {e}")
            self.rc = 1
        self.state = "done" if self.rc == 0 else "error"
        self.lock.release()

    def snapshot(self, outputs, tail=400):
        return dict(state=self.state, rc=self.rc, step=self.step, images=self.images,
                    log=(self.log[-tail:] if tail else []), outputs=outputs if self.state in ("done", "error") else [])


# ------------------------------------------------------------------ 세션 (서버 모드는 사용자별, 로컬은 하나)
class Session:
    def __init__(self, email, token, workdir):
        self.id = secrets.token_urlsafe(32)
        self.email, self.token, self.workdir = email, token, Path(workdir)
        self.job = Job()
        self.last = time.time()
        for d in ("input", "images", "output"):
            (self.workdir / d).mkdir(parents=True, exist_ok=True)

    def inputs_dir(self): return self.workdir / "input"
    def output_dir(self): return self.workdir / "output"


SESSIONS = {}
PENDING = {}                  # OAuth state → 만든 시각
LOCAL = None if SERVER else Session("local", None, ROOT)
LOCK = threading.Lock()


def new_session(email, token):
    s = Session(email, token, WORK_ROOT / secrets.token_hex(8))
    with LOCK:
        SESSIONS[s.id] = s
    return s


def drop_session(s):
    with LOCK:
        SESSIONS.pop(s.id, None)
    if s.job.state != "running":
        shutil.rmtree(s.workdir, ignore_errors=True)       # 올린 CSV·받은 이미지·결과를 지운다


def reaper():
    while True:
        time.sleep(300)
        now = time.time()
        for s in list(SESSIONS.values()):
            if now - s.last > SESSION_TTL and s.job.state != "running":
                drop_session(s)
        for k, t in list(PENDING.items()):
            if now - t > 600:
                PENDING.pop(k, None)


def list_inputs(s):
    items = []
    for p in sorted(s.inputs_dir().glob("*.csv")):
        m, per = TAB.search(p.name), PERIOD.search(p.name)
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


def list_outputs(s):
    out = s.output_dir()
    if not out.exists():
        return []
    return [dict(name=p.name, size=p.stat().st_size) for p in sorted(out.iterdir())
            if p.is_file() and p.suffix.lower() in (".pptx", ".html", ".txt")]


def env_state():
    env = load_env(ROOT / ".env")
    return dict(has_env=(ROOT / ".env").is_file() or bool(env.get("META_ACCESS_TOKEN")), has_token=bool(env.get("META_ACCESS_TOKEN")),
                issued=env.get("META_TOKEN_ISSUED", ""),
                accounts={c: bool(env.get(f"META_AD_ACCOUNT_ID_{c}")) for c in COUNTRIES},
                shared_account=bool(env.get("META_AD_ACCOUNT_ID")))


def save_settings(data):
    """(로컬 전용) 토큰·국가별 광고계정을 .env 에 저장. 토큰은 화면에 돌려주지 않는다."""
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


# ------------------------------------------------------------------ HTTP
def allowed_hosts():
    hosts = {"127.0.0.1", "localhost"}
    if PUBLIC_URL:
        hosts.add(urllib.parse.urlparse(PUBLIC_URL).hostname)
    return hosts


class Handler(BaseHTTPRequestHandler):
    server_version = "CreativeReport"

    def log_message(self, *a):
        pass

    # ---- 공통
    def _json(self, code, obj, headers=()):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, url, headers=()):
        self.send_response(302)
        self.send_header("Location", url)
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD:
            raise ValueError("파일이 너무 큽니다 / File quá lớn")
        return self.rfile.read(n)

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in allowed_hosts()

    def _session(self):
        if not SERVER:
            return LOCAL
        c = SimpleCookie(self.headers.get("Cookie") or "")
        sid = c["sid"].value if "sid" in c else None
        s = SESSIONS.get(sid) if sid else None
        if s:
            s.last = time.time()
        return s

    def _guard(self, write=False, public=False):
        """반환: 세션(로컬은 항상 있음) 또는 None(이미 응답함)."""
        if not self._host_ok():
            self._json(403, dict(error="forbidden host"))
            return None
        if write and self.headers.get("X-App") != "1":
            self._json(403, dict(error="forbidden"))
            return None
        if public:
            return True
        s = self._session()
        if s is None:
            if self.command == "GET" and not self.path.startswith("/api/"):
                self._redirect("/login")
            else:
                self._json(401, dict(error="login required"))
            return None
        return s

    def state(self, s):
        return dict(version=VERSION, version_date=VERSION_DATE, mode="server" if SERVER else "local", user=s.email,
                    env=env_state(), inputs=list_inputs(s), outputs=list_outputs(s), countries=COUNTRIES,
                    job=s.job.snapshot([], 0))

    def _download(self, s, name):
        p = s.output_dir() / Path(name).name           # 경로 이동 방지
        if not p.is_file() or p.parent.resolve() != s.output_dir().resolve():
            return self._json(404, dict(error="not found"))
        data = p.read_bytes()
        ctype = {".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                 ".html": "text/html; charset=utf-8"}.get(p.suffix.lower(), "text/plain; charset=utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(p.name))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---- 구글 로그인
    def _login(self):
        if not SERVER:
            return self._redirect("/")
        cid = os.environ.get("GOOGLE_CLIENT_ID")
        if not (cid and PUBLIC_URL):
            return self._json(500, dict(error="서버 설정(GOOGLE_CLIENT_ID, PUBLIC_URL)이 필요합니다"))
        st = secrets.token_urlsafe(24)
        PENDING[st] = time.time()
        q = urllib.parse.urlencode(dict(client_id=cid, redirect_uri=PUBLIC_URL + "/oauth/callback", response_type="code",
                                        scope=G_SCOPE, state=st, hd=ALLOWED_DOMAIN, prompt="select_account", access_type="online"))
        self._redirect(f"{G_AUTH}?{q}")

    def _callback(self, q):
        st = (q.get("state") or [""])[0]
        if st not in PENDING:
            return self._page(400, "로그인 요청이 만료됐습니다. 다시 시도해 주세요 / Yêu cầu đăng nhập đã hết hạn")
        PENDING.pop(st, None)
        code = (q.get("code") or [""])[0]
        try:
            data = urllib.parse.urlencode(dict(code=code, client_id=os.environ["GOOGLE_CLIENT_ID"],
                                               client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                                               redirect_uri=PUBLIC_URL + "/oauth/callback", grant_type="authorization_code")).encode()
            with urllib.request.urlopen(urllib.request.Request(G_TOKEN, data=data), timeout=30) as r:
                tok = json.loads(r.read().decode())["access_token"]
            with urllib.request.urlopen(urllib.request.Request(G_USERINFO, headers={"Authorization": f"Bearer {tok}"}), timeout=30) as r:
                info = json.loads(r.read().decode())
        except Exception:  # noqa: BLE001
            return self._page(400, "구글 로그인에 실패했습니다. 다시 시도해 주세요 / Đăng nhập Google thất bại, hãy thử lại")
        email = (info.get("email") or "").lower()
        if not (info.get("email_verified") and email.endswith("@" + ALLOWED_DOMAIN)):
            return self._page(403, f"@{ALLOWED_DOMAIN} 계정만 사용할 수 있습니다 / Chỉ dùng được tài khoản @{ALLOWED_DOMAIN}")
        s = new_session(email, tok)
        secure = "; Secure" if PUBLIC_URL.startswith("https") else ""
        self._redirect("/", [("Set-Cookie", f"sid={s.id}; HttpOnly; SameSite=Lax; Path=/{secure}")])

    def _page(self, code, msg):
        body = (f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<body style="font:16px sans-serif;max-width:560px;margin:60px auto;padding:0 16px"><p>{msg}</p>'
                f'<p><a href="/login">다시 로그인 / Đăng nhập lại</a></p></body>').encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---- GET
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/healthz":
            return self._json(200, dict(ok=True))
        if u.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if u.path == "/login":
            return self._login() if self._guard(public=True) else None
        if u.path == "/oauth/callback":
            return self._callback(q) if self._guard(public=True) else None
        s = self._guard()
        if not s:
            return
        if u.path == "/":
            html = (ROOT / "web" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        elif u.path == "/api/state":
            self._json(200, self.state(s))
        elif u.path == "/api/job":
            self._json(200, s.job.snapshot(list_outputs(s)))
        elif u.path == "/download-all.zip":
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for f in list_outputs(s):
                    if f["name"].endswith((".pptx", ".html")):
                        z.write(s.output_dir() / f["name"], f["name"])
            data = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="creative-report.zip"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif u.path.startswith("/download/"):
            self._download(s, urllib.parse.unquote(u.path[len("/download/"):]))
        else:
            self._json(404, dict(error="not found"))

    # ---- POST
    def do_POST(self):
        s = self._guard(write=True)
        if not s:
            return
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path == "/api/upload":
                name = Path(urllib.parse.unquote(urllib.parse.parse_qs(u.query).get("name", [""])[0])).name
                if not name.lower().endswith(".csv"):
                    return self._json(400, dict(error="CSV 파일만 올릴 수 있습니다 / Chỉ tải được file CSV"))
                if s.job.state == "running":
                    return self._json(409, dict(error="실행 중에는 파일을 바꿀 수 없습니다 / Đang chạy, không thể đổi file"))
                data = self._body()
                dest = s.inputs_dir() / name
                dest.write_bytes(data)
                try:
                    read_csv(dest)
                except EncodingProblem as e:
                    dest.unlink()
                    return self._json(400, dict(error=str(e)))
                return self._json(200, self.state(s))
            if u.path == "/api/sheet":
                if not SERVER or not s.token:
                    return self._json(400, dict(error="구글 로그인이 필요한 기능입니다(서버 방식) / Cần đăng nhập Google (bản máy chủ)"))
                if s.job.state == "running":
                    return self._json(409, dict(error="실행 중입니다 / Đang chạy"))
                try:
                    title, files = fetch_tabs(s.token, parse_id(json.loads(self._body() or b"{}").get("url")), s.inputs_dir())
                except SheetError as e:
                    return self._json(400, dict(error=str(e)))
                st = self.state(s)
                st["sheet_title"] = title
                return self._json(200, st)
            if u.path == "/api/inputs/clear":
                if s.job.state == "running":
                    return self._json(409, dict(error="실행 중입니다 / Đang chạy"))
                for p in s.inputs_dir().glob("*.csv"):
                    p.unlink()
                return self._json(200, self.state(s))
            if u.path == "/api/settings":
                if SERVER:
                    return self._json(403, dict(error="서버에서는 관리자가 설정합니다 / Do quản trị viên cài đặt"))
                save_settings(json.loads(self._body() or b"{}"))
                return self._json(200, self.state(s))
            if u.path == "/api/check":
                data = json.loads(self._body() or b"{}")
                res = check.run_checks(online=bool(data.get("online")), client_factory=client_factory,
                                       countries=data.get("countries") or None, workdir=s.workdir)
                return self._json(200, dict(results=[dict(level=a, ko=b, vi=c) for a, b, c in res],
                                            ok=not any(a == check.ERR for a, _, _ in res)))
            if u.path == "/api/run":
                data = json.loads(self._body() or b"{}")
                countries = [c for c in data.get("countries", []) if c in COUNTRIES]
                if not s.job.start(s.workdir, countries, bool(data.get("skip_fetch"))):
                    return self._json(409, dict(error="이미 실행 중입니다 / Đang chạy"))
                return self._json(200, dict(started=True))
            if u.path == "/api/logout":
                if SERVER:
                    drop_session(s)
                return self._json(200, dict(ok=True), [("Set-Cookie", "sid=; Max-Age=0; Path=/")] if SERVER else ())
            self._json(404, dict(error="not found"))
        except (ValueError, json.JSONDecodeError) as e:
            self._json(400, dict(error=str(e)))


def make_server(host, port):
    for p in range(port, port + (20 if host == "127.0.0.1" else 1)):
        try:
            return ThreadingHTTPServer((host, p), Handler)
        except OSError:
            continue
    raise OSError("사용 가능한 포트를 찾지 못했습니다")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="0.0.0.0" if SERVER else "127.0.0.1")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    if SERVER and not (os.environ.get("GOOGLE_CLIENT_ID") and PUBLIC_URL):
        print("[멈춤] 서버 모드에는 GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, PUBLIC_URL 설정이 필요합니다 (docs/서버_배포.md).")
        return 1
    srv = make_server(a.host, a.port)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    if SERVER:
        threading.Thread(target=reaper, daemon=True).start()
        print(f"서버 모드 v{VERSION} — {PUBLIC_URL} (허용 도메인 @{ALLOWED_DOMAIN}, 포트 {srv.server_address[1]})", flush=True)
    else:
        print(f"Creative Report 웹 화면 v{VERSION} — {url}\n이 창을 닫으면 화면도 종료됩니다. / Đóng cửa sổ này thì màn hình cũng tắt.", flush=True)
        if not a.no_browser:
            threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
