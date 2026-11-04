"""PR&BR 탭의 오른쪽(BR) 블록 → BR(브랜딩 파트너십) 슬라이드 계획.

8~10월 EAST-1·EAST-2 FN 기준 형식 [확인됨, docs/SPEC.md 2-4]:
- 캠페인디테일 블록(체크된 행이 있는 것)마다 한 장. 카드 블록 + 같은 장 하단 TOP10 표, 코멘트 박스 없음.
- 체크 열이 '소진량 최상위 / 유입 고효율 소재'(EAST-1 ID) 이면 그 두 이름으로 블록을 나눈다.
  체크 열이 '고효율 / 저효율'(EAST-2 MY·SG) 이면 행 메모(> 유입 저조, > ROAS/유입 우수 …)로 유입/구매/유입&구매 × 우수/저조 블록을 나눈다.
- 카드에는 소재명 대신 계정명 `[Partnership_계정]` 과 KPI 를 쓴다.
- KPI 의 '소진량'만 만원 단위로 바꾼다 (소수 1자리, 반올림) — CLAUDE.md 규칙 1 의 유일한 예외 (26-11-04 지윤님 결정).
  CTR·CPC·구매·ROAS 는 시트 문자열 그대로 (₩ 만 떼고 원/건 을 붙임).
"""
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

MAX_CARDS = 5
TYPE_IN, TYPE_BOTH, TYPE_PUR = "in", "both", "pur"
TYPE_TEXT = {TYPE_IN: "유입 효율 (CTR, CPC)", TYPE_BOTH: "유입 & 구매 효율", TYPE_PUR: "구매 효율(ROAS)"}
TYPE_ORDER = {TYPE_IN: 0, TYPE_BOTH: 1, TYPE_PUR: 2}


@dataclass
class BRCard:
    account: str        # [Partnership_계정]
    kpi: list           # KPI 줄 (1~2줄)
    name: str           # 소재명 (이미지 찾기·대조용, 장표에는 안 씀)
    cls: str            # 'hi' | 'lo'


@dataclass
class BRGroup:
    title: str          # ▼ … 소재
    cards: list


@dataclass
class BRSlide:
    title: str
    groups: list
    note: str = ""
    table: object = None    # plan.TableSpec (title 포함) — 첫 장에만


