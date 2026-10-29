"""시트 블록 → 슬라이드 계획. 체크박스 TRUE 행만 쓰고, 숫자는 시트 문자열 그대로."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config" / "labels.json"
STD_ATC_MEMO = re.compile(r"^>\s*유입\s*효율\s*(우수|저조)\s*$")


@dataclass
class Slot:
    label: str
    kpi: list           # KPI 문자열 줄 (1줄 또는 2줄 버전은 build 에서 결정)
    name: str
    cls: str            # 'hi' | 'lo' | 'mix'
    detail: str = ""
    side: str = ""
    cells: list = field(default_factory=list)   # [(지표 헤더, 시트 문자열)] — 노트용, 시트 열 순서
    memo: str = ""      # 시트 메모 열
    prev: str = ""      # 전월 기록 문장 (history.status)


@dataclass
class ContentSlide:
    title: str
    slots: list
    n_hi: int = 0       # 우수·저조 통합(분할 배경) 슬라이드일 때만 사용
    n_lo: int = 0
    split: bool = False
    group_labels: tuple = ()


@dataclass
class TableSpec:
    label: str
    headers: list
    rows: list          # [(name, [값...], 'hi'|'lo'|'')]


@dataclass
class DeckPlan:
    country: str
    kind: str           # 'OG' | 'PR'
    slides: list = field(default_factory=list)
    tables: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    infos: list = field(default_factory=list)


def load_labels():
    return json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}


def _alias(cfg, which, cc, kind, side, detail):
    m = cfg.get(which, {}).get(cc, {}).get(kind, {})
    return m.get(f"{side}:{detail}") or m.get(detail) or None


def campaign_start(campaign):
    m = re.search(r"_(\d{6})_(\d{6}|NONE)$", campaign.strip())
    return m.group(1) if m else "999999"


def roas_value(row):
    v = re.sub(r"[^0-9.]", "", row.cells.get("ROAS", ""))
    return float(v) if v else -1.0


def _need(row, key):
    if key not in row.cells:
        raise KeyError(f"시트에 '{key}' 열이 없습니다 (소재: {row.name[:40]}…). 시트 양식이 바뀌었는지 확인해 주세요.")
    return row.cells[key]


def kpi_text(side_kind, row):
    """('atc'|'pur', row) -> [줄1, 줄2]; 한 줄로 붙일 때는 ' / '.join."""
    spend = _need(row, "지출금액")
    roas = _need(row, "ROAS")
    if side_kind == "atc":
        return [f"지출 {spend}", f"장바구니 CPA {_need(row, 'CPA(장바구니 담기)')} / ROAS {roas}"]
    return [f"지출 {spend}", f"구매 CVR {_need(row, 'CVR(구매)')} / ROAS {roas}"]


def is_catalog(row):
    """카탈로그 소재(이름에 Catalog)는 분석 대상이 아니다 — 카드·표에서 제외."""
    return "catalog" in row.name.casefold()


def _ordered_blocks(blocks, side):
    bl = [b for b in blocks if b.side == side and not b.na_only and b.rows]
    return sorted(bl, key=lambda b: campaign_start(b.campaign))  # 안정 정렬: 같은 날짜면 시트 순서


def _pick(blocks, side, which, kpi_kind, cfg, cc, kind, warnings):
    """블록들에서 which('hi'|'lo') 체크된 행을 슬롯으로. 5개 초과면 디테일당 1개(ROAS 최고)로 줄인다."""
    items = []
    for b in _ordered_blocks(blocks, side):
        for r in b.rows:
            flag = r.hi if which == "hi" else r.lo
            if flag and not is_catalog(r):
                items.append((b, r))
    if len(items) > 5:
        best = {}
        for b, r in items:
            k = b.detail
            if k not in best or roas_value(r) > roas_value(best[k][1]):
                best[k] = (b, r)
        reduced = [it for it in items if best[it[0].detail][1] is it[1]]
        dropped = [r.name for b, r in items if best[b.detail][1] is not r]
        warnings.append(f"{'우수' if which == 'hi' else '저조'} {len(items)}개 > 5: 캠페인디테일당 ROAS 최고 1개만 남김 (제외: {', '.join(d[:36] + '…' for d in dropped)})")
        items = reduced
        if len(items) > 5:
            warnings.append(f"그래도 {len(items)}개 > 5: 앞의 5개만 사용")
            items = items[:5]
    slots = []
    for b, r in items:
        label = _alias(cfg, "card_label", cc, kind, side, b.detail) or b.detail
        slots.append(Slot(label=label, kpi=kpi_text(kpi_kind, r), name=r.name, cls=which, detail=b.detail, side=side,
                          cells=[(h, r.cells[h]) for h in r.order], memo=r.memo))
    return slots


def _table_specs(blocks, sides, cfg, cc, kind):
    specs = []
    for side in sides:
        for b in _ordered_blocks(blocks, side):
            if not any(r.hi or r.lo for r in b.rows):
                continue
            label = _alias(cfg, "table_label", cc, kind, side, b.detail) or ("ATC" if (kind == "OG" and side == "L") else b.detail)
            rows = [(r.name, [r.cells[h] for h in b.headers], "hi" if r.hi else ("lo" if r.lo else "")) for r in b.rows if not is_catalog(r)]
            specs.append(TableSpec(label=label, headers=b.headers, rows=rows))
    return specs


def plan_deck(cc, kind, blocks):
    cfg = load_labels()
    plan = DeckPlan(country=cc, kind=kind)
    W = plan.warnings
    zone = "상시" if kind == "OG" else "프로모션"
    if kind == "OG":
        # --- ATC (왼쪽 블록) ---
        atc_hi = _pick(blocks, "L", "hi", "atc", cfg, cc, kind, W)
        atc_lo = _pick(blocks, "L", "lo", "atc", cfg, cc, kind, W)
        # 같은 행이 우수·저조 양쪽에 중복되지 않게 (한 행에 TRUE 가 둘이면 시트 오류)
        both = {s.name for s in atc_hi} & {s.name for s in atc_lo}
        if both:
            W.append(f"우수·저조에 동시에 체크된 소재: {sorted(both)}")
        memos = [r.memo for b in blocks if b.side == "L" for r in b.rows if r.hi or r.lo]
        custom = [m for m in memos if not STD_ATC_MEMO.match(m)]
        if atc_hi or atc_lo:
            # 라벨/분류 결정
            cross = {}
            for b in _ordered_blocks(blocks, "L"):
                for r in b.rows:
                    if r.hi or r.lo:
                        cross[r.name] = r.memo
            allslots = atc_hi + atc_lo
            if custom:
                # 메모가 직접 쓴 라벨 (예: 장바구니/구매 우수, 장바구니 저조 <> 구매 우수): 카드마다 메모를 라벨로 쓴다
                for s in allslots:
                    s.label = cross.get(s.name) or s.label
                    if "<>" in s.label:
                        s.cls = "mix"
                order = {"hi": 0, "mix": 1, "lo": 2}
                allslots.sort(key=lambda s: order[s.cls])
                title = f"{cc} {zone} 캠페인(ATC) 유입/구매 효율 우수 <> 저조 소재"
                if len(allslots) <= 5:
                    plan.slides.append(ContentSlide(title=title, slots=allslots))
                else:
                    plan.slides.append(ContentSlide(title=f"{cc} {zone} 캠페인(ATC) 유입 효율 우수 소재", slots=atc_hi))
                    plan.slides.append(ContentSlide(title=f"{cc} {zone} 캠페인(ATC) 유입 효율 저조 소재", slots=atc_lo))
            elif len(allslots) <= 5:
                plan.slides.append(ContentSlide(
                    title=f"{cc} {zone} 캠페인 유입 효율 우수 소재 <> 저조 소재", slots=allslots,
                    split=True, n_hi=len(atc_hi), n_lo=len(atc_lo),
                    group_labels=("ATC 효율 우수 소재", "ATC 효율 저조 소재")))
            else:
                if atc_hi:
                    plan.slides.append(ContentSlide(title=f"{cc} {zone} 캠페인 유입 효율 우수 소재", slots=atc_hi))
                if atc_lo:
                    plan.slides.append(ContentSlide(title=f"{cc} {zone} 캠페인 유입 효율 저조 소재", slots=atc_lo))
        pur_side = "R"
        pur_hi = _pick(blocks, pur_side, "hi", "pur", cfg, cc, kind, W)
        pur_lo = _pick(blocks, pur_side, "lo", "pur", cfg, cc, kind, W)
        if pur_hi:
            plan.slides.append(ContentSlide(title=f"{cc} {zone} 캠페인 구매 효율 우수 소재", slots=pur_hi))
        if pur_lo:
            plan.slides.append(ContentSlide(title=f"{cc} {zone} 캠페인 구매 효율 저조 소재", slots=pur_lo))
        plan.tables = _table_specs(blocks, ("L", "R"), cfg, cc, kind)
    else:  # PR : 왼쪽 블록 = PR, 오른쪽 블록 = BR(이번 범위 제외)
        hi = _pick(blocks, "L", "hi", "pur", cfg, cc, kind, W)
        lo = _pick(blocks, "L", "lo", "pur", cfg, cc, kind, W)
        if hi:
            plan.slides.append(ContentSlide(title=f"{cc} {zone} 캠페인 구매 효율 우수 소재", slots=hi))
        if lo:
            plan.slides.append(ContentSlide(title=f"{cc} {zone} 캠페인 구매 효율 저조 소재", slots=lo))
        plan.tables = _table_specs(blocks, ("L",), cfg, cc, kind)
        plan.infos.append("BR(파트너십)은 이번 범위(P1-1)에서 제외")
    for b in blocks:
        if b.note and b.rows and any(r.hi or r.lo for r in b.rows):
            plan.infos.append(f"시트 메모: [{b.detail}] {b.note}")
    for s in plan.slides:
        if len(s.slots) < 3:
            W.append(f"'{s.title.strip()}' 슬롯이 {len(s.slots)}개 (3개 미만): 3슬롯 레이아웃에서 남는 자리를 지우고 만듭니다")
    return plan
