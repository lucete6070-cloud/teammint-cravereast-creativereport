"""구글 시트에서 국가 탭을 읽어 CSV 로 저장한다 (로그인한 사용자의 권한으로, 읽기 전용).

시트의 '표시된 값'(FORMATTED_VALUE)을 그대로 받으므로 CSV 다운로드와 같은 모양이다 (₩1,234 / 12.3% / TRUE / #N/A).
"""
import csv
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SHEETS_BASE = os.environ.get("GOOGLE_SHEETS_BASE", "https://sheets.googleapis.com/v4")
TAB = re.compile(r"^[A-Za-z]{2}_(OG&TEST|PR&BR)$")
ID_IN_URL = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")


class SheetError(Exception):
    """사용자에게 그대로 보여 줘도 되는 메시지."""


def parse_id(text):
    text = (text or "").strip()
    m = ID_IN_URL.search(text)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", text):
        return text
    raise SheetError("구글 시트 주소(https://docs.google.com/spreadsheets/d/...)를 붙여넣어 주세요 / Hãy dán địa chỉ Google Sheet")


def _get(token, url):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise SheetError("로그인이 만료됐습니다. 다시 로그인해 주세요 / Phiên đăng nhập đã hết hạn, hãy đăng nhập lại") from None
        if e.code in (403, 404):
            raise SheetError("이 시트를 볼 수 있는 권한이 없거나 주소가 틀렸습니다. 본인 계정으로 시트가 열리는지 확인하세요 / "
                             "Bạn không có quyền xem sheet này hoặc địa chỉ sai") from None
        raise SheetError(f"구글 시트를 읽지 못했습니다 ({e.code}) / Không đọc được Google Sheet ({e.code})") from None
    except urllib.error.URLError:
        raise SheetError("구글 시트에 연결하지 못했습니다 / Không kết nối được Google Sheet") from None


def csv_name(title, tab):
    """CSV 다운로드와 같은 이름: '제목 (08_24-09_20) - MY_OG&TEST.csv' (괄호 안의 / 는 _ 로)."""
    t = re.sub(r"\((\d{2})/(\d{2})-(\d{2})/(\d{2})\)", r"(\1_\2-\3_\4)", title)
    t = re.sub(r'[\\/:*?"<>|]', "_", t)
    return f"{t} - {tab}.csv"


def fetch_tabs(token, sheet_id, input_dir, base=None):
    """국가 탭들을 input_dir 에 CSV 로 저장. 기존 CSV 는 먼저 지운다(지난달 파일 혼입 방지). 반환: (제목, [파일이름])."""
    base = base or SHEETS_BASE
    meta = _get(token, f"{base}/spreadsheets/{sheet_id}?fields=properties.title,sheets.properties.title")
    title = meta.get("properties", {}).get("title", "sheet")
    tabs = [s["properties"]["title"] for s in meta.get("sheets", []) if TAB.match(s["properties"]["title"])]
    if not tabs:
        raise SheetError("이 시트에서 MY_OG&TEST, MY_PR&BR 같은 국가 탭을 찾지 못했습니다 / Không tìm thấy tab quốc gia như MY_OG&TEST")
    if not re.search(r"\(\d{2}/\d{2}-\d{2}/\d{2}\)", title):
        raise SheetError(f"시트 제목에 데이터 기간 '(08/24-09/20)' 이 없습니다: {title} / Tiêu đề sheet thiếu khoảng thời gian dữ liệu")
    Path(input_dir).mkdir(parents=True, exist_ok=True)
    for old in Path(input_dir).glob("*.csv"):
        old.unlink()
    files = []
    for tab in tabs:
        rng = urllib.parse.quote(f"'{tab}'", safe="")
        vals = _get(token, f"{base}/spreadsheets/{sheet_id}/values/{rng}?valueRenderOption=FORMATTED_VALUE&majorDimension=ROWS")
        name = csv_name(title, tab)
        with open(Path(input_dir) / name, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(vals.get("values", []))
        files.append(name)
    return title, files
