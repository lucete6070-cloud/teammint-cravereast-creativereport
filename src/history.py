"""전월 우수·저조 기록 찾기 (코멘트 근거용). 숫자 계산은 하지 않고 체크박스·이력 표의 구분만 읽는다.

출처 두 가지 (둘 다 없어도 생성은 계속한다):
1. 전월 시트 CSV: input/전월/ 에 지난달 국가 탭 CSV (예: MY_OG&TEST.csv). 고효율/저효율 체크박스를 읽는다.
2. 소재이력 파일: reference/ 아래 소재이력_{국가}.md (드라이브 '코멘트 참고 파일'에서 받은 것).
   표 형식: | 소재명 | 월(YY-MM) | 유형 | 퍼널 | 캠페인 라벨 | 구분 | 코멘트 요지 |
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from sheet import EncodingProblem, parse_blocks, read_csv

MONTH = re.compile(r"^\d{2}-\d{2}$")
LABEL = {"hi": "우수", "lo": "저조", "run": "집행(체크 없음)"}


def prev_month(yy, mm):
    """('26', 9) -> '26-08'"""
    y, m = int(yy), int(mm) - 1
    if m == 0:
        y, m = y - 1, 12
    return f"{y % 100:02d}-{m:02d}"


def _cls_of(text):
    t = text.strip()
    if t.startswith("우수"):
        return "hi"
    if t.startswith("저조"):
        return "lo"
    if t.startswith("혼합"):
        return "mix"
    return ""


@dataclass
class History:
    prev_csv: dict = field(default_factory=dict)    # (cc, kind) -> {소재명 casefold: 'hi'|'lo'|'run'}
    prev_csv_files: list = field(default_factory=list)
    records: dict = field(default_factory=dict)     # cc -> {소재명 casefold: [(YY-MM, 퍼널, 라벨, cls)]}
    history_files: list = field(default_factory=list)
    problems: list = field(default_factory=list)


def load_prev_csv(folder, find_inputs):
    """input/전월/ 의 CSV. 글자 깨짐은 멈추지 않고 problems 에 남긴다."""
    h = {}
    files, problems = [], []
    folder = Path(folder)
    if not folder.is_dir():
        return h, files, problems
    for cc, kind, p in find_inputs(folder):
        try:
            blocks = parse_blocks(read_csv(p))
        except EncodingProblem as e:
            problems.append(f"전월 시트를 읽지 못해 건너뜀: {e}")
            continue
        m = h.setdefault((cc, kind), {})
        for b in blocks:
            for r in b.rows:
                k = r.name.casefold()
                cls = "hi" if r.hi else "lo" if r.lo else "run"
                if m.get(k) in ("hi", "lo") and cls == "run":
                    continue   # 다른 블록에서 이미 체크된 것을 덮지 않는다
                m[k] = cls
        files.append(p.name)
    return h, files, problems


def load_history_files(folder):
    """reference/ 아래 소재이력_{CC}.md 를 모두 읽는다."""
    recs, files = {}, []
    folder = Path(folder)
    if not folder.is_dir():
        return recs, files
    for p in sorted(folder.rglob("소재이력_*.md")):
        cc = p.stem.split("_", 1)[1].upper()[:2]
        m = recs.setdefault(cc, {})
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 6 or not MONTH.match(cells[1]):
                continue
            name = cells[0].strip("` ")
            m.setdefault(name.casefold(), []).append((cells[1], cells[3], cells[4], _cls_of(cells[5])))
        files.append(p.name)
    return recs, files


def load(prev_folder, history_folder, find_inputs):
    h = History()
    h.prev_csv, h.prev_csv_files, h.problems = load_prev_csv(prev_folder, find_inputs)
    h.records, h.history_files = load_history_files(history_folder)
    return h


def status(h, cc, kind, funnel, name, report_yymm, cur_cls=""):
    """한 슬롯의 전월 기록 문장. report_yymm = 리포트 월 'YY-MM', cur_cls = 이번 달 구분('hi'|'lo'|'mix')."""
    yy, mm = report_yymm.split("-")
    pm = prev_month(yy, mm)
    key = name.casefold()
    parts = []
    by_month = {}
    for mon, fun, label, cls in h.records.get(cc, {}).get(key, []):
        if cls and (not funnel or not fun or funnel in fun):
            by_month.setdefault(mon, set()).add(cls)
    prev_cls = None
    src = ""
    csv_map = h.prev_csv.get((cc, kind))
    if csv_map is not None:
        prev_cls = csv_map.get(key)
        src = "전월 시트"
        if prev_cls is None:
            parts.append(f"{pm} 전월 시트에 없음 (신규 또는 미집행)")
    if prev_cls is None and pm in by_month and len(by_month[pm]) == 1:
        prev_cls = next(iter(by_month[pm]))
        src = "소재이력"
    if prev_cls in ("hi", "lo", "run", "mix"):
        parts.append(f"{pm} {LABEL.get(prev_cls, '혼합')} ({src})")
        if prev_cls in ("hi", "lo"):
            n, y, m = 1, *map(int, pm.split("-"))
            while True:
                cur = prev_month(f"{y:02d}", m)
                y, m = map(int, cur.split("-"))
                if by_month.get(cur) == {prev_cls}:
                    n += 1
                else:
                    break
            if cur_cls == prev_cls:
                parts.append(f"→ 이번 달 포함 {n + 1}개월 연속 {LABEL[prev_cls]}" + (" (소재이력 기준)" if n >= 2 else ""))
            elif cur_cls in ("hi", "lo"):
                parts.append(f"→ 이번 달 {LABEL[cur_cls]}로 전환" + (f" (직전 {n}개월 연속 {LABEL[prev_cls]})" if n >= 2 else ""))
    elif csv_map is None and not h.records.get(cc):
        parts.append("전월 자료 없음 (전월 시트·소재이력 파일 모두 없음)")
    elif csv_map is None:
        parts.append(f"{pm} 기록 없음 (소재이력 기준)")
    older = sorted((mon for mon in by_month if mon < pm), reverse=True)[:3]
    if older:
        parts.append("이전 이력: " + ", ".join(f"{mon} {'/'.join(LABEL.get(c, '혼합') for c in sorted(by_month[mon]))}" for mon in older))
    return " ".join(parts)
