"""양식(template/)을 복제·채워서 국가×유형별 pptx 를 만든다.

- 코멘트 박스·콜아웃은 비워 둔다 (코멘트는 별도 스킬 담당).
- 이미지는 양식의 '소재 이미지' 사각형 위치·크기에 맞춰 정사각 크롭 후 교체. 없으면 사각형을 남기고 기록한다.
- 텍스트는 run 단위로 교체해 서식을 보존한다.
"""
import copy
from pathlib import Path

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.util import Emu, Inches, Pt

from pptx_util import (A_NS, clear_text, clone_shapes, delete_slide, move_slide_to_end_order, new_slide,
                       set_lines, set_para_text, split_sku)

IMG_EXT = (".png", ".jpg", ".jpeg")
GREEN, PINK = "E2F0D9", "FADADD"   # 표 하이라이트: 우수=연두, 저조=분홍 [추정: SPEC 3장 기준, FN 은 우수만 칠함]
SLOT_TEMPLATE_INDEX = {3: 1, 4: 2, 5: 3}   # 양식 슬라이드 번호(0부터): 3/4/5슬롯
TABLE_TEMPLATE_INDEX = 17
EOD_INDEX = 16


class ImageIndex:
    """images/ 폴더에서 파일명(확장자 뺀 것) = 소재명 으로 찾는다. 대소문자는 구분하지 않는다.
    images_manual/ (images/ 와 같은 위치)에 같은 이름의 파일이 있으면 그것이 우선이고, 자동 수집이 덮어쓰지 않는다."""

    def __init__(self, folder):
        self.map = {}
        self.manual_keys = set()
        folder = Path(folder)
        if folder.exists():
            for p in folder.iterdir():
                if p.suffix.lower() in IMG_EXT:
                    self.map[p.stem.casefold()] = p
        manual = folder.parent / "images_manual" if folder.name == "images" else None
        if manual is not None and manual.exists():
            for p in manual.iterdir():
                if p.suffix.lower() in IMG_EXT:
                    self.map[p.stem.casefold()] = p
                    self.manual_keys.add(p.stem.casefold())

    def find(self, name):
        return self.map.get(name.casefold())

    def find_shots(self, name, n):
        """BR 소재의 캡처 n 장: `소재명_1`, `소재명_2` … . 1번이 없으면 `소재명`(자동 수집 썸네일)을 1번으로 쓴다."""
        shots = [self.find(f"{name}_{j + 1}") for j in range(n)]
        if shots[0] is None:
            shots[0] = self.find(name)
        return shots


# ----------------------------------------------------------------- 도형 찾기
def _cx(s):
    return s.left + s.width / 2


def find_slots(slide):
    top = list(slide.shapes)
    rects = sorted([s for s in top if s.has_text_frame and s.text_frame.text.strip() == "소재 이미지"], key=lambda s: s.left)
    labels = [s for s in top if s.has_text_frame and s.text_frame.text.strip() == "캠페인명"]
    groups = [s for s in top if s.shape_type == 6 and any(
        c.has_text_frame and c.text_frame.text.strip().startswith("지출") for c in s.shapes)]
    slots = []
    for r in rects:
        lab = min(labels, key=lambda l: abs(_cx(l) - _cx(r)))
        grp = min(groups, key=lambda g: abs(_cx(g) - _cx(r)))
        kpi = next(c for c in grp.shapes if c.has_text_frame and c.text_frame.text.strip().startswith("지출"))
        nm = next(c for c in grp.shapes if c.has_text_frame and c.text_frame.text.strip().startswith("소재명"))
        slots.append(dict(rect=r, label=lab, group=grp, kpi=kpi, name=nm))
    return slots


def _remove(sh):
    sh._element.getparent().remove(sh._element)


