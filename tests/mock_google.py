"""테스트용 가짜 구글: 로그인(OAuth) + 사용자 정보 + 시트 API. 시트 내용은 input/ 의 9월 CSV 에서 만든다."""
import csv
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

TITLE = "9월 크리 리포트_RDPV (08/24-09/20)"
STATE = {"user": "nobody@team-mint.io"}


def start(csv_dir):
    tabs = {}
    for f in Path(csv_dir).glob("*.csv"):
        tab = f.stem.rsplit(" - ", 1)[1]
        tabs[tab] = [r for r in csv.reader(f.read_text(encoding="utf-8-sig").splitlines())]

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def send(self, code, obj, ctype="application/json"):
            body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
            if u.path == "/_set":
                STATE["user"] = q["email"][0]; return self.send(200, {"ok": True})
            if u.path == "/auth":     # 사용자가 로그인·동의했다고 보고 바로 돌려보냄
                loc = q["redirect_uri"][0] + "?" + urllib.parse.urlencode({"code": "code_" + STATE["user"], "state": q["state"][0]})
                self.send_response(302); self.send_header("Location", loc); self.end_headers(); return
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer tok_"):
                return self.send(401, {"error": "unauth"})
            if u.path == "/userinfo":
                return self.send(200, {"email": auth[len("Bearer tok_"):], "email_verified": True})
            m = urllib.parse.unquote(u.path)
            if m.startswith("/v4/spreadsheets/"):
                rest = m[len("/v4/spreadsheets/"):]
                sid, _, tail = rest.partition("/")
                if sid.startswith("noaccess"):
                    return self.send(403, {"error": "forbidden"})
                if not tail:
                    return self.send(200, {"properties": {"title": TITLE},
                                           "sheets": [{"properties": {"title": t}} for t in list(tabs) + ["메모"]]})
                tab = tail.split("/", 1)[1].strip("'")
                return self.send(200, {"values": tabs.get(tab, [])})
            self.send(404, {})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(n).decode())
            code = form.get("code", [""])[0]
            if code.startswith("code_") and form.get("client_secret", [""])[0] == "csecret":
                return self.send(200, {"access_token": "tok_" + code[5:]})
            self.send(400, {"error": "bad code"})

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
