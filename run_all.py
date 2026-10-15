"""한 번에 실행 (보조용): 점검 → 이미지 수집 → pptx/HTML 생성. run_all.bat 더블클릭으로 실행한다.

기록은 output\\실행기록_날짜시간.txt 에 남는다.
"""
import argparse
import contextlib
import io
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import check  # noqa: E402
import fetch_images  # noqa: E402
import run as run_mod  # noqa: E402


class Tee(io.TextIOBase):
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
        return len(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def step(ko, vi):
    print(f"\n=== {ko} / {vi} ===")


def main(argv=None, client_factory=None, open_folder=True):
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fetch", action="store_true", help="이미지 수집을 건너뛰고 images 폴더의 이미지로만 만들기")
    ap.add_argument("--offline", action="store_true", help="Meta 연결 확인 생략")
    ap.add_argument("--countries", default="", help="담당 국가만 (예: MY 또는 MY,SG). 비우면 CSV 가 있는 모든 국가")
    a = ap.parse_args(argv)
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    log_path = out_dir / f"실행기록_{datetime.now():%Y%m%d_%H%M%S}.txt"
    with open(log_path, "w", encoding="utf-8") as logf, contextlib.redirect_stdout(Tee(sys.stdout, logf)):
        from version import VERSION
        print(f"시작 {datetime.now():%Y-%m-%d %H:%M:%S}  (프로그램 버전 {VERSION})")
        countries = [c for c in a.countries.replace(" ", "").split(",") if c]
        cargs = ["--countries", ",".join(countries)] if countries else []
        step("1/3 점검", "Bước 1/3 Kiểm tra")
        results = check.run_checks(online=not a.offline and not a.skip_fetch, client_factory=client_factory, countries=countries or None)
        if not check.show(results):
            print("\n[멈춤] 위 오류를 고친 뒤 다시 실행하세요. / [DỪNG] Hãy sửa các lỗi trên rồi chạy lại.")
            return 1
        warnings = []
        if not a.skip_fetch:
            step("2/3 이미지 수집 (Meta)", "Bước 2/3 Tải ảnh từ Meta")
            rc = fetch_images.main(["--force"] + cargs, client_factory=client_factory)
            if rc in (1, 2):
                print("\n[멈춤] 이미지를 받지 못했습니다. / [DỪNG] Không tải được ảnh.")
                return 1
            if rc == 3:
                warnings.append("일부 소재 이미지를 못 받았습니다 — 해당 자리는 회색 사각형으로 남습니다. 위 '실패' 목록을 지윤님께 알려 주세요. / "
                                "Một số ảnh không tải được — chỗ đó sẽ để ô xám. Hãy báo danh sách 'thất bại' ở trên.")
        step("3/3 pptx/HTML 만들기", "Bước 3/3 Tạo pptx/HTML")
        rc = run_mod.main(cargs)
        if rc != 0:
            print("\n[멈춤] 생성에 실패했습니다. / [DỪNG] Tạo file thất bại.")
            return 1
        gen_log = out_dir / "생성로그.txt"
        if gen_log.exists():
            miss = [l for l in gen_log.read_text(encoding="utf-8").splitlines() if "이미지 없음" in l]
            if miss:
                warnings.append(f"이미지가 없는 소재 {len(miss)}개 (output\\생성로그.txt 확인). / Có {len(miss)} ảnh còn thiếu (xem output\\생성로그.txt).")
        print("\n" + "=" * 60)
        if warnings:
            for w in warnings:
                print("[주의/LƯU Ý] " + w)
        print(f"완료! output 폴더에 pptx(편집용)와 html(보기용)이 만들어졌습니다.\nXong! Thư mục output có file pptx (để chỉnh sửa) và html (để xem).")
        print(f"기록: {log_path.name}")
    if open_folder and os.name == "nt":
        os.startfile(out_dir)  # noqa: S606  (탐색기로 output 폴더 열기)
    return 0


if __name__ == "__main__":
    sys.exit(main())