def put_image(slide, rect, path):
    """rect 자리에 그림을 넣고 rect 를 지운다. 그림은 rect 비율(정사각, BR 은 세로형)에 맞춰 가운데를 잘라 쓰고,
    rect 의 겹침 순서를 이어받는다."""
    pic = slide.shapes.add_picture(str(path), rect.left, rect.top, rect.width, rect.height)
    with Image.open(path) as im:
        w, h = im.size
    target = rect.width / rect.height
    if w / h > target:      # 그림이 더 넓다 → 좌우를 자른다
        cut = (1 - target * h / w) / 2
        pic.crop_left = pic.crop_right = cut
    elif w / h < target:    # 그림이 더 길다 → 위아래를 자른다
        cut = (1 - (w / target) / h) / 2
        pic.crop_top = pic.crop_bottom = cut
    # 그림 효과: 양식 사각형의 효과(바깥쪽 그림자 – 오프셋: 오른쪽 아래)를 그림에 그대로 옮긴다
    eff = rect._element.spPr.find(f"{{{A_NS}}}effectLst")
    if eff is not None:
        pic._element.spPr.append(copy.deepcopy(eff))
    rect._element.addprevious(pic._element)
    _remove(rect)


# ----------------------------------------------------------------- 표지
def fill_cover(slide, yy, mm, created, period):
    sm, sd, em, ed = period
    done = set()
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        for para in sh.text_frame.paragraphs:
            for r in para.runs:
                t = r.text
                if "ST MM" in t:
                    r.text = t.replace("MM", f"{em:02d}"); done.add("title")
                elif t == "YY":
                    r.text = yy; done.add("yy")
                elif t.startswith("-MM-DD"):
                    r.text = t.replace("-MM-DD", f"-{created.month:02d}-{created.day:02d}"); done.add("date")
                elif t.startswith(": MM/DD"):
                    r.text = f": {sm:02d}/{sd:02d} - {em:02d}/{ed:02d}"; done.add("period")
    missing = {"title", "yy", "date", "period"} - done
    if missing:
        raise RuntimeError(f"표지에서 채우지 못한 칸: {sorted(missing)} — 양식 표지가 바뀌었는지 확인해 주세요.")


# ----------------------------------------------------------------- 콘텐츠 슬라이드
def _move(shape, dx):
    shape.left = int(shape.left + dx)


def _apply_split(slide, slots, n_hi, n_lo, group_labels):
    top = list(slide.shapes)
    bg = next(s for s in top if s.shape_type == 1 and not (s.has_text_frame and s.text_frame.text.strip()) and s.width > Inches(5))
    bg2_el = copy.deepcopy(bg._element)
    bg._element.addnext(bg2_el)
    bg2 = next(s for s in slide.shapes if s._element is bg2_el)
    gap = int(Inches(0.03))
    L0, W = bg.left, bg.width
    wl = int((W - gap) * n_hi / (n_hi + n_lo))
    regions = [(L0, wl, slots[:n_hi]), (L0 + wl + gap, W - gap - wl, slots[n_hi:])]
    for (rl, rw, group), bgs, text in zip(regions, (bg, bg2), group_labels):
        bgs.left, bgs.width = rl, rw
        cell = rw / max(len(group), 1)
        for k, sl in enumerate(group):
            dx = rl + cell * (k + 0.5) - _cx(sl["rect"])
            for key in ("rect", "label", "group"):
                _move(sl[key], dx)
        # 그룹 라벨: 영역의 첫 슬롯 라벨을 영역 전체 폭으로 늘려 쓰고 나머지는 지운다
        first = group[0]["label"]
        set_lines(first, [text])
        first.left, first.width = int(rl + Inches(0.3)), int(rw - Inches(0.6))
        for sl in group[1:]:
            _remove(sl["label"])
            sl["label"] = None


