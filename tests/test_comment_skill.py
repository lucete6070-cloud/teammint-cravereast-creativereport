"""코멘트 스킬 스크립트(추출·점검·삽입)를 양식 pptx 로 끝까지 돌려 본다. 실행: python tests/test_comment_skill.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parent.parent
K = ROOT / "skills" / "craver-creative-report-comment" / "scripts"
sys.path.insert(0, str(K))
from pptx_comment import find_comment_box  # noqa: E402

TEMPLATE = ROOT / "template" / "EAST_template.pptx"


def run(*args, ok=True):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    if ok and r.returncode != 0:
        raise AssertionError(r.stdout + r.stderr)
    return r


def main():
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "work"
        # 1) 추출: 양식의 3·4·5슬롯 슬라이드 3장 (이미지 없음 상태)
        run(K / "extract_slides.py", TEMPLATE, work)
        slides = json.loads((work / "slides.json").read_text(encoding="utf-8"))
        nos = [s["slide_no"] for s in slides]
        assert nos[:3] == [2, 3, 4], nos
        assert [len(s["slots"]) for s in slides[:3]] == [3, 4, 5], [len(s["slots"]) for s in slides[:3]]
        assert all(sl["image"] == "이미지 없음" for sl in slides[0]["slots"])
        assert slides[0]["existing_comment"], "양식 코멘트 박스 글이 읽혀야 함"

        # 2) 점검: 나쁜 초안은 걸리고, 좋은 초안은 통과
        kpi = slides[0]["slots"][0]["kpi"]
        bad = [{"slide_no": 2, "body": ["매출이 늘었다.", "ROAS 777% 기록"], "arrow": "계속 확인"}]
        (work / "drafts.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        r = run(K / "check_drafts.py", work, ok=False)
        assert r.returncode == 1 and "'~다.' 종결" in r.stdout and "777%" in r.stdout and "처방형" in r.stdout, r.stdout

        good = [{"slide_no": n, "body": ["우수 소재는 할인율을 첫 화면에 크게 둔 양상",
                                          "특히 세트 소재는 전월에 이어 우수군 유지",
                                          "반면 저조 소재는 설명 요소 비중이 높았던 것으로 사료",
                                          "캠페인 라벨 : 효능 정보 나열로 혜택 인지가 분산되었을 가능성"],
                 "arrow": "▶ 첫 화면은 가격·할인 중심으로 단순화하는 방향 제언",
                 "callouts": [{"slot": 1, "text": "할인 혜택 부재"}], "notes": ["근거: 테스트"]} for n in nos]
        (work / "drafts.json").write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")
        r = run(K / "check_drafts.py", work)
        assert "점검 통과" in r.stdout, r.stdout

        # 3) 삽입: 본문 4줄 + ▶ 1줄, ▶ 문단 서식(run 속성) 유지, 노트 기입 / --no-notes 로 비우기
        before = Presentation(str(TEMPLATE))
        arrow_rpr = find_comment_box(before.slides[1]).text_frame.paragraphs[-1].runs[0]._r.rPr
        out = Path(td) / "out.pptx"
        run(K / "insert_comments.py", TEMPLATE, work, out)
        prs = Presentation(str(out))
        box = find_comment_box(prs.slides[1])
        texts = [p.text for p in box.text_frame.paragraphs]
        assert texts == good[0]["body"] + [good[0]["arrow"]], texts
        new_rpr = box.text_frame.paragraphs[-1].runs[0]._r.rPr
        assert (arrow_rpr is None and new_rpr is None) or arrow_rpr.xml == new_rpr.xml, "▶ 문단 서식이 바뀜"
        notes = prs.slides[1].notes_slide.notes_text_frame.text
        assert "콜아웃 후보 (슬롯 1): 할인 혜택 부재" in notes, notes

        out2 = Path(td) / "out2.pptx"
        run(K / "insert_comments.py", out, work, out2, "--no-notes")
        assert Presentation(str(out2)).slides[1].notes_slide.notes_text_frame.text.strip() == ""
    print("코멘트 스킬 테스트 통과")


if __name__ == "__main__":
    main()
