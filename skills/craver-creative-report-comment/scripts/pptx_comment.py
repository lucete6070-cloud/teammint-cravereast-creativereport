"""EAST Creative Report pptx 의 코멘트 슬라이드를 읽고(extract), 초안을 넣는(insert) 공용 함수.

생성기 1차본(코멘트 박스가 빈칸) 구조 기준:
- 제목: 위쪽(약 0.88in) 텍스트 박스, '소재' 포함
- 코멘트 박스: 왼쪽 약 0.88in, 위 약 1.45in, 폭 9in 이상인 텍스트 박스. 마지막 문단이 ▶ 줄
- 슬롯: '지출'로 시작하는 KPI 와 소재명이 든 그룹 + 위쪽 캠페인 라벨 + 그림(소재 이미지)
텍스트는 run 단위로 바꿔 서식을 지킨다 (text_frame.text = 금지).
"""
import copy
import re

from pptx.util import Emu

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
IN = 914400


def _in(v):
    return (v or 0) / IN


def _cx(s):
    return s.left + s.width / 2


def text_of(sh):
    return sh.text_frame.text if getattr(sh, "has_text_frame", False) and sh.has_text_frame else ""


def find_title(slide):
    cands = [s for s in slide.shapes if text_of(s).strip() and _in(s.top) < 1.3 and _in(s.width) > 6 and "소재" in text_of(s)]
    return min(cands, key=lambda s: s.top) if cands else None


def find_comment_box(slide):
    cands = [s for s in slide.shapes if getattr(s, "has_text_frame", False) and s.has_text_frame
             and _in(s.left) < 1.4 and 1.2 <= _in(s.top) <= 2.0 and _in(s.width) > 9]
    return min(cands, key=lambda s: s.top) if cands else None


def _group_texts(g):
    out = []
    for c in g.shapes:
        if c.shape_type == 6:
            out += _group_texts(c)
        elif c.has_text_frame:
            out.append(c)
    return out


def find_slots(slide):
    top = list(slide.shapes)
    groups = []
    for s in top:
        if s.shape_type == 6:
            texts = _group_texts(s)
            kpi = next((c for c in texts if c.text_frame.text.strip().startswith("지출")), None)
            if kpi is not None:
                name = next((c for c in texts if c is not kpi and c.text_frame.text.strip()), None)
                groups.append((s, kpi, name))
    pics = [s for s in top if s.shape_type == 13 and 2.5 < _in(s.top) < 6.5]
    rects = [s for s in top if text_of(s).strip() == "소재 이미지"]
    labels = [s for s in top if text_of(s).strip() and 2.5 < _in(s.top) < 3.4 and _in(s.height) < 0.6]
    slots = []
    for g, kpi, name in sorted(groups, key=lambda t: t[0].left):
        pic = min(pics, key=lambda p: abs(_cx(p) - _cx(g))) if pics else None
        if pic is not None and abs(_cx(pic) - _cx(g)) > 0.8 * IN:
            pic = None
        rect = None if pic is not None else (min(rects, key=lambda r: abs(_cx(r) - _cx(g))) if rects else None)
        # 라벨: 슬롯 중심을 덮는 라벨(분할 슬라이드의 넓은 그룹 라벨 포함) 중 가장 가까운 것
        cover = [l for l in labels if l.left - 0.2 * IN <= _cx(g) <= l.left + l.width + 0.2 * IN]
        lab = min(cover or labels, key=lambda l: abs(_cx(l) - _cx(g))) if labels else None
        slots.append(dict(group=g, kpi=kpi, name=name, pic=pic, rect=rect, label=lab))
    return slots


def slot_class(title, label):
    t, l = title or "", label or ""
    if "우수" in l and "저조" not in l:
        return "우수"
    if "저조" in l and "우수" not in l:
        return "저조"
    if "우수" in t and "저조" not in t:
        return "우수"
    if "저조" in t and "우수" not in t:
        return "저조"
    return "확인 필요"


def layout_country_kind(slide):
    m = re.match(r"([A-Z]{2})\s*-\s*([A-Z]{2})", slide.slide_layout.name or "")
    return (m.group(1), m.group(2)) if m else ("", "")


# ------------------------------------------------------------------ 텍스트 교체 (run 단위)
def set_para_text(para, text):
    runs = list(para.runs)
    if runs:
        runs[0].text = text
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
        return
    r = para.add_run()
    r.text = text
    end = para._p.find(f"{{{A_NS}}}endParaRPr")
    if end is not None:
        rpr = copy.deepcopy(end)
        rpr.tag = f"{{{A_NS}}}rPr"
        old = r._r.find(f"{{{A_NS}}}rPr")
        if old is not None:
            r._r.remove(old)
        r._r.insert(0, rpr)


def fill_comment_box(box, body_lines, arrow_line):
    """본문 문단은 첫 본문 문단 서식으로 늘리거나 줄이고, 마지막(▶) 문단은 그 서식 그대로 둔다."""
    paras = list(box.text_frame.paragraphs)
    if len(paras) >= 2:
        body, arrow = paras[:-1], paras[-1]
    else:
        body, arrow = paras, None
    while len(body) < len(body_lines):
        newp = copy.deepcopy(body[-1]._p)
        body[-1]._p.addnext(newp)
        body = list(box.text_frame.paragraphs)[:len(body) + 1]
    for p in body[len(body_lines):]:
        p._p.getparent().remove(p._p)
    body = body[:len(body_lines)]
    for p, t in zip(body, body_lines):
        set_para_text(p, t)
    if arrow_line:
        text = arrow_line if arrow_line.startswith("▶") else "▶ " + arrow_line
        if arrow is None:
            newp = copy.deepcopy(body[-1]._p)
            body[-1]._p.addnext(newp)
            arrow = list(box.text_frame.paragraphs)[-1]
        set_para_text(arrow, text)
    elif arrow is not None:
        set_para_text(arrow, "")


def set_notes(slide, lines):
    tf = slide.notes_slide.notes_text_frame
    paras = list(tf.paragraphs)
    for p in paras[1:]:
        p._p.getparent().remove(p._p)
    set_para_text(paras[0], lines[0] if lines else "")
    for t in lines[1:]:
        p = tf.add_paragraph()
        p.text = t   # 노트 칸은 서식이 없어 run 단위 규칙 대상이 아님
