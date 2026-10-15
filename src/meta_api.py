"""Meta Marketing API(Graph)에서 광고 이름으로 소재 이미지를 찾아 내려받는다.

- 토큰·계정 ID 는 .env 에서만 읽는다 (코드·로그·화면에 출력하지 않는다).
- 광고관리자 광고명 = 소재명 + 시작/종료일자 → 광고명 "포함" 검색 [추정: SPEC 4장].
- 이미지 우선순위: creative.image_url → (영상) 영상 썸네일 중 가장 큰 것/preferred → creative.thumbnail_url.
- Graph 버전·필드 이름은 공식 문서 기준 [추정]; 실제 계정 연동 전에는 [미확인].
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_VERSION = "v21.0"
BASE = "https://graph.facebook.com"
STATUSES = ["ACTIVE", "PAUSED", "ARCHIVED", "CAMPAIGN_PAUSED", "ADSET_PAUSED", "PENDING_REVIEW",
            "DISAPPROVED", "WITH_ISSUES", "IN_PROCESS"]


class MetaError(Exception):
    pass


def load_env(path):
    """.env 의 KEY=VALUE 를 읽는다 (따옴표·주석 허용). 이미 있는 환경변수가 우선."""
    env = {}
    p = Path(path)
    if p.is_file():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith("META_") or k == "GRAPH_BASE_URL"})
    return env


class MetaClient:
    def __init__(self, token, account_id, version=DEFAULT_VERSION, base=None, sleep=time.sleep):
        """account_id: 광고계정 ID 하나, 또는 쉼표/공백으로 구분한 여러 개 (모든 계정에서 검색)."""
        ids = [x for x in re.split(r"[,\s;]+", account_id or "") if x]
        if not token or not ids:
            raise MetaError("META_ACCESS_TOKEN / META_AD_ACCOUNT_ID 가 필요합니다 (.env.example 참고).")
        self._token = token
        self.accounts = [i if i.startswith("act_") else f"act_{i}" for i in ids]
        self.account = self.accounts[0]
        self.root = f"{(base or BASE).rstrip('/')}/{version}"
        self._sleep = sleep

    def _get(self, url, params=None, binary=False):
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._token}"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                return data if binary else json.loads(data.decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                code = None
                try:
                    code = json.loads(body).get("error", {}).get("code")
                except ValueError:
                    pass
                if (e.code in (429, 500, 502, 503) or code in (4, 17, 32, 613)) and attempt < 3:
                    self._sleep(2 ** (attempt + 1))   # 2·4·8초 후 재시도
                    continue
                msg = self._scrub(body)[:300]
                raise MetaError(f"Meta API 오류 {e.code}: {msg}") from None
            except urllib.error.URLError as e:
                if attempt < 3:
                    self._sleep(2 ** (attempt + 1))
                    continue
                raise MetaError(f"Meta API 연결 실패: {e.reason}") from None

    def _scrub(self, text):
        return text.replace(self._token, "***")

    def find_ads(self, name, limit=25):
        """광고명에 name 이 포함된 광고들 (creative 이미지 필드 포함)."""
        fields = ("name,effective_status,"
                  "creative.thumbnail_width(1080).thumbnail_height(1080){image_url,thumbnail_url,video_id}")
        params = {"fields": fields, "limit": limit,
                  "filtering": json.dumps([{"field": "name", "operator": "CONTAIN", "value": name}]),
                  "effective_status": json.dumps(STATUSES)}
        ads, errors = [], []
        for acc in self.accounts:   # 계정이 여러 개면 모두 검색해서 합친다
            try:
                ads += self._get(f"{self.root}/{acc}/ads", params).get("data", [])
            except MetaError as e:
                errors.append(f"{acc}: {e}")
        if errors and not ads and len(errors) == len(self.accounts):
            raise MetaError(" / ".join(errors))   # 모든 계정이 오류일 때만 오류로 본다
        return ads

    def ping(self):
        """첫 광고계정을 조회해 토큰·권한이 살아 있는지 확인한다. 성공하면 계정 이름을 돌려준다."""
        return self._get(f"{self.root}/{self.accounts[0]}", {"fields": "name"}).get("name", "")

    def candidates(self, name, limit=25):
        """진단용: 계정별로 광고명에 name 이 포함된 광고 목록. [(계정, 광고들, 오류메시지)]"""
        fields = ("name,effective_status,"
                  "creative.thumbnail_width(1080).thumbnail_height(1080){image_url,thumbnail_url,video_id}")
        params = {"fields": fields, "limit": limit,
                  "filtering": json.dumps([{"field": "name", "operator": "CONTAIN", "value": name}]),
                  "effective_status": json.dumps(STATUSES)}
        out = []
        for acc in self.accounts:
            try:
                out.append((acc, self._get(f"{self.root}/{acc}/ads", params).get("data", []), None))
            except MetaError as e:
                out.append((acc, [], str(e)))
        return out

    def video_thumbnail(self, video_id):
        data = self._get(f"{self.root}/{video_id}/thumbnails", {"fields": "uri,is_preferred,width,height"}).get("data", [])
        if not data:
            return None
        pref = [d for d in data if d.get("is_preferred")]
        best = pref[0] if pref else max(data, key=lambda d: (d.get("width") or 0) * (d.get("height") or 0))
        return best.get("uri")

    def image_url_for(self, ad):
        cr = ad.get("creative") or {}
        if cr.get("image_url"):
            return cr["image_url"], "image_url"
        if cr.get("video_id"):
            try:
                u = self.video_thumbnail(cr["video_id"])
                if u:
                    return u, "video_thumbnail"
            except MetaError:
                pass
        if cr.get("thumbnail_url"):
            return cr["thumbnail_url"], "thumbnail_url"
        return None, None

    def download(self, url):
        # 이미지 CDN 주소는 토큰 없이도 열린다 — 토큰을 외부 도메인에 보내지 않도록 별도 요청
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read(), r.headers.get("Content-Type", "")


AD_DATES = re.compile(r"_(\d{6})_(\d{6}|NONE)$")


def _ymd(s):
    from datetime import date
    return date(2000 + int(s[:2]), int(s[2:4]), int(s[4:6]))


def ad_dates(ad_name):
    """광고명 끝의 _시작일_종료일(또는 NONE) → (시작, 종료 또는 None). 없으면 None."""
    m = AD_DATES.search(ad_name or "")
    if not m:
        return None
    try:
        return _ymd(m.group(1)), (None if m.group(2) == "NONE" else _ymd(m.group(2)))
    except ValueError:
        return None


def overlaps(ad_name, period):
    """광고 집행 기간이 보고서 기간(period=(시작, 끝) date)과 겹치는가. 날짜가 없으면 None(모름)."""
    d = ad_dates(ad_name)
    if d is None or period is None:
        return None
    start, end = d
    return start <= period[1] and (end is None or end >= period[0])


def pick_ad(ads, name, period=None):
    """소재명에 가장 잘 맞는 광고.
    우선순위: 광고명이 소재명으로 시작 > 보고서 기간과 집행 기간이 겹침 > 켜져 있음(ACTIVE) > 이미지 있음 > 시작일이 늦음."""
    def score(a):
        n = a.get("name", "")
        d = ad_dates(n)
        return (n.casefold().startswith(name.casefold()), overlaps(n, period) is True,
                a.get("effective_status") == "ACTIVE", bool((a.get("creative") or {}).get("image_url")),
                d[0].toordinal() if d else 0)
    return max(ads, key=score) if ads else None


def ext_for(content_type, data):
    if "png" in content_type or data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    return ".jpg"


def safe_name(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name)