def fill_content(prs, cc, kind, cs, imgs, tpl_slides, log):
    n = max(3, min(5, len(cs.slots)))
    src = tpl_slides[SLOT_TEMPLATE_INDEX[n]]
    slide = new_slide(prs, f"{cc} - {kind}")
    clone_shapes(src, slide)
    for sh in list(slide.shapes):
        if sh.has_text_frame:
            t = sh.text_frame.text
            if "자리가 없을 경우" in t:
                _remove(sh)
            elif t.startswith("(국가)"):
                set_lines(sh, [cs.title])
            elif t.startswith("서브헤더는"):
                clear_text(sh)   # 코멘트 박스는 비워 둔다
    slots = find_slots(slide)
    for sl in slots[len(cs.slots):]:   # 남는 슬롯 삭제
        for key in ("rect", "label", "group"):
            _remove(sl[key])
    slots = slots[:len(cs.slots)]
    for sl, sp in zip(slots, cs.slots):
        set_lines(sl["label"], [sp.label])
        set_lines(sl["kpi"], sp.kpi if len(sl["kpi"].text_frame.paragraphs) >= 2 else [" / ".join(sp.kpi)])
        set_lines(sl["name"], split_sku(sp.name))
        img = imgs.find(sp.name)
        if img:
            put_image(slide, sl["rect"], img)
        else:
            log.append(f"이미지 없음: {sp.name}  ({cs.title.strip()})")
    if cs.split:
        _apply_split(slide, slots, cs.n_hi, cs.n_lo, cs.group_labels)
    return slide


