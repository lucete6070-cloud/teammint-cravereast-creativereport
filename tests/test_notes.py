"""코멘트 근거 노트 테스트 (합성 데이터, 광고주 데이터 없음). 실행: python tests/test_notes.py

이번 달 MY OG 시트 + 전월 시트 + 소재이력 파일로 생성기를 돌리고, 콘텐츠 슬라이드 노트에
슬롯·시트 지표(문자열 그대로)·전월 기록·2개월 연속 표시가 들어가는지, 코멘트 박스는 비어 있는지 본다.
"""
import csv
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import run  # noqa: E402
from pptx import Presentation  # noqa: E402

ATC = ["지출금액", "CPM", "CTR", "CPC", "CVR(장바구니 담기)", "CPA(장바구니 담기)", "CVR(구매)", "CPA(구매)", "ROAS"]
PUR = ["지출금액", "CPM", "CTR", "CPC", "CVR(구매)", "CPA(구매)", "매출액", "AOV", "ROAS"]


def tab(left, right):
    """left/right = (detail, campaign, headers, [(name, [values], hi, lo, memo)])"""
    rows = [[""] * 32 for _ in range(16)]
    for (detail, camp, hdr, data), st in ((left, 1), (right, 16)):
        rows[0][st + 1] = detail
        rows[1][st + 1] = camp
        rows[2][st] = "TOP 10"
        for k, h in enumerate(hdr + ["고효율 소재", "저효율 소재"]):
            rows[2][st + 1 + k] = h
        for j, (name, vals, hi, lo, memo) in enumerate(data):
            r = rows[3 + j]
            r[st - 1] = detail + name
            r[st] = name
            for k, v in enumerate(vals):
                r[st + 1 + k] = v
            r[st + 1 + len(hdr)] = "TRUE" if hi else "FALSE"
            r[st + 2 + len(hdr)] = "TRUE" if lo else "FALSE"
            r[st + 3 + len(hdr)] = memo
    return rows


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)


A1, A2, A3 = "COL-IMG_OG_UIN_ALL_MASK_Product_Discount_1_1080x1080_NONE_EN", "COL-IMG_OG_UIN_TNB_AMPOULE_Product_Function_1_1080x1080_NONE_EN", "COL-VID_OG_UIN_CNT_CREAM_Influencer_BnA_1_1080x1080_15s_EN"
P1, P2, P3 = "COL-IMG_OG_UIN_POR_SUNSCREEN_Product_Function_2_1080x1080_NONE_EN", "COL-IMG_OG_UIN_TTC_PEELING-GEL_Product_NewArrival_1_1080x1080_NONE_EN", "COL-IMG_DailyPromotion-Oct_MIX_MIX_MIX_Calendar_DailyDeal_1_1080x1080_NONE_EN"
av = lambda s, roas: [s, "₩2,342", "0.55%", "₩426", "61.2%", "₩247", "6.92%", "₩6,157", roas]
pv = lambda s, roas: [s, "₩2,342", "0.55%", "₩426", "6.92%", "₩6,157", "₩25,720,793", "₩31,951", roas]

cur = tab(("ATC", "COL_MY_ATC_261020_261116", ATC, [(A1, av("₩910,734", "1225%"), True, False, "> 유입 효율 우수"), (A2, av("₩890,996", "312%"), False, True, "> 유입 효율 저조"), (A3, av("₩386,425", "349%"), False, True, "> 유입 효율 저조")]),
          ("PUR-CVN", "COL_MY_PUR_261020_261116", PUR, [(P1, pv("₩4,956,628", "519%"), True, False, ""), (P3, pv("₩177,878", "1813%"), True, False, ""), (P2, pv("₩2,247,365", "141%"), False, True, "")]))
prev = tab(("ATC", "COL_MY_ATC_260922_261019", ATC, [(A1, av("₩1", "900%"), True, False, ""), (A2, av("₩1", "200%"), False, True, ""), (A3, av("₩1", "500%"), False, False, "")]),
           ("PUR-CVN", "COL_MY_PUR_260922_261019", PUR, [(P1, pv("₩1", "500%"), True, False, ""), (P2, pv("₩1", "100%"), False, True, "")]))
