"""pptx 에서 카드(라벨·KPI·소재명)와 표를 뽑는 읽기 도구. verify.py 와 개발용 스크립트가 같이 쓴다."""
import re
from pptx import Presentation
from pptx.util import Emu

IN = 914400


def _walk(shapes, ox=0.0, oy=0.0, sx=1.0, sy=1.0):
    """그룹 변환을 반영한 절대 좌표(인치)로 (shape, left, top, w, h) 를 낸다."""
    for sh in shapes:
        if sh.shape_type == 6:  # group
            x = sh._element.grpSpPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm')
            ns = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
            off, ext = x.find(ns + 'off'), x.find(ns + 'ext')
            choff, chext = x.find(ns + 'chOff'), x.find(ns + 'chExt')
            gx, gy, gw, gh = int(off.get('x')), int(off.get('y')), int(ext.get('cx')), int(ext.get('cy'))
            cx, cy, cw, ch = int(choff.get('x')), int(choff.get('y')), int(chext.get('cx')), int(chext.get('cy'))
            fx = gw / cw if cw else 1.0
            fy = gh / ch if ch else 1.0
            # 자식 좌표 -> 슬라이드 좌표 : g + (c - ch) * f   (부모 변환은 한 단계만 지원)
            for child, l, t, w, h in _walk(sh.shapes, 0, 0, 1, 1):
                yield (child, (gx + (l * IN - cx) * fx) / IN, (gy + (t * IN - cy) * fy) / IN,
                       w * fx, h * fy)
        else:
            yield sh, (sh.left or 0) / IN, (sh.top or 0) / IN, (sh.width or 0) / IN, (sh.height or 0) / IN


def text_of(sh):
    if not sh.has_text_frame:
        return ""
    return "\n".join("".join(r.text for r in p.runs) for p in sh.text_frame.paragraphs)


def norm(s):
    """공백·줄바꿈·구분자를 지운 비교용 문자열."""
    return re.sub(r"[\s/|]+", "", s.replace("\x0b", ""))


def slide_items(slide):
    items = []
    for sh, l, t, w, h in _walk(slide.shapes):
        items.append(dict(shape=sh, x=l, y=t, w=w, h=h, text=text_of(sh) if sh.has_text_frame else ""))
    return items


def slide_cards(slide):
    """카드 목록 [(라벨, KPI, 소재명)] — x 순서대로. KPI 박스 기준으로 라벨(위)·소재명(아래)을 묶는다."""
    items = slide_items(slide)
    kpis = [i for i in items if i["text"] and re.search(r"ROAS\s*[\d,]+%", i["text"]) and re.search(r"지출|소진량", i["text"])]
    kpis.sort(key=lambda i: (round(i["x"] + i["w"] / 2, 0), i["y"]))
    cards = []
    for k in sorted(kpis, key=lambda i: i["x"] + i["w"] / 2):
        cx = k["x"] + k["w"] / 2
        # 소재명: KPI 바로 아래(0.5인치 이내)에서 x 중심이 가장 가까운 텍스트
        under = [i for i in items if i["text"].strip() and i is not k and 0 < i["y"] - k["y"] < 0.6
                 and abs((i["x"] + i["w"] / 2) - cx) < 1.6 and "ROAS" not in i["text"]]
        name = max(under, key=lambda i: -abs((i["x"] + i["w"] / 2) - cx))["text"] if under else ""
        # 라벨: KPI 위쪽 y 2.7~3.3 사이
        above = [i for i in items if i["text"].strip() and 2.7 < i["y"] < 3.1 and abs((i["x"] + i["w"] / 2) - cx) < 1.9]
        label = min(above, key=lambda i: abs((i["x"] + i["w"] / 2) - cx))["text"] if above else ""
        cards.append(dict(label=label.strip(), kpi=k["text"], name=name, x=cx))
    return cards


BR_KPI = re.compile(r"소진(량|금액)\s*[\d.,]+")


