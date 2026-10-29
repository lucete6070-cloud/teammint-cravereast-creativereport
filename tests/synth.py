"""테스트용 합성 시트 (광고주 데이터 아님). test_notes.py, test_skill_scripts.py 가 같이 쓴다."""
import csv
from pathlib import Path

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



def make_inputs(d, with_prev=True, with_hist=True):
    """d 아래 input/(이번 달), input/전월/, ref/소재이력_MY.md 를 만든다."""
    d = Path(d)
    write(d / "input" / "10월 리포트 (09_21-10_18) - MY_OG&TEST.csv", cur)
    if with_prev:
        write(d / "input" / "전월" / "9월 리포트 (08_24-09_20) - MY_OG&TEST.csv", prev)
    (d / "ref").mkdir(exist_ok=True)
    if with_hist:
        (d / "ref" / "소재이력_MY.md").write_text(HIST, encoding="utf-8")
