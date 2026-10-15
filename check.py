"""실행 전 점검 (한국어 / Tiếng Việt). 문제가 있으면 무엇을 고치면 되는지 알려 준다.

    python check.py            # 파일·설정 점검
    python check.py --online   # + Meta 토큰·광고계정이 살아 있는지 확인
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from meta_api import DEFAULT_VERSION, MetaClient, MetaError, load_env  # noqa: E402
from run import PERIOD, find_inputs  # noqa: E402
from sheet import EncodingProblem, read_csv  # noqa: E402

OK, WARN, ERR = "OK", "주의", "오류"
VI = {OK: "OK", WARN: "LƯU Ý", ERR: "LỖI"}
TOKEN_MAX_DAYS = 50    # 장기 토큰은 약 60일 [추정] — 50일이 지나면 갱신 안내


def line(level, ko, vi):
    return (level, ko, vi)


def run_checks(root=ROOT, online=False, client_factory=None, today=None, countries=None):
    """[(수준, 한국어, 베트남어)] 목록. 수준이 '오류'인 항목이 하나라도 있으면 실행하면 안 된다."""
    root = Path(root)
    today = today or date.today()
    out = []
    # --- 부품
    try:
        import pptx, PIL, lxml  # noqa: F401
        out.append(line(OK, "필요한 부품(python-pptx, Pillow)이 설치돼 있습니다.", "Đã cài các thư viện cần thiết (python-pptx, Pillow)."))
    except ImportError as e:
        out.append(line(ERR, f"부품이 없습니다({e.name}). setup.bat 을 먼저 실행하세요.",
                        f"Thiếu thư viện ({e.name}). Hãy chạy setup.bat trước."))
    # --- 양식
    if (root / "template" / "EAST_template.pptx").is_file():
        out.append(line(OK, "양식(template)이 있습니다.", "Có file mẫu (template)."))
    else:
        out.append(line(ERR, "template\\EAST_template.pptx 가 없습니다. 프로그램 폴더를 다시 받아 주세요.",
                        "Không có template\\EAST_template.pptx. Hãy tải lại thư mục chương trình."))
    # --- CSV
    inputs = find_inputs(root / "input", countries)
    if not inputs:
        out.append(line(ERR, "input 폴더에 CSV 가 없습니다. 시트 국가 탭을 CSV 로 내려받아 넣어 주세요 (파일 이름 끝: MY_OG&TEST.csv 형태).",
                        "Thư mục input chưa có file CSV. Hãy tải các tab quốc gia từ Google Sheet dạng CSV và bỏ vào (tên file kết thúc như MY_OG&TEST.csv)."))
    periods, countries = set(), set()
    for cc, kind, p in inputs:
        countries.add(cc)
        try:
            read_csv(p)
        except EncodingProblem as e:
            out.append(line(ERR, str(e), f"File {p.name} bị lỗi font/mã hóa. Hãy tải lại CSV từ Google Sheet (File > Download > CSV)."))
            continue
        m = PERIOD.search(p.name)
        if m:
            periods.add(m.groups())
        else:
            out.append(line(ERR, f"'{p.name}' 파일 이름에 데이터 기간 '(08_24-09_20)' 이 없습니다.",
                            f"Tên file '{p.name}' không có khoảng thời gian dữ liệu như '(08_24-09_20)'."))
    if inputs and len(periods) > 1:
        out.append(line(ERR, "input 폴더에 데이터 기간이 서로 다른 CSV 가 섞여 있습니다 (지난달 파일이 남아 있나요?). 이번 달 파일만 남겨 주세요.",
                        "Thư mục input có CSV của các kỳ khác nhau (còn file tháng trước?). Chỉ giữ file của tháng này."))
    elif periods:
        sm, sd, em, ed = next(iter(periods))
        out.append(line(OK, f"CSV {len(inputs)}개, 데이터 기간 {sm}/{sd} ~ {em}/{ed}", f"{len(inputs)} file CSV, kỳ dữ liệu {sm}/{sd} ~ {em}/{ed}"))
    # --- .env
    env = load_env(root / ".env")
    if not (root / ".env").is_file():
        out.append(line(ERR, ".env 파일이 없습니다. setup.bat 을 실행하거나 .env.example 을 .env 로 복사해 토큰을 채워 주세요.",
                        "Chưa có file .env. Chạy setup.bat hoặc sao chép .env.example thành .env rồi điền token."))
    else:
        if not env.get("META_ACCESS_TOKEN"):
            out.append(line(ERR, ".env 에 META_ACCESS_TOKEN 이 비어 있습니다.", "META_ACCESS_TOKEN trong .env đang trống."))
        for cc in sorted(countries):
            if not (env.get(f"META_AD_ACCOUNT_ID_{cc}") or env.get("META_AD_ACCOUNT_ID")):
                out.append(line(ERR, f".env 에 {cc} 광고계정(META_AD_ACCOUNT_ID_{cc})이 없습니다.",
                                f".env chưa có tài khoản quảng cáo của {cc} (META_AD_ACCOUNT_ID_{cc})."))
        issued = env.get("META_TOKEN_ISSUED", "").strip()
        if issued:
            try:
                age = (today - date.fromisoformat(issued)).days
                if age > TOKEN_MAX_DAYS:
                    out.append(line(WARN, f"토큰을 발급한 지 {age}일이 지났습니다. 곧 만료되니 지윤님께 새 토큰을 요청하세요.",
                                    f"Token đã phát hành {age} ngày, sắp hết hạn. Hãy xin token mới."))
            except ValueError:
                out.append(line(WARN, "META_TOKEN_ISSUED 날짜 형식은 2026-10-15 입니다.", "META_TOKEN_ISSUED phải có dạng 2026-10-15."))
    # --- 온라인 (토큰·계정 확인)
    has_token = (root / ".env").is_file() and env.get("META_ACCESS_TOKEN")
    if online and has_token and countries:
        for cc in sorted(countries):
            ids = env.get(f"META_AD_ACCOUNT_ID_{cc}") or env.get("META_AD_ACCOUNT_ID")
            if not ids:
                continue
            try:
                client = client_factory(cc) if client_factory else MetaClient(
                    env.get("META_ACCESS_TOKEN"), ids, version=env.get("META_GRAPH_VERSION", DEFAULT_VERSION), base=env.get("GRAPH_BASE_URL"))
                name = client.ping()
                out.append(line(OK, f"{cc} 광고계정 연결 확인: {name}", f"Kết nối tài khoản quảng cáo {cc} thành công: {name}"))
            except MetaError as e:
                s = str(e)
                if "190" in s or "OAuth" in s or "expired" in s:
                    out.append(line(ERR, f"{cc}: 토큰이 만료됐거나 잘못됐습니다. 지윤님께 새 토큰을 요청해 .env 에 넣어 주세요.",
                                    f"{cc}: Token hết hạn hoặc sai. Hãy xin token mới và dán vào .env."))
                elif "403" in s or "(#200)" in s or "permission" in s:
                    out.append(line(ERR, f"{cc}: 이 토큰에 광고계정 접근 권한이 없습니다. 광고계정 ID 와 토큰 권한(ads_read)을 확인하세요.",
                                    f"{cc}: Token không có quyền truy cập tài khoản. Kiểm tra ID tài khoản và quyền ads_read."))
                else:
                    out.append(line(ERR, f"{cc}: Meta 연결 실패 — {s[:160]}", f"{cc}: Kết nối Meta thất bại — {s[:160]}"))
    return out


def show(results):
    for level, ko, vi in results:
        print(f"[{level}] {ko}\n[{VI[level]}] {vi}")
    return not any(l == ERR for l, _, _ in results)


def main(argv=None, client_factory=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--online", action="store_true")
    a = ap.parse_args(argv)
    ok = show(run_checks(online=a.online, client_factory=client_factory))
    print("\n점검 결과: " + ("문제 없음" if ok else "고쳐야 할 오류가 있습니다") + " / " + ("Kết quả: không có vấn đề" if ok else "Có lỗi cần sửa"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
