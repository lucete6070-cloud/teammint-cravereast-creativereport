"""양식(template/EAST_template.pptx)에 BR(브랜딩 파트너십)용 레이아웃·간지를 추가한다.

- 레이아웃 `{국가} - BR` 4종: `{국가} - PR` 레이아웃을 복제하고 머리표 글자만 BR 로 바꾼다.
- BR 간지 4장: `{국가} - PR` 의 'PR' 간지를 복제해 'BR' 로 바꾼다 (양식 맨 뒤에 붙는다).
- 광고주 데이터가 들어가지 않으므로 FN 없이 돌릴 수 있고, 결과 양식은 git 에 올려도 된다.
- 이미 추가돼 있으면 아무것도 하지 않는다. build_template.py 가 양식을 새로 만들 때도 이 단계를 함께 부른다.

사용법:  python tools/add_br_template.py
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pptx import Presentation  # noqa: E402
from pptx.opc.constants import RELATIONSHIP_TYPE as RT  # noqa: E402
from pptx.parts.slide import SlideLayoutPart  # noqa: E402

from pptx_util import clone_shapes, layout_by_name, new_slide, set_para_text  # noqa: E402

TEMPLATE = ROOT / "template" / "EAST_template.pptx"
COUNTRIES = ("ID", "MY", "PH", "SG")
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _replace_run_text(shapes, old, new):
    n = 0
    for sh in shapes:
        if sh.shape_type == 6:
            n += _replace_run_text(sh.shapes, old, new)
            continue
        if not sh.has_text_frame:
            continue
        for p in sh.text_frame.paragraphs:
            for r in p.runs:
                if old in r.text:
                    r.text = r.text.replace(old, new)
                    n += 1
    return n


def clone_layout(prs, src_name, new_name, old_text, new_text):
    """src 레이아웃을 복제해 같은 마스터에 new_name 으로 추가한다."""
    src = layout_by_name(prs, src_name)
    pkg = prs.part.package
    el = copy.deepcopy(src._element)
    part = SlideLayoutPart(pkg.next_partname("/ppt/slideLayouts/slideLayout%d.xml"), src.part.content_type, pkg, el)
    # 관계(마스터·이미지) 복사: rId 가 달라질 수 있으니 XML 안의 참조를 새 rId 로 바꾼다
    remap = {}
    for rId, rel in src.part.rels.items():
        if rel.is_external:
            remap[rId] = part.relate_to(rel.target_ref, rel.reltype, is_external=True)
        else:
            remap[rId] = part.relate_to(rel.target_part, rel.reltype)
    for node in el.iter():
        for attr, val in list(node.attrib.items()):
            if attr.startswith(f"{{{R_NS}}}") and val in remap:
                node.set(attr, remap[val])
    el.cSld.set("name", new_name)
    lay = part.slide_layout
    if _replace_run_text(lay.shapes, old_text, new_text) == 0:
        raise RuntimeError(f"레이아웃 '{src_name}' 에서 머리표 '{old_text}' 를 찾지 못했습니다.")
    master = src.slide_master
    rId = master.part.relate_to(part, RT.SLIDE_LAYOUT)
    lst = master._element.get_or_add_sldLayoutIdLst()
    used = [int(x.get("id")) for x in lst] + [int(x.get("id")) for x in prs.part._element.sldMasterIdLst]
    new_id = max(used) + 1
    item = lst._add_sldLayoutId()
    item.set("id", str(new_id))
    item.set(f"{{{R_NS}}}id", rId)
    return lay


def _find_divider(prs, layout, text):
    for s in prs.slides:
        if s.slide_layout.name == layout and any(sh.has_text_frame and sh.text_frame.text.strip() == text for sh in s.shapes):
            return s
    return None


def add_br(prs):
    """BR 레이아웃·간지를 추가한다. 추가한 개수를 돌려준다 (이미 있으면 0)."""
    names = {lay.name for lay in prs.slide_layouts}
    added = 0
    for cc in COUNTRIES:
        if f"{cc} - BR" not in names:
            clone_layout(prs, f"{cc} - PR", f"{cc} - BR", f"{cc} - PR", f"{cc} - BR")
            added += 1
        if _find_divider(prs, f"{cc} - BR", "BR") is None:
            src = _find_divider(prs, f"{cc} - PR", "PR")
            if src is None:
                raise RuntimeError(f"양식에서 '{cc} - PR' 간지를 찾지 못했습니다.")
            dst = new_slide(prs, f"{cc} - BR")
            clone_shapes(src, dst)
            for sh in dst.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip() == "PR":
                    set_para_text(sh.text_frame.paragraphs[0], "BR")
            added += 1
    return added


def main():
    prs = Presentation(str(TEMPLATE))
    n = add_br(prs)
    if n == 0:
        print("이미 BR 레이아웃·간지가 있습니다. 바꾼 것 없음.")
        return 0
    prs.save(str(TEMPLATE))
    print(f"BR 레이아웃·간지 {n}개를 추가했습니다: {TEMPLATE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
