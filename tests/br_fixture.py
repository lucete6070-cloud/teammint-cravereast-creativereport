"""BR 테스트용 가짜 PR&BR 탭 CSV 만들기 (광고주 데이터 없음 — 이름·숫자는 모두 지어낸 값).

시트 구조는 실제 `*_PR&BR` 탭과 같다: 왼쪽(B열~) PR 블록, 오른쪽(Q열~) BR 블록, P열 = 보조키.
- MY 형: 체크 열 '고효율 소재 / 저효율 소재' + 행 메모로 유입/구매 구분 (EAST-2)
- ID 형: 체크 열 '소진량 최상위 / 유입 고효율 소재' (EAST-1)
"""
import csv
from pathlib import Path

NCOL = 32
PR_HEAD = ["지출금액", "CPM", "CTR", "CPC", "CVR(구매)", "CPA(구매)", "매출액", "AOV", "ROAS"]
BR_HEAD = ["지출금액", "CPM", "CTR", "CPC", "VTR", "CPV", "장바구니담기", "구매", "ROAS"]


def _grid(n):
    return [[""] * NCOL for _ in range(n)]


def _block(g, r0, st, detail, campaign, head, flags, rows):
    """r0 행부터 블록 하나를 쓴다. rows = [(소재명, [지표...], hi, lo, 메모)]. 다음 블록 시작 행을 돌려준다."""
    g[r0][st] = "캠페인디테일"
    g[r0][st + 1] = detail
    g[r0 + 1][st] = "캠페인명"
    g[r0 + 1][st + 1] = campaign
    g[r0 + 1][st + 11] = "* PPT 삽입 기준"
    g[r0 + 2][st] = "TOP 10"
    for k, h in enumerate(head + list(flags)):
        g[r0 + 2][st + 1 + k] = h
    for j, (name, vals, hi, lo, memo) in enumerate(rows):
        r = g[r0 + 3 + j]
        r[st - 1] = detail + name
        r[st] = name
        for k, v in enumerate(vals):
            r[st + 1 + k] = v
        r[st + 1 + len(head)] = "TRUE" if hi else "FALSE"
        r[st + 2 + len(head)] = "TRUE" if lo else "FALSE"
        r[st + 3 + len(head)] = memo
    return r0 + 3 + len(rows) + 3


def _br_rows(cc, n, lang, length, checks):
    rows = []
    for i in range(n):
        spend = 1_670_896 - i * 137_011
        name = f"VID_OG_UIN_TNB_MIX_Influencer_Partnership_tester{i + 1}_1080x1920_{length}_{lang}"
        vals = [f"₩{spend:,}", f"₩{1400 + i * 10:,}", f"{2.81 + i * 0.3:.2f}%", f"₩{50 - i}", f"{89.91 - i:.2f}%",
                "₩2", f"{1673 - i * 100:,}", f"{248 - i * 20}", f"{527 - i * 30}%"]
        hi, lo, memo = checks.get(i, (False, False, ""))
        rows.append((name, vals, hi, lo, memo))
    return rows


def _pr_rows(n):
    rows = []
    for i in range(n):
        name = f"COL-IMG_PR_UIN_ALL_MASK_Product_Discount_Sample{i + 1}_1080x1080_MS"
        vals = [f"₩{900_000 - i * 50_000:,}", "₩1,200", "1.50%", "₩80", f"{6.0 - i * 0.2:.2f}%", "₩9,000", "₩4,000,000", "₩30,000",
                f"{500 - i * 20}%"]
        rows.append((name, vals, i == 0, i == n - 1, ""))
    return rows


def write_my(path):
    """MY 형: 메모로 유입 우수 / 유입 저조 / 유입&구매 우수 / 구매 저조 4블록 + #N/A 블록."""
    g = _grid(60)
    g[2][16] = "MY_BR"
    g[3][16] = "[Click 최적화]"
    _block(g, 5, 1, "Payday", "EAST_MY_Meta_Purchase_PR_CPAS-Shopee_Payday_260901_260930", PR_HEAD,
           ("고효율 소재", "저효율 소재"), _pr_rows(4))
    checks = {0: (True, False, "유입 & 구매 우수"), 1: (True, False, "> 유입 우수"), 2: (False, True, "> 유입 저조"),
              4: (False, True, ">ROAS 저조")}
    r = _block(g, 5, 16, "Partnership-Boosting", "EAST_MY_Meta_Traffic_Click_BR_CPAS-Shopee_Partnership-Boosting_260406_NONE",
               BR_HEAD, ("고효율 소재", "저효율 소재"), _br_rows("MY", 10, "MS", "34s", checks))
    g[r][16], g[r][17] = "캠페인디테일", "Partnership"
    g[r + 1][16], g[r + 1][17] = "캠페인명", "#N/A"
    g[r + 2][16] = "TOP 10"
    for k, h in enumerate(BR_HEAD + ["고효율 소재", "저효율 소재"]):
        g[r + 2][17 + k] = h
    g[r + 3][16] = "#N/A"
    _save(g, path)


def write_id(path):
    """ID 형: 소진량 최상위 2 + 유입 고효율 2 (Partnership-Routine)."""
    g = _grid(40)
    g[2][16] = "ID_BR"
    checks = {0: (True, False, ""), 1: (True, False, ""), 2: (False, True, ""), 3: (False, True, "")}
    _block(g, 5, 16, "Partnership-Routine", "EAST_ID_Meta_Traffic_Click_BR_CPAS-Shopee_Partnership-Routine_260723_NONE",
           BR_HEAD, ("소진량 최상위", "유입 고효율 소재"), _br_rows("ID", 10, "ID", "2m49s", checks))
    _save(g, path)


def _save(g, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(g)


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "input_test")
    write_my(out / "10월 리포트 (09_21-10_18) - MY_PR&BR.csv")
    write_id(out / "10월 리포트 (09_21-10_18) - ID_PR&BR.csv")
    print("만들었습니다:", out)
