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


def deck_slides(path):
    p = Presentation(path)
    res = []
    for n, s in enumerate(p.slides, 1):
        res.append(dict(n=n, layout=s.slide_layout.name, title=slide_title(s),
                        cards=slide_cards(s), tables=slide_tables(s), slide=s))
    return res
