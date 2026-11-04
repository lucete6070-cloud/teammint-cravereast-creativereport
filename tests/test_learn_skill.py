"""월간 학습 스킬 스크립트(추출 점검·월간 파일·판정결과/변경내역 갱신)를 가짜 데이터로 돌려 본다. 실행: python tests/test_learn_skill.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
K = ROOT / "skills" / "craver-creative-report-learn" / "scripts"

FN_TEXT = """SKIN1004 EAST 11월 Creative Report 데이터 기준 : 10/26 – 11/22
MY 상시캠페인유입효율 우수소재<> 저조소재
우수 소재는 할인율을 첫 화면에 크게 둔 양상
반면 저조 소재는 설명 요소 비중이 높았던 것으로 판단
▶ 첫 화면은 가격 중심으로 단순화 제언
지출 ₩100,000 / 장바구니 CPA ₩200 / ROAS 900%
COL-IMG_OG_UIN_TEST_A_Product_Discount_1_1080x1080_NONE_EN
지출 ₩50,000 / 장바구니 CPA ₩400 / ROAS 300%
COL-IMG\\_OG\\_UIN\\_TEST\\_B\\_Product
\\_Review\\_1\\_1080x1080\\_NONE\\_EN
"""

EXTRACTED = {
    "month": "26-11", "period": "26/10/26 - 26/11/22", "written": "2026-12-03", "sources": ["가짜 FN.pdf"],
    "slides": [{"country": "MY", "kind": "OG", "funnel": "유입", "title": "MY 상시 캠페인 유입 효율 우수 소재 <> 저조 소재",
                "comment": ["우수 소재는 할인율을 첫 화면에 크게 둔 양상", "반면 저조 소재는 설명 요소 비중이 높았던 것으로 판단"],
                "arrow": "▶ 첫 화면은 가격 중심으로 단순화 제언", "callouts": ["할인 혜택 부재"],
                "slots": [{"label": "ATC", "cls": "우수 (장바구니)", "name": "COL-IMG_OG_UIN_TEST_A_Product_Discount_1_1080x1080_NONE_EN",
                           "kpi": "지출 ₩100,000 / 장바구니 CPA ₩200 / ROAS 900%", "gist": "할인율 전면"},
                          {"label": "ATC", "cls": "저조 (장바구니)", "name": "COL-IMG_OG_UIN_TEST_B_Product_Review_1_1080x1080_NONE_EN",
                           "kpi": "지출 ₩50,000 / 장바구니 CPA ₩400 / ROAS 300%", "gist": "리뷰 설명 점유"}]}],
    "continuity": [{"item": "MY TEST_A", "fn": "전월에 이어 우수"}]}

OLD_JUDG = """# 판정 결과
- 1차 작성: 2026-10-29 / 2차 갱신: 2026-11-04
- 우선순위: 이 파일 우선. 같은 ID가 이 파일 안에 두 번 있으면 **아래쪽(최신 갱신)** 을 따른다.

## 0. 공통 규칙 갱신
| 주제 | 규칙 |
|---|---|
| 피로도 | 가능성 허용 |

## 1. 26년 10월 FN 반영 판정
| # | 대상 |
|---|---|
| O-10 | 예전 판정 |

## 3. 1차 판정
| J-01 | 아주 예전 |
"""

OLD_LOG = """# 변경 내역
| 날짜 | 반영 월 | 파일 | 변경 | 실행 | 판정 |
|---|---|---|---|---|---|
| 2026-11-04 | 26년 10월 | 판정결과.md | 10월 반영 | Claude | 지윤님 |