# ----------------------------------------------------------------- 값 변환
def man_won(spend):
    """'₩1,180,750' → '118.1만원' (만원, 소수 1자리, 반올림). 숫자가 아니면 None."""
    digits = re.sub(r"[^0-9.]", "", spend or "")
    if not digits:
        return None
    v = (Decimal(digits) / Decimal(10000)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{v:,}만원"


def _won(v):
    """'₩8' → '8원' (숫자 문자열은 그대로)."""
    return v.replace("₩", "").strip() + "원"


def _count(v):
    """'₩272' / '248' → '272건' (시트 서식 때문에 건수에 ₩ 가 붙은 경우가 있음)."""
    return v.replace("₩", "").strip() + "건"


def account_label(name, with_length=False):
    """소재명에서 `[Partnership_계정]` (with_length 면 `[Partnership_계정_길이]`). 못 찾으면 None."""
    toks = name.split("_")
    try:
        i = next(k for k, t in enumerate(toks) if t.casefold() == "partnership")
    except StopIteration:
        return None
    rest = toks[i + 1:]
    acc, length = [], None
    for k, t in enumerate(rest):
        if re.fullmatch(r"\d+x\d+", t):
            nxt = rest[k + 1] if k + 1 < len(rest) else ""
            if re.fullmatch(r"(\d+m)?\d+s", nxt):
                length = nxt
            break
        acc.append(t)
    if not acc:
        return None
    label = "_".join(acc)
    if with_length and length:
        label += f"_{length}"
    return f"[Partnership_{label}]"


def classify_memo(memo, cls):
    """행 메모 → (유형, 등급, 경고 또는 None). 등급은 'hi'|'lo'."""
    m = memo.replace(" ", "")
    has_in = any(k in m for k in ("유입", "CTR", "CPC"))
    has_pur = any(k in m for k in ("구매", "ROAS"))
    warn = None
    if has_in and has_pur:
        typ = TYPE_BOTH
    elif has_in:
        typ = TYPE_IN
    elif has_pur:
        typ = TYPE_PUR
    else:
        typ = TYPE_BOTH
        warn = "메모에 유입/구매 구분이 없어 '유입 & 구매 효율'로 분류"
    good, bad = "우수" in m, "저조" in m
    grade = cls
    if good != bad:
        g = "hi" if good else "lo"
        if g != cls:
            warn = f"메모('{memo}')와 체크 열이 반대 — 체크 열 기준으로 '{'우수' if cls == 'hi' else '저조'}' 처리"
    return typ, grade, warn


def kpi_lines(typ, row, need):
    spend = man_won(need(row, "지출금액"))
    if spend is None:
        spend = need(row, "지출금액")
    sp = f"소진량 {spend}"
    if typ == TYPE_IN:
        return [f"{sp} / CTR {need(row, 'CTR')} / CPC {_won(need(row, 'CPC'))}"]
    if typ == TYPE_PUR:
        return [f"{sp} / 구매 {_count(need(row, '구매'))} / ROAS {need(row, 'ROAS')}"]
    return [f"{sp} / CTR {need(row, 'CTR')} / CPC {_won(need(row, 'CPC'))}",
            f"구매 {_count(need(row, '구매'))} / ROAS {need(row, 'ROAS')}"]


# ----------------------------------------------------------------- 계획
def _channel(campaign):
    m = re.search(r"CPAS-([A-Za-z]+)", campaign)
    return m.group(1) if m else ""


def _partner_name(detail, with_suffix):
    if detail.casefold().startswith("partnership"):
        suffix = detail[len("partnership"):].lstrip("-_ ")
        return f"파트너십-{suffix}" if (with_suffix and suffix) else "파트너십"
    return detail


def _chunks(groups, limit):
    """그룹을 슬라이드당 카드 limit 개 이하로 나눈다. 그룹은 들어갈 자리가 없을 때만 쪼갠다."""
    pages, cur, n = [], [], 0
    for g in groups:
        cards = list(g.cards)
        if cur and len(cards) > limit - n and len(cards) <= limit:
            pages.append(cur)
            cur, n = [], 0
        while cards:
            if n == limit:
                pages.append(cur)
                cur, n = [], 0
            take, cards = cards[:limit - n], cards[limit - n:]
            cur.append(BRGroup(title=g.title, cards=take))
            n += len(take)
    if cur:
        pages.append(cur)
    return pages


def plan_br(cc, blocks, cfg, need, is_catalog, ordered_blocks, alias, TableSpec, warnings, infos):
    """BR 블록들 → [BRSlide]."""
    br_cfg = cfg.get("br", {}).get(cc, {})
    with_length = bool(br_cfg.get("account_with_length", False))
    note = br_cfg.get("note", "")
    slides = []
    for b in ordered_blocks(blocks, "R"):
        rows = [r for r in b.rows if not is_catalog(r)]
        checked = [r for r in rows if r.hi or r.lo]
        if not checked:
            continue
        chan = _channel(b.campaign)
        top_mode = "소진량" in b.flags[0]
        groups = []
        if top_mode:
            # 체크 열 이름 그대로 두 블록 (둘 다 '우수' 성격) — KPI 는 유입 지표
            titles = (f"▼ {cc} {b.detail} 캠페인 소진량 최상위 소재",
                      f"▼ {cc} {b.detail} 캠페인 평균 대비 유입 효율 (CTR, CPC) 우수 소재")
            for which, title in zip(("hi", "lo"), titles):
                cards = [BRCard(account="", kpi=kpi_lines(TYPE_IN, r, need), name=r.name, cls="hi")
                         for r in rows if (r.hi if which == "hi" else r.lo)]
                if cards:
                    groups.append(BRGroup(title=title, cards=cards))
            both = [r.name for r in rows if r.hi and r.lo]
            if both:
                warnings.append(f"BR '{b.detail}': 소진량 최상위·유입 고효율에 동시에 체크된 소재 {len(both)}개 — 두 블록에 모두 넣음")
            any_lo = False
        else:
            keyed = {}
            for r in checked:
                if r.hi and r.lo:
                    warnings.append(f"BR 고효율·저효율에 동시에 체크: {r.name[:50]}… — 고효율로 처리")
                cls = "hi" if r.hi else "lo"
                typ, grade, warn = classify_memo(r.memo, cls)
                if warn:
                    warnings.append(f"BR {r.name[:40]}…: {warn}")
                keyed.setdefault((typ, grade), []).append(
                    BRCard(account="", kpi=kpi_lines(typ, r, need), name=r.name, cls=grade))
            for (typ, grade) in sorted(keyed, key=lambda k: (TYPE_ORDER[k[0]], k[1] == "lo")):
                title = f"▼ 평균 대비 {TYPE_TEXT[typ]} {'우수' if grade == 'hi' else '저조'} 소재"
                groups.append(BRGroup(title=title, cards=keyed[(typ, grade)]))
            any_lo = any(g == "lo" for _, g in keyed)
        for g in groups:
            for c in g.cards:
                acc = account_label(c.name, with_length)
                if acc is None:
                    warnings.append(f"BR 계정명을 소재명에서 찾지 못함 (Partnership_계정_해상도 형식 아님): {c.name[:60]} — 소재명을 그대로 씀")
                    acc = c.name
                c.account = acc
        pname = _partner_name(b.detail, top_mode)
        head = f"{cc} {chan + ' ' if chan else ''}브랜딩 {pname} 캠페인 우수{' <> 저조' if any_lo else ''} 소재"
        label = alias(cfg, "table_label", cc, "BR", "R", b.detail) or b.detail
        n = len(rows)
        prefix = f"{chan}-CPAS " if chan else ""
        ttitle = (f"▼ {prefix}<{label}> 소재 지출 금액 TOP {n}" if top_mode
                  else f"▼ {prefix}<{label}> 소재별 주요 성과 (총 {n}건)")
        tcls = (lambda r: "hi" if (r.hi or r.lo) else "") if top_mode else (lambda r: "hi" if r.hi else ("lo" if r.lo else ""))
        table = TableSpec(label=label, headers=b.headers,
                          rows=[(r.name, [r.cells[h] for h in b.headers], tcls(r)) for r in rows], title=ttitle)
        pages = _chunks(groups, MAX_CARDS)
        if len(pages) > 1:
            warnings.append(f"BR '{b.detail}' 카드 {sum(len(g.cards) for g in groups)}개 > {MAX_CARDS}: {len(pages)}장으로 나눔 (표는 첫 장에만)")
        for k, pg in enumerate(pages):
            slides.append(BRSlide(title=head, groups=pg, note=note, table=table if k == 0 else None))
    return slides