# ----------------------------------------------------------------- 표 슬라이드
def _set_cell_fill(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    for el in list(tcPr):
        if etree.QName(el).localname in ("solidFill", "noFill", "gradFill", "pattFill", "blipFill", "grpFill"):
            tcPr.remove(el)
    if not hexcolor:
        return
    sf = etree.Element(f"{{{A_NS}}}solidFill")
    etree.SubElement(sf, f"{{{A_NS}}}srgbClr").set("val", hexcolor)
    last = None
    for el in tcPr:
        if etree.QName(el).localname.startswith("ln"):
            last = el
    if last is not None:
        last.addnext(sf)
    else:
        tcPr.insert(0, sf)


def _fill_table(gf, spec):
    tbl = gf.table
    ncols = len(tbl.columns)
    if len(spec.headers) + 1 != ncols:
        raise ValueError(f"표 열 수가 맞지 않습니다: 시트 {len(spec.headers) + 1}열 / 양식 {ncols}열 ({spec.label})")
    need = len(spec.rows) + 1
    trs = list(tbl._tbl.tr_lst)
    while len(trs) > need:
        tbl._tbl.remove(trs.pop())
    while len(trs) < need:
        new = copy.deepcopy(trs[-1])
        trs[-1].addnext(new)
        trs.append(new)
    # 머리글은 양식·FN 표기대로 줄여 쓴다 ('(장바구니 담기)' → '(장바구니)')
    header = ["소재명"] + [h.replace("(장바구니 담기)", "(장바구니)") for h in spec.headers]
    for c, t in enumerate(header):
        set_para_text(tbl.cell(0, c).text_frame.paragraphs[0], t)
    for r, (name, vals, cls) in enumerate(spec.rows, start=1):
        for c, t in enumerate([name] + vals):
            cell = tbl.cell(r, c)
            set_para_text(cell.text_frame.paragraphs[0], t)
            _set_cell_fill(cell, {"hi": GREEN, "lo": PINK, "top": BLUE}.get(cls))
    gf.height = Emu(sum(r.height for r in tbl.rows))


def fill_table_slide(prs, cc, kind, specs, tpl_slides):
    slide = new_slide(prs, f"{cc} - {kind}")
    clone_shapes(tpl_slides[TABLE_TEMPLATE_INDEX], slide)
    zone = "상시" if kind == "OG" else "프로모션"
    heads = sorted([s for s in slide.shapes if s.has_text_frame and s.text_frame.text.startswith("▼")], key=lambda s: s.top)
    tables = sorted([s for s in slide.shapes if s.has_table], key=lambda s: s.top)
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.startswith("SKIN1004"):
            set_lines(sh, [f"SKIN1004 {cc} {zone} 캠페인별 우수 소재 상세 효율"])
    for i, (h, t) in enumerate(zip(heads, tables)):
        if i < len(specs):
            n = len(specs[i].rows)
            set_lines(h, [specs[i].title or f"▼ <{specs[i].label}> 소재 지출 금액 TOP {n}"])
            _fill_table(t, specs[i])
        else:
            _remove(h)
            _remove(t)
    # 두 번째 표는 첫 표의 실제 높이(긴 소재명 줄바꿈 포함 추정) 바로 아래로 — 양식은 두 표 사이 간격이 0 이라 겹쳤음
    if len(specs) > 1:
        dy = tables[1].top - heads[1].top
        y = tables[0].top + _table_height(tables[0]) + int(Inches(0.08))
        heads[1].top = int(y)
        tables[1].top = int(y + dy)
    return slide


def _table_height(gf):
    """표 실제 높이 추정: 행마다 글자 수 ÷ 칸 폭으로 줄 수를 어림 (9pt 기준 글자당 0.061", PowerPoint 캡처 기준)."""
    cols = [c.width for c in gf.table.columns]
    h = 0
    for row in gf.table.rows:
        lines = 1
        for c, cell in enumerate(row.cells):
            w = max(cols[c] - Inches(0.07), Inches(0.2))
            lines = max(lines, -(-int(len(cell.text) * Inches(0.061)) // int(w)) or 1)
        h += max(row.height, int(lines * Inches(0.16) + Inches(0.05)))
    return h



# ----------------------------------------------------------------- BR 슬라이드
# 좌표는 10월 EAST-1 ID FN 캡처 기준 (13.33" 폭) [확인됨: 지윤님 캡처 11/04]
BR_SHOTS = 2                                      # 소재 하나당 캡처 수 (영상 장면 2장)
BR_IMG_W, BR_IMG_H = Inches(1.17), Inches(2.05)   # 캡처 1장 크기 (세로형)
BR_IMG_GAP = Inches(0.1)                          # 같은 소재의 캡처 사이 간격
BR_HEAD_TOP, BR_IMG_TOP = Inches(1.55), Inches(1.9)
BR_ACC_TOP, BR_KPI_TOP = Inches(4.12), Inches(4.3)
BR_TABLE_HEAD_TOP, BR_TABLE_TOP = Inches(4.68), Inches(4.9)
BR_ROW_H = Inches(0.19)
BLUE = "DDEBF7"   # BR 표: 소진량 최상위 행 (ID FN) [확인됨]


def _clone_el(slide, el):
    new = copy.deepcopy(el)
    slide.shapes._spTree.append(new)
    return next(s for s in slide.shapes if s._element is new)


def _first(shapes, pred):
    return next(s for s in shapes if pred(s))


def _set_size(shape, pt):
    for p in shape.text_frame.paragraphs:
        for r in p.runs:
            r.font.size = Pt(pt)


def _br_parts(tpl_slides):
    """BR 장표를 짓는 데 쓸 양식 도형(XML)들: 제목·패널·이미지 자리·KPI·계정명·▼ 제목·표."""
    slot = tpl_slides[SLOT_TEMPLATE_INDEX[4]]
    tbl = tpl_slides[TABLE_TEMPLATE_INDEX]
    top = list(slot.shapes)
    grp = _first(top, lambda s: s.shape_type == 6)
    heads = sorted([s for s in tbl.shapes if s.has_text_frame and s.text_frame.text.startswith("▼")], key=lambda s: s.top)
    tables = sorted([s for s in tbl.shapes if s.has_table], key=lambda s: s.top)
    return dict(
        title=_first(top, lambda s: s.has_text_frame and s.text_frame.text.startswith("(국가)"))._element,
        panel=_first(top, lambda s: s.shape_type == 1 and not (s.has_text_frame and s.text_frame.text.strip()) and s.width > Inches(5))._element,
        rect=_first(top, lambda s: s.has_text_frame and s.text_frame.text.strip() == "소재 이미지")._element,
        kpi=_first(grp.shapes, lambda c: c.has_text_frame and c.text_frame.text.strip().startswith("지출"))._element,
        name=_first(grp.shapes, lambda c: c.has_text_frame and c.text_frame.text.strip().startswith("소재명"))._element,
        head=heads[-1]._element,
        table=tables[-1]._element,
        note=_first(tbl.shapes, lambda s: s.has_text_frame and s.text_frame.text.startswith("구매 효율 우수 소재"))._element,
    )


def _black(shape):
    for p in shape.text_frame.paragraphs:
        for r in p.runs:
            r.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)


def fill_br(prs, cc, br, imgs, tpl_slides, log):
    """BR 한 장: 제목 + 블록(▼ 블록 제목, 소재마다 세로형 캡처 2장 + 계정명 + KPI) + 주석 + TOP10 표. 코멘트 박스 없음.
    캡처는 images/ 의 `소재명_1`, `소재명_2` (없으면 1번 자리에 `소재명`)."""
    parts = _br_parts(tpl_slides)
    slide = new_slide(prs, f"{cc} - BR")
    title = _clone_el(slide, parts["title"])
    set_lines(title, [br.title])
    total = sum(len(g.cards) for g in br.groups)
    L0, W = Inches(0.95), Inches(11.5)
    # 소재 1개짜리 블록이 있으면(MY 4블록 등) 블록 제목이 두 줄이 되므로 글씨를 줄이고 캡처를 그만큼 내린다
    narrow = any(W * len(g.cards) / total < Inches(3.5) for g in br.groups)
    head_pt = 10.5 if narrow else 12
    img_top = BR_IMG_TOP + (Inches(0.25) if narrow else 0)
    img_h_max = BR_IMG_H - (Inches(0.25) if narrow else 0)
    x = L0
    for g in br.groups:
        gw = int(W * len(g.cards) / total)
        head = _clone_el(slide, parts["head"])
        set_lines(head, [g.title])
        _set_size(head, head_pt)
        head.left, head.top, head.width = int(x + Inches(0.12)), int(BR_HEAD_TOP), int(gw - Inches(0.12))
        cell = gw / len(g.cards)
        # 칸이 좁으면(소재 5개 등) 캡처를 줄인다 (세로형 비율 유지)
        iw = int(min(BR_IMG_W * img_h_max / BR_IMG_H, (cell - Inches(0.3) - BR_IMG_GAP * (BR_SHOTS - 1)) / BR_SHOTS))
        ih = int(iw * BR_IMG_H / BR_IMG_W)
        for k, c in enumerate(g.cards):
            cx = x + cell * (k + 0.5)
            pair_w = iw * BR_SHOTS + BR_IMG_GAP * (BR_SHOTS - 1)
            shots = imgs.find_shots(c.name, BR_SHOTS)
            for j in range(BR_SHOTS):
                rect = _clone_el(slide, parts["rect"])
                rect.width, rect.height = iw, ih
                rect.left, rect.top = int(cx - pair_w / 2 + j * (iw + BR_IMG_GAP)), int(img_top)
                if shots[j]:
                    put_image(slide, rect, shots[j])
            missing = [str(j + 1) for j in range(BR_SHOTS) if not shots[j]]
            if len(missing) == BR_SHOTS:
                log.append(f"이미지 없음: {c.name}  ({br.title.strip()})")
            elif missing:
                log.append(f"캡처 {','.join(missing)}번 없음: {c.name}_{missing[0]}  ({br.title.strip()})")
            tw = int(cell - Inches(0.04))
            acc = _clone_el(slide, parts["name"])
            set_lines(acc, [c.account])
            _set_size(acc, 9.5)
            _black(acc)
            acc.left, acc.top, acc.width = int(cx - tw / 2), int(BR_ACC_TOP), tw
            kpi = _clone_el(slide, parts["kpi"])
            set_lines(kpi, c.kpi)
            _set_size(kpi, 9)
            _black(kpi)
            kpi.left, kpi.top, kpi.width = int(cx - tw / 2), int(BR_KPI_TOP), tw
        x += gw
    if br.table is not None:
        head = _clone_el(slide, parts["head"])
        set_lines(head, [br.table.title])
        _set_size(head, 12)
        head.left, head.top, head.width = int(Inches(1.07)), int(BR_TABLE_HEAD_TOP), int(Inches(8.0))
        gf = _clone_el(slide, parts["table"])
        gf.left, gf.top = int(Inches(0.98)), int(BR_TABLE_TOP)
        _fill_table(gf, br.table)
        # 열 폭: 지출금액·장바구니담기는 넓게, 나머지 지표 0.65", 소재명은 남는 폭 (표 전체 폭 11.5")
        cols = gf.table.columns
        wide = {"지출금액": Inches(0.8), "장바구니담기": Inches(0.8)}
        widths = [wide.get(h, Inches(0.65)) for h in br.table.headers]
        cols[0].width = Emu(int(Inches(11.5) - sum(widths)))
        for c, w in zip(list(cols)[1:], widths):
            c.width = Emu(int(w))
        # 머리글은 전부 첫 칸(검정)과 같은 배경으로 (양식의 빨간 ROAS 머리글은 OG·PR 용) [확인됨: ID FN]
        head_fill = gf.table.cell(0, 0)._tc.get_or_add_tcPr().find(f"{{{A_NS}}}solidFill")
        if head_fill is not None:
            for ci in range(1, len(cols)):
                tcPr = gf.table.cell(0, ci)._tc.get_or_add_tcPr()
                for el in list(tcPr):
                    if etree.QName(el).localname in ("solidFill", "noFill", "gradFill", "pattFill"):
                        tcPr.remove(el)
                tcPr.append(copy.deepcopy(head_fill))
        for r in gf.table.rows:
            r.height = Emu(int(BR_ROW_H))
        gf.height = Emu(sum(r.height for r in gf.table.rows))
    if br.note:
        note = _clone_el(slide, parts["note"])
        set_lines(note, [br.note])
        _set_size(note, 9)
        note.left, note.width = int(Inches(7.9)), int(Inches(4.55))
        note.top = int(BR_TABLE_HEAD_TOP)
        for p in note.text_frame.paragraphs:
            p.alignment = PP_ALIGN.RIGHT
    return slide


# ----------------------------------------------------------------- 한 벌 만들기
def _find_by_text(slides, layout, text):
    for s in slides:
        if s.slide_layout.name == layout and any(sh.has_text_frame and sh.text_frame.text.strip() == text for sh in s.shapes):
            return s
    hint = " (BR 간지는 'python tools/add_br_template.py' 로 양식에 추가)" if layout.endswith("BR") else ""
    raise KeyError(f"양식에서 '{layout}' 레이아웃의 '{text}' 슬라이드를 찾지 못했습니다. 지원 국가: ID, MY, PH, SG{hint}")


def build_deck(plan, template_path, meta, images_dir, out_path, log):
    prs = Presentation(str(template_path))
    tpl = list(prs.slides)
    cc, kind = plan.country, plan.kind
    imgs = ImageIndex(images_dir)

    cover = tpl[0]
    fill_cover(cover, meta["yy"], meta["mm"], meta["created"], meta["period"])
    country_slide = _find_by_text(tpl, f"{cc} - OG", cc)
    kind_slide = _find_by_text(tpl, f"{cc} - {kind}", kind)

    order = [cover, country_slide]
    if plan.slides or plan.tables:
        order.append(kind_slide)
    for cs in plan.slides:
        order.append(fill_content(prs, cc, kind, cs, imgs, tpl, log))
    for i in range(0, len(plan.tables), 2):
        order.append(fill_table_slide(prs, cc, kind, plan.tables[i:i + 2], tpl))
    if plan.br:
        order.append(_find_by_text(tpl, f"{cc} - BR", "BR"))
        for br in plan.br:
            order.append(fill_br(prs, cc, br, imgs, tpl, log))
    eod = new_slide(prs, f"{cc} - {kind}")
    clone_shapes(tpl[EOD_INDEX], eod)
    order.append(eod)

    keep = {id(s.part) for s in order}
    for s in tpl:
        if id(s.part) not in keep:
            delete_slide(prs, s)
    move_slide_to_end_order(prs, order)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return out_path
