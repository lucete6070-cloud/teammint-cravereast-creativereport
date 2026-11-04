"""drafts.json 의 초안을 pptx 코멘트 박스에 넣고, 근거·콜아웃 후보·플래그를 슬라이드 노트에 적는다.

사용: python insert_comments.py 입력.pptx 작업폴더 출력.pptx [--no-notes]
  --no-notes : 노트 칸을 비운다 (최종 공유본용)
drafts.json 형식 (슬라이드마다 1개):
  {"slide_no": 4, "body": ["줄1", "줄2", "줄3"], "arrow": "▶ ...",
   "callouts": [{"slot": 1, "text": "할인 혜택 부재"}], "notes": ["근거: ...", "플래그: ..."]}
"""
import json
import sys
from pathlib import Path

from pptx import Presentation

sys.path.insert(0, str(Path(__file__).parent))
from pptx_comment import fill_comment_box, find_comment_box, set_notes  # noqa: E402


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    src, work, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    no_notes = "--no-notes" in sys.argv
    drafts = {d["slide_no"]: d for d in json.loads((work / "drafts.json").read_text(encoding="utf-8"))}
    prs = Presentation(str(src))
    done = []
    for no, slide in enumerate(prs.slides, start=1):
        d = drafts.get(no)
        if d is None:
            continue
        box = find_comment_box(slide)
        if box is None:
            print(f"#{no}: 코멘트 박스를 찾지 못해 건너뜀")
            continue
        fill_comment_box(box, d["body"], d.get("arrow", ""))
        if no_notes:
            if slide.has_notes_slide:
                set_notes(slide, [])
        else:
            lines = ["[코멘트 초안 근거 — 자동 기입, 최종본 전 삭제]"]
            for c in d.get("callouts", []):
                lines.append(f"콜아웃 후보 (슬롯 {c.get('slot')}): {c.get('text')}")
            lines += d.get("notes", [])
            set_notes(slide, lines)
        done.append(no)
    dst.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(dst))
    print(f"코멘트 {len(done)}장 입력 → {dst}")
    missing = set(drafts) - set(done)
    if missing:
        print(f"입력하지 못한 슬라이드: {sorted(missing)}")


if __name__ == "__main__":
    main()