## 파일 버전 관리
- 설명
"""


def run(*args, ok=True):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    if ok and r.returncode != 0:
        raise AssertionError(r.stdout + r.stderr)
    return r


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "fn.txt").write_text(FN_TEXT, encoding="utf-8")
        ex = td / "extracted.json"

        # 1) 원문 대조: 맞으면 통과 (원문의 줄바꿈·공백·역슬래시 차이는 무시)
        ex.write_text(json.dumps(EXTRACTED, ensure_ascii=False), encoding="utf-8")
        r = run(K / "check_extract.py", ex, td / "fn.txt")
        assert "추출 점검 통과" in r.stdout, r.stdout

        # 2) 원문과 다른 KPI·소재명·분류는 걸린다
        bad = json.loads(json.dumps(EXTRACTED))
        bad["slides"][0]["slots"][0]["kpi"] = "지출 ₩100,001 / 장바구니 CPA ₩200 / ROAS 900%"
        bad["slides"][0]["slots"][1]["name"] = "COL-IMG_없는_소재"
        bad["slides"][0]["slots"][1]["cls"] = "보통"
        ex.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        r = run(K / "check_extract.py", ex, td / "fn.txt", ok=False)
        assert r.returncode == 1 and "₩100,001" in r.stdout and "없는_소재" in r.stdout and "cls" in r.stdout, r.stdout

        # 3) 월간 파일 2개
        ex.write_text(json.dumps(EXTRACTED, ensure_ascii=False), encoding="utf-8")
        run(K / "make_files.py", ex, td / "out")
        hist = (td / "out" / "소재이력_26-11.md").read_text(encoding="utf-8")
        assert "| COL-IMG_OG_UIN_TEST_A_Product_Discount_1_1080x1080_NONE_EN | 26-11 | OG | 유입 | ATC | 우수 (장바구니) | 할인율 전면 |" in hist, hist
        assert "SG·ID·PH: 이번 달 FN 에 본문 없음" in hist and "전월에 이어 우수" in hist
        fnc = (td / "out" / "FN코멘트_26-11.md").read_text(encoding="utf-8")
        assert "## MY OG — MY 상시" in fnc and "- ▶ 첫 화면은 가격 중심으로 단순화 제언" in fnc and "콜아웃: 할인 혜택 부재" in fnc, fnc

        # 4) 판정결과: 다음 번호, 새 절은 0장 아래·기존 판정 위, 우선순위 문구 교체, 기존 내용 유지
        (td / "old_j.md").write_text(OLD_JUDG, encoding="utf-8")
        assert run(K / "update_judgments.py", "next-id", td / "old_j.md").stdout.strip() == "O-11"
        (td / "sec.md").write_text("## 26년 11월 FN 반영 판정 (2026-12-03)\n| # | 대상 |\n|---|---|\n| O-11 | 새 판정 |\n", encoding="utf-8")
        run(K / "update_judgments.py", "judgments", td / "old_j.md", td / "sec.md", td / "new_j.md", "2026-12-03 (11월 FN 반영 1건)")
        nj = (td / "new_j.md").read_text(encoding="utf-8")
        assert nj.index("## 0.") < nj.index("## 26년 11월") < nj.index("## 1. 26년 10월") < nj.index("## 3. 1차"), nj
        assert "갱신: 2026-12-03 (11월 FN 반영 1건)" in nj and "날짜가 최신인 절" in nj and "아래쪽(최신 갱신)" not in nj
        assert "O-10 | 예전 판정" in nj and "J-01 | 아주 예전" in nj

        # 5) 변경내역: 표 끝에 행 추가, 표 아래 설명은 그대로
        (td / "old_l.md").write_text(OLD_LOG, encoding="utf-8")
        (td / "rows.md").write_text("| 2026-12-03 | 26년 11월 | 소재이력_26-11.md | 신규 | Claude | 사실 기록 |\n", encoding="utf-8")
        run(K / "update_judgments.py", "changelog", td / "old_l.md", td / "rows.md", td / "new_l.md")
        nl = (td / "new_l.md").read_text(encoding="utf-8")
        assert nl.index("2026-11-04") < nl.index("2026-12-03") < nl.index("## 파일 버전 관리"), nl
    print("월간 학습 스킬 테스트 통과")


if __name__ == "__main__":
    main()