def slide_br_cards(slide):
    """BR 카드 [(계정명, KPI)] — '소진량' KPI 박스 기준. 계정명은 바로 위 '[Partnership_…]' 텍스트.
    KPI 가 두 박스로 나뉜 경우(구매 줄이 따로) 바로 아래 '구매 n건' 박스를 붙인다."""
    items = [i for i in slide_items(slide) if i["text"].strip()]
    kpis = [i for i in items if BR_KPI.search(i["text"])]
    cards = []
    for k in sorted(kpis, key=lambda i: (i["x"] + i["w"] / 2)):
        cx = k["x"] + k["w"] / 2
        above = [i for i in items if i["text"].strip().startswith("[") and 0 <= k["y"] - i["y"] < 0.6
                 and abs((i["x"] + i["w"] / 2) - cx) < 1.4]
        acc = min(above, key=lambda i: (k["y"] - i["y"], abs((i["x"] + i["w"] / 2) - cx)))["text"].strip() if above else ""
        kpi = k["text"]
        if "구매" not in kpi or "ROAS" not in kpi:
            below = [i for i in items if i is not k and 0 < i["y"] - k["y"] < 0.4 and abs((i["x"] + i["w"] / 2) - cx) < 1.4
                     and re.search(r"구매\s*[\d,]+\s*건", i["text"])]
            if below and "ROAS" not in kpi:
                kpi = kpi + "\n" + min(below, key=lambda i: i["y"])["text"]
        cards.append(dict(account=acc, kpi=kpi.strip(), x=cx))
    return cards


def slide_title(slide):
    items = [i for i in slide_items(slide) if i["text"].strip() and 0.7 < i["y"] < 1.4 and i["w"] > 8]
    return items[0]["text"].strip() if items else ""


def slide_tables(slide):
    """[(제목, [[셀,...],...])] — 제목은 표 바로 위 '▼ <...>' 텍스트."""
    items = slide_items(slide)
    heads = [i for i in items if i["text"].startswith("▼")]
    out = []
    for i in items:
        if i["shape"].has_table:
            tbl = i["shape"].table
            cells = [[c.text.strip() for c in r.cells] for r in tbl.rows]
            cand = [h for h in heads if 0 <= i["y"] - h["y"] < 0.6 and abs(h["x"] - i["x"]) < 1.0]
            title = cand[0]["text"].strip() if cand else ""
            out.append(dict(title=title, cells=cells, x=i["x"], y=i["y"]))
    out.sort(key=lambda t: (t["y"], t["x"]))
    return out


TAG = re.compile(r"^([A-Z]{2})\s*-\s*(OG|PR|BR)$")
COUNTRIES = {"ID", "MY", "PH", "SG"}


def _slide_key(s, layout, cur, has_br):
    """슬라이드가 어느 (국가, 유형) 인지. 레이아웃 이름 → 장표 안 머리표 글자('MY - BR') → 앞 간지 순.
    소진량 카드가 있으면 유형은 BR (FN 은 BR 장표에 PR 등 다른 레이아웃을 쓴 경우가 있음)."""
    texts = [text_of(sh).strip() for sh, *_ in _walk(s.shapes) if text_of(sh).strip()]
    m = TAG.match(layout.strip())
    key = m.groups() if m else None
    tag = next((TAG.match(t).groups() for t in texts if TAG.match(t)), None)
    if tag and key is None:
        key = tag
    if key is None and cur[0] and cur[1]:
        key = (cur[0], cur[1])
    if key and key[1] == "PR" and cur[1] == "BR":
        key = (key[0], "BR")   # BR 간지 뒤인데 PR 레이아웃을 그대로 쓴 장표
    if has_br:
        key = ((key or (cur[0], None))[0], "BR")
    return key, texts


def deck_slides(path):
    """슬라이드별 정보. key = (국가, OG|PR|BR) 또는 None(표지·EOD 등)."""
    p = Presentation(path)
    res = []
    cur = [None, None]   # 앞에서 본 간지: [국가, 유형]
    for n, s in enumerate(p.slides, 1):
        layout = s.slide_layout.name
        brc = slide_br_cards(s)
        key, texts = _slide_key(s, layout, cur, bool(brc))
        body = [t for t in texts if not TAG.match(t) and t not in ("EAST", "teammint")]
        if len(body) == 1 and body[0] in COUNTRIES:
            cur[0], cur[1] = body[0], None
        elif len(body) == 1 and body[0] in ("OG", "PR", "BR"):
            cur[1] = body[0]
            if key:
                cur[0] = cur[0] or key[0]
        is_br = bool(key and key[1] == "BR")
        res.append(dict(n=n, layout=layout, key=key, title=slide_title(s),
                        cards=[] if is_br else slide_cards(s), br_cards=brc if is_br else [],
                        tables=slide_tables(s), slide=s))
    return res
