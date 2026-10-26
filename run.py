"""EAST Creative Report 생성기.

사용법 (명령 한 줄):
    python run.py
input/ 의 국가 탭별 CSV 와 images/ 의 소재 이미지로 국가×유형(OG/PR)별 pptx 를 output/ 에 만든다.
옵션: --only MY_OG (한 벌만), --period 08/24-09/20 (파일명에 기간이 없을 때), --created 2026-10-14, --per-country (국가별 한 파일: OG+PR)
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from build import build_deck, build_decks  # noqa: E402
from html_out import write_html  # noqa: E402
from plan import plan_deck  # noqa: E402
from sheet import EncodingProblem, parse_blocks, read_csv  # noqa: E402

TAB = re.compile(r"(?P<cc>[A-Za-z]{2})_(?P<tab>OG&TEST|PR&BR)\.csv$", re.I)
PERIOD = re.compile(r"\((\d{2})_(\d{2})-(\d{2})_(\d{2})\)")


def find_inputs(folder, countries=None):
    """input 폴더의 국가 탭 CSV. countries(예: ["MY"])를 주면 그 국가만."""
    found = []
    want = {c.upper() for c in countries} if countries else None
    for p in sorted(Path(folder).glob("*.csv")):
        m = TAB.search(p.name)
        if m and (want is None or m.group("cc").upper() in want):
            found.append((m.group("cc").upper(), "OG" if m.group("tab").upper().startswith("OG") else "PR", p))
    return found


def report_year(end_m, end_d, today):
    y = today.year
    return y - 1 if date(y, end_m, end_d) > today else y


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=str(ROOT / "input"))
    ap.add_argument("--images", default=str(ROOT / "images"))
    ap.add_argument("--template", default=str(ROOT / "template" / "EAST_template.pptx"))
    ap.add_argument("--out", default=str(ROOT / "output"))
    ap.add_argument("--only", help="예: MY_OG")
    ap.add_argument("--countries", help="담당 국가만 (예: MY 또는 MY,SG). 비우면 CSV 가 있는 모든 국가")
    ap.add_argument("--period", help="데이터 기간 MM/DD-MM/DD (파일명에서 못 읽을 때)")
    ap.add_argument("--created", help="표지 작성일 YYYY-MM-DD (기본: 오늘)")
    ap.add_argument("--per-country", action="store_true", help="국가별 한 파일(OG 다음 PR)로 만든다")
    a = ap.parse_args(argv)

    countries = [c for c in (a.countries or "").replace(" ", "").split(",") if c]
    inputs = find_inputs(a.input, countries)
    if not inputs:
        print(f"[멈춤] {a.input} 에서 '국가_OG&TEST.csv' / '국가_PR&BR.csv' 형태의 CSV 를 찾지 못했습니다.")
        return 1

    # 1) 모든 CSV 를 먼저 읽어 글자 깨짐을 확인한다 (하나라도 깨졌으면 아무것도 만들지 않고 멈춤)
    tabs = {}
    bad = []
    for cc, kind, p in inputs:
        try:
            tabs[(cc, kind)] = parse_blocks(read_csv(p))
        except EncodingProblem as e:
            bad.append(str(e))
    if bad:
        print("\n".join(bad))
        return 2

    # 2) 기간·날짜
    m = None
    for _, _, p in inputs:
        m = PERIOD.search(p.name)
        if m:
            break
    if a.period:
        mm = re.fullmatch(r"(\d{2})/(\d{2})-(\d{2})/(\d{2})", a.period)
        if not mm:
            print("[멈춤] --period 형식은 08/24-09/20 입니다.")
            return 1
        period = tuple(int(x) for x in mm.groups())
    elif m:
        period = tuple(int(x) for x in m.groups())
    else:
        print("[멈춤] 파일명에서 데이터 기간 '(08_24-09_20)' 을 찾지 못했습니다. --period 08/24-09/20 으로 알려 주세요.")
        return 1
    created = date.fromisoformat(a.created) if a.created else date.today()
    year = report_year(period[2], period[3], created)
    meta = dict(yy=f"{year % 100:02d}", mm=period[2], created=created, period=period)

    # 3) 생성
    log, outs = [], []
    plans = []
    for (cc, kind), blocks in sorted(tabs.items()):
        if a.only and a.only.upper() != f"{cc}_{kind}":
            continue
        plan = plan_deck(cc, kind, blocks)
        if not plan.slides:
            log.append(f"[{cc} {kind}] 체크된 소재가 없어 건너뜀")
            continue
        plans.append(plan)
    groups = []
    if a.per_country:
        for plan in plans:   # sorted(tabs) 라 같은 국가는 OG → PR 순
            if groups and groups[-1][0].country == plan.country:
                groups[-1].append(plan)
            else:
                groups.append([plan])
    else:
        groups = [[p] for p in plans]
    for group in groups:
        cc = group[0].country
        suffix = cc if a.per_country else f"{cc}_{group[0].kind}"
        out = Path(a.out) / f"SKIN1004_{meta['yy']}-{period[2]:02d}_EAST_{suffix}.pptx"
        build_decks(group, a.template, meta, a.images, out, log_local := [])
        for plan in group:
            write_html(plan, meta, a.images, out.with_name(f"SKIN1004_{meta['yy']}-{period[2]:02d}_EAST_{plan.country}_{plan.kind}.html"))
        outs.append(out)
        n = 1 + 1 + sum(1 + len(p.slides) + (len(p.tables) + 1) // 2 for p in group) + 1
        log.append(f"[{' + '.join(f'{p.country} {p.kind}' for p in group)}] 슬라이드 {n}장 → {out.name} (+ .html)")
        for plan in group:
            log += [f"   경고: {w}" for w in plan.warnings] + [f"   참고: {i}" for i in plan.infos]
        log += [f"   {x}" for x in log_local]
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "생성로그.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    print(f"\n완료: {len(outs)}개 파일 → {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
