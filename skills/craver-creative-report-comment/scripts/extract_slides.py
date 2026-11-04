"""pptx → 코멘트 작성용 입력(slides.json + 슬롯 이미지 파일).

사용: python extract_slides.py 입력.pptx 작업폴더 [--blind]
  --blind : 코멘트 박스에 이미 들어 있는 글을 json 에 넣지 않는다 (FN 으로 시험할 때)
출력: 작업폴더/slides.json, 작업폴더/images/s{슬라이드번호}_{슬롯번호}.{확장자}
"""
import json
import sys
from pathlib import Path

from pptx import Presentation

sys.path.insert(0, str(Path(__file__).parent))
from pptx_comment import find_comment_box, find_slots, find_title, layout_country_kind, slot_class, text_of  # noqa: E402


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    blind = "--blind" in sys.argv
    (out / "images").mkdir(parents=True, exist_ok=True)
    prs = Presentation(str(src))
    result = []
    for no, slide in enumerate(prs.slides, start=1):
        title = find_title(slide)
        box = find_comment_box(slide)
        slots = find_slots(slide)
        if title is None or box is None or not slots:
            continue
        cc, kind = layout_country_kind(slide)
        ttl = " ".join(text_of(title).split())
        items = []
        for k, sl in enumerate(slots, start=1):
            label = " ".join(text_of(sl["label"]).split()) if sl["label"] is not None else ""
            img = None
            if sl["pic"] is not None:
                blob = sl["pic"].image
                img = f"images/s{no:02d}_{k}.{blob.ext}"
                (out / img).write_bytes(blob.blob)
            items.append(dict(
                no=k, label=label, cls=slot_class(ttl, label),
                name="".join(text_of(sl["name"]).split()) if sl["name"] is not None else "",
                kpi=" / ".join(x.strip() for x in text_of(sl["kpi"]).split("\n") if x.strip()),
                image=img or "이미지 없음"))
        rec = dict(slide_no=no, country=cc, kind=kind, title=ttl,
                   comment_paragraphs=len(box.text_frame.paragraphs), slots=items)
        if not blind:
            rec["existing_comment"] = [p.text for p in box.text_frame.paragraphs if p.text.strip()]
        result.append(rec)
    (out / "slides.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"코멘트 슬라이드 {len(result)}장 → {out / 'slides.json'}")
    for r in result:
        miss = sum(1 for s in r["slots"] if s["image"] == "이미지 없음")
        print(f"  #{r['slide_no']} {r['title']} — 슬롯 {len(r['slots'])}개" + (f", 이미지 없음 {miss}" if miss else ""))


if __name__ == "__main__":
    main()