HIST = f"""# 소재 이력 — MY

| 소재명 | 월 | 유형 | 퍼널 | 캠페인 라벨 | 구분(우수/저조/혼합) | 코멘트 요지 |
|---|---|---|---|---|---|---|
| {A2} | 26-09 | OG | 유입 | ATC | 저조 | 효능 설명 비중 |
| {A2} | 26-08 | OG | 유입 | ATC | 저조 [추정] | 효능 설명 비중 |
| {P1} | 26-09 | OG | 구매 | PUR-CVN | 우수 | 대표 SKU |
| {P2} | 26-09 | OG | 구매 | PUR-CVN | 저조 | 신제품 |
"""

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    write(d / "input" / "10월 리포트 (09_21-10_18) - MY_OG&TEST.csv", cur)
    write(d / "input" / "전월" / "9월 리포트 (08_24-09_20) - MY_OG&TEST.csv", prev)
    (d / "ref").mkdir()
    (d / "ref" / "소재이력_MY.md").write_text(HIST, encoding="utf-8")
    rc = run.main(["--input", str(d / "input"), "--images", str(d / "images"), "--out", str(d / "out"),
                   "--history", str(d / "ref"), "--created", "2026-10-25"])
    assert rc == 0
    log = (d / "out" / "생성로그.txt").read_text(encoding="utf-8")
    print(log)
    assert "전월 비교 자료 = 전월 시트 CSV + 소재이력_MY.md" in log
    prs = Presentation(str(d / "out" / "SKIN1004_26-10_EAST_MY_OG.pptx"))
    notes = [s.notes_slide.notes_text_frame.text for s in prs.slides if s.has_notes_slide]
    notes = [n for n in notes if n.startswith("=== 코멘트 근거")]
    assert len(notes) == 3, len(notes)   # 유입 통합 1 + 구매 우수 1 + 구매 저조 1
    atc = next(n for n in notes if "유입" in n.splitlines()[2])
    print(atc)
    assert "MY 상시(OG) 유입 / 우수<>저조" in atc
    assert "지출금액 ₩910,734" in atc and "ROAS 1225%" in atc          # 시트 문자열 그대로
    assert f"[슬롯 2] 저조 | ATC | {A2}" in atc
    assert "26-09 저조 (전월 시트) → 이번 달 포함 3개월 연속 저조 (소재이력 기준)" in atc   # 10월+9월(전월 시트)+8월(이력)
    assert "26-09 우수 (전월 시트) → 이번 달 포함 2개월 연속 우수" in atc
    assert "26-09 집행(체크 없음) (전월 시트)" in atc                       # A3: 전월 체크 없음
    pur_lo = next(n for n in notes if "구매 / 저조" in n)
    assert "26-09 저조 (전월 시트) → 이번 달 포함 2개월 연속 저조" in pur_lo
    pur_hi = next(n for n in notes if "구매 / 우수" in n)
    assert "26-09 전월 시트에 없음" in pur_hi                                 # P3 신규
    assert "=== 코멘트 스킬 메모" in atc
    # 코멘트 박스(서브헤더 자리)는 여전히 비어 있다
    for s in prs.slides:
        for sh in s.shapes:
            if sh.has_text_frame:
                assert not sh.text_frame.text.startswith("서브헤더는")

    # 소재이력만 있을 때 (보조가 전월 시트를 안 넣은 경우)
    rc = run.main(["--input", str(d / "input"), "--images", str(d / "images"), "--out", str(d / "out3"),
                   "--prev", str(d / "none"), "--history", str(d / "ref"), "--created", "2026-10-25"])
    assert rc == 0
    prs = Presentation(str(d / "out3" / "SKIN1004_26-10_EAST_MY_OG.pptx"))
    t = "\n".join(s.notes_slide.notes_text_frame.text for s in prs.slides if s.has_notes_slide)
    assert "전월 비교 자료: 소재이력_MY.md" in t
    assert "26-09 저조 (소재이력) → 이번 달 포함 3개월 연속 저조 (소재이력 기준)" in t
    assert "26-09 기록 없음 (소재이력 기준)" in t            # 이력에 없는 A1

    # 전월 자료가 하나도 없으면 '없음'으로 적고 생성은 계속
    rc = run.main(["--input", str(d / "input"), "--images", str(d / "images"), "--out", str(d / "out2"),
                   "--prev", str(d / "none"), "--history", str(d / "none"), "--created", "2026-10-25"])
    assert rc == 0
    prs = Presentation(str(d / "out2" / "SKIN1004_26-10_EAST_MY_OG.pptx"))
    n0 = next(t for t in (s.notes_slide.notes_text_frame.text for s in prs.slides if s.has_notes_slide) if t.startswith("=== 코멘트 근거"))
    assert "전월 비교 자료: 없음" in n0 and "전월 자료 없음" in n0
print("OK")
