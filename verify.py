"""생성한 pptx 를 reference/ 의 FN(정답지)과 대조한다: KPI · 소재명 · 캠페인명(카드 라벨) · TOP10 표 값 · 표지(월·기간).

사용법:  python verify.py            (output/ 의 pptx 전부를 reference/ FN 과 비교)
         python verify.py --fn reference/xxx.pptx
불일치 목록을 화면에 출력하고 output/대조결과.md 에도 저장한다.
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from pptx import Presentation  # noqa: E402
from pptx_read import deck_slides, norm, slide_items  # noqa: E402


def group_cards(path):
    """{(국가, 유형): {'cards': [...], 'tables': [...]}} — 레이아웃 이름 '{국가} - {OG|PR}' 기준."""
    out = defaultdict(lambda: dict(cards=[], tables=[]))
    for d in deck_slides(path):
        m = re.fullmatch(r"([A-Z]{2}) - (OG|PR)", d["layout"])
        if not m:
            continue
        key = m.groups()
        for c in d["cards"]:
            if "소진량" in c["kpi"]:
                continue
            out[key]["cards"].append(dict(label=c["label"], kpi=c["kpi"], name=c["name"], slide=d["n"]))
        for t in d["tables"]:
            out[key]["tables"].append(dict(title=t["title"], cells=t["cells"], slide=d["n"]))
    return out


def cover_info(path):
    d = Presentation(str(path)).slides[0]
    txt = " ".join(i["text"] for i in slide_items(d))
    month = re.search(r"EAST\s*(\d{2})\s*월", txt)
    period = re.search(r"데이터 기준\s*:\s*(\d{2}/\d{2})\s*-\s*(\d{2}/\d{2})", txt)
    return (month.group(1) if month else None, f"{period.group(1)} - {period.group(2)}" if period else None)


def compare_cards(gen, fn):
    """(일치수, 불일치 줄 목록). 소재명 기준으로 짝지어 KPI·라벨을 비교한다."""
    G = [dict(c, key=norm(c["name"]).casefold(), kp=norm(c["kpi"]), lb=norm(c["label"])) for c in gen]
    F = [dict(c, key=norm(c["name"]).casefold(), kp=norm(c["kpi"]), lb=norm(c["label"])) for c in fn]
    ok, issues = 0, []
    # 1) 소재명 + KPI + 라벨 모두 같은 것
    for g in list(G):
        for f in F:
            if g["key"] == f["key"] and g["kp"] == f["kp"] and g["lb"] == f["lb"]:
                ok += 1
                G.remove(g); F.remove(f)
                break
    # 2) 소재명 + KPI 가 같고 라벨만 다른 것
    for g in list(G):
        for f in F:
            if g["key"] == f["key"] and g["kp"] == f["kp"]:
                issues.append(f"캠페인명(라벨) 불일치 | {g['name'][:60]}… | 생성 '{g['label']}' ≠ FN '{f['label']}' (FN {f['slide']}p)")
                G.remove(g); F.remove(f)
                break
    # 3) 소재명이 같고 라벨이 같은데 KPI 가 다른 것 → KPI 불일치
    for g in list(G):
        for f in F:
            if g["key"] == f["key"] and g["lb"] == f["lb"]:
                issues.append(f"KPI 불일치 | {g['label']} | {g['name'][:50]}… | 생성 '{' '.join(g['kpi'].split())}' ≠ FN '{' '.join(f['kpi'].split())}' (FN {f['slide']}p)")
                G.remove(g); F.remove(f)
                break
    # 4) 소재명 다르지만 KPI 숫자열이 같은 것 → 소재명 불일치
    for g in list(G):
        for f in F:
            if g["kp"] == f["kp"] and g["lb"] == f["lb"]:
                issues.append(f"소재명 불일치 | {g['label']} | 생성 '{g['name']}' ≠ FN '{f['name']}'")
                G.remove(g); F.remove(f)
                break
    for g in G:
        issues.append(f"FN 에 없음(생성물에만) | {g['label']} | {g['name'][:60]}… | {' '.join(g['kpi'].split())}")
    for f in F:
        issues.append(f"생성물에 없음(FN 에만) | {f['label']} | {f['name'][:60]}… | {' '.join(f['kpi'].split())} (FN {f['slide']}p)")
    return ok, issues


def _cell_norm(s):
    # FN 표 머리글은 '(장바구니 담기)' 를 '(장바구니)' 로 줄여 쓴다 — 같은 뜻으로 본다
    return norm(s).replace("(장바구니담기)", "(장바구니)")


def compare_tables(gen, fn):
    ok_cells, issues, matched = 0, [], 0
    used = set()
    for g in gen:
        gnames = {norm(r[0]).casefold() for r in g["cells"][1:]}
        best, score = None, 0
        for i, f in enumerate(fn):
            if i in used:
                continue
            fnames = {norm(r[0]).casefold() for r in f["cells"][1:]}
            sc = len(gnames & fnames)
            if sc > score:
                best, score = i, sc
        label = re.sub(r"[▼\s]", "", g["title"])
        if best is None or score == 0:
            issues.append(f"표 FN 에 대응 없음 | {g['title']} ({len(g['cells']) - 1}행)")
            continue
        used.add(best)
        f = fn[best]
        matched += 1
        if len(g["cells"]) != len(f["cells"]):
            issues.append(f"표 행 수 다름 | {g['title']} | 생성 {len(g['cells']) - 1}행 / FN {len(f['cells']) - 1}행 (FN {f['slide']}p)")
        fmap = {norm(r[0]).casefold(): r for r in f["cells"]}
        for r in g["cells"]:
            fr = fmap.get(norm(r[0]).casefold())
            if fr is None:
                issues.append(f"표 행 FN 에 없음 | {g['title']} | {r[0][:50]}…")
                continue
            for c, (a, b) in enumerate(zip(r, fr)):
                if _cell_norm(a) == _cell_norm(b):
                    ok_cells += 1
                else:
                    head = g["cells"][0][c] if c < len(g["cells"][0]) else c
                    issues.append(f"표 값 불일치 | {g['title']} | {r[0][:40]}… | {head}: 생성 '{a}' ≠ FN '{b}' (FN {f['slide']}p)")
        # 표 제목(라벨)
        if norm(g["title"]).replace("TOP", "") != norm(f["title"]).replace("TOP", ""):
            issues.append(f"표 제목 다름(참고) | 생성 '{g['title']}' / FN '{f['title']}'")
    for i, f in enumerate(fn):
        if i not in used:
            issues.append(f"표 생성물에 없음(FN 에만) | {f['title']} (FN {f['slide']}p)")
    return ok_cells, issues


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fn", default=str(next((ROOT / "reference").glob("*FN*.pptx"), "")))
    ap.add_argument("--out", default=str(ROOT / "output"))
    a = ap.parse_args(argv)
    if not Path(a.fn).is_file():
        print("[멈춤] reference/ 에서 FN pptx 를 찾지 못했습니다.")
        return 1
    fn = group_cards(a.fn)
    fn_month, fn_period = cover_info(a.fn)
    lines, total_issues = [], 0
    tot = dict(cards=0, card_ok=0, cells=0, cell_ok=0)
    lines.append(f"# 생성물 ↔ FN 대조 결과\n\n정답지: {Path(a.fn).name}  (표지: {fn_month}월 / {fn_period})\n")
    for p in sorted(Path(a.out).glob("*.pptx")):
        m = re.search(r"_([A-Z]{2})_(OG|PR)\.pptx$", p.name)
        if not m:
            continue
        key = m.groups()
        gen = group_cards(p)[key]
        ref = fn.get(key, dict(cards=[], tables=[]))
        ok, ci = compare_cards(gen["cards"], ref["cards"])
        cell_ok, ti = compare_tables(gen["tables"], ref["tables"])
        month, period = cover_info(p)
        cov = [] if (month, period) == (fn_month, fn_period) else [f"표지 불일치 | 생성 {month}월/{period} ≠ FN {fn_month}월/{fn_period}"]
        issues = cov + ci + ti
        total_cards = len(gen["cards"])
        ncells = sum(len(t["cells"]) * len(t["cells"][0]) for t in gen["tables"])
        tot["cards"] += total_cards; tot["card_ok"] += ok; tot["cells"] += ncells; tot["cell_ok"] += cell_ok
        total_issues += len(issues)
        lines.append(f"## {key[0]} {key[1]}  ({p.name})")
        lines.append(f"- 카드(KPI·소재명·캠페인명): 생성 {total_cards}장 중 FN 과 완전 일치 {ok}장 (FN {len(ref['cards'])}장)")
        lines.append(f"- TOP10 표: 생성 {len(gen['tables'])}개, 셀 {ncells}칸 중 일치 {cell_ok}칸 (FN {len(ref['tables'])}개)")
        lines.append(f"- 표지(월·데이터 기간): {'일치' if not cov else '불일치'}  (작성일은 비교 제외)")
        lines.append(f"- 불일치 {len(issues)}건" + ("" if not issues else ":"))
        lines += [f"  - {x}" for x in issues]
        lines.append("")
    lines.insert(2, f"**전체: 카드 {tot['card_ok']}/{tot['cards']} 일치, 표 셀 {tot['cell_ok']}/{tot['cells']} 일치, 불일치 목록 {total_issues}건**\n")
    text = "\n".join(lines)
    print(text)
    Path(a.out).mkdir(exist_ok=True)
    (Path(a.out) / "대조결과.md").write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
