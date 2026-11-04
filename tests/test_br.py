"""BR(브랜딩 파트너십) 장표 시험: 가짜 PR&BR 탭(광고주 데이터 없음)으로 계획·pptx·HTML·대조까지. 실행: python tests/test_br.py"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from pptx import Presentation  # noqa: E402

import br_fixture  # noqa: E402
import verify  # noqa: E402
from plan import plan_deck  # noqa: E402
from plan_br import account_label, classify_memo, man_won  # noqa: E402
from pptx_read import deck_slides  # noqa: E402
from sheet import parse_blocks, read_csv  # noqa: E402


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  OK", msg)


def unit():
    print("[1] 값 변환")
    check(man_won("₩1,180,750") == "118.1만원", "₩1,180,750 → 118.1만원")
    check(man_won("₩285,408") == "28.5만원", "₩285,408 → 28.5만원 (반올림)")
    check(man_won("₩264,950") == "26.5만원", "₩264,950 → 26.5만원 (반올림, .5 올림)")
    check(man_won("₩530,369") == "53.0만원", ".0 도 남김")
    check(man_won("₩16,708,960") == "1,670.9만원", "천만원 이상은 쉼표")
    check(man_won("#N/A") is None, "숫자가 아니면 None")
    n = "VID_OG_UIN_TNB_MIX_Influencer_Partnership_abellyc_1080x1920_2m49s_ID"
    check(account_label(n) == "[Partnership_abellyc]", "계정명")
    check(account_label(n, True) == "[Partnership_abellyc_2m49s]", "계정명 + 길이 (ID)")
    check(account_label("VID_X_Partnership_qimahmad-2_1080x1920_34s_MS") == "[Partnership_qimahmad-2]", "-2 접미사 유지")
    check(account_label("IMG_OG_UIN_ALL_MASK_Product") is None, "Partnership 없으면 None")
    check(classify_memo("> ROAS/유입 우수", "hi")[:2] == ("both", "hi"), "ROAS/유입 우수 → 유입&구매 우수")
    check(classify_memo(">ROAS 저조", "lo")[:2] == ("pur", "lo"), ">ROAS 저조 → 구매 저조")
    check(classify_memo("> 유입 저조", "lo")[:2] == ("in", "lo"), "> 유입 저조 → 유입 저조")
    check(classify_memo("", "hi")[2] is not None, "메모 없으면 경고")
    _, grade, warn = classify_memo("> 유입 저조", "hi")
    check(grade == "hi" and warn, "메모·체크 반대면 체크 기준 + 경고")


def plans(work):
    print("[2] 계획")
    inp = work / "input"
    br_fixture.write_my(inp / "10월 리포트 (09_21-10_18) - MY_PR&BR.csv")
    br_fixture.write_id(inp / "10월 리포트 (09_21-10_18) - ID_PR&BR.csv")
    my = plan_deck("MY", "PR", parse_blocks(read_csv(inp / "10월 리포트 (09_21-10_18) - MY_PR&BR.csv")))
    check(len(my.br) == 1, "MY: #N/A 블록은 건너뛰고 BR 1장")
    b = my.br[0]
    check(b.title == "MY Shopee 브랜딩 파트너십 캠페인 우수 <> 저조 소재", f"MY 제목: {b.title}")
    check([g.title for g in b.groups] == ["▼ 평균 대비 유입 효율 (CTR, CPC) 우수 소재", "▼ 평균 대비 유입 효율 (CTR, CPC) 저조 소재",
                                          "▼ 평균 대비 유입 & 구매 효율 우수 소재", "▼ 평균 대비 구매 효율(ROAS) 저조 소재"], "MY 블록 순서·제목")
    both = b.groups[2].cards[0]
    check(both.kpi == ["소진량 167.1만원 / CTR 2.81% / CPC 50원", "구매 248건 / ROAS 527%"], f"유입&구매 KPI 2줄: {both.kpi}")
    check(b.groups[3].cards[0].kpi == ["소진량 112.3만원 / 구매 168건 / ROAS 407%"], "구매 KPI")
    check(both.account == "[Partnership_tester1]", "MY 계정명 (길이 없음)")
    check(b.note.startswith("* Traffic, Purchase"), "MY 주석")
    check(b.table.title == "▼ Shopee-CPAS <Partnership> 소재별 주요 성과 (총 10건)", f"MY 표 제목 (라벨 별칭): {b.table.title}")
    check(b.table.rows[0][1][0] == "₩1,670,896", "표 값은 시트 문자열 그대로")
    check(len(my.slides) == 2, "PR 장표도 그대로 (우수 1 / 저조 1)")

    idp = plan_deck("ID", "PR", parse_blocks(read_csv(inp / "10월 리포트 (09_21-10_18) - ID_PR&BR.csv")))
    check(not idp.slides and len(idp.br) == 1, "ID: PR 없이 BR 만")
    b = idp.br[0]
    check(b.title == "ID Shopee 브랜딩 파트너십-Routine 캠페인 우수 소재", f"ID 제목: {b.title}")
    check([g.title for g in b.groups] == ["▼ ID Partnership-Routine 캠페인 소진량 최상위 소재",
                                          "▼ ID Partnership-Routine 캠페인 평균 대비 유입 효율 (CTR, CPC) 우수 소재"], "ID 블록")
    check(b.groups[0].cards[0].account == "[Partnership_tester1_2m49s]", "ID 계정명 (길이 포함)")
    check(b.groups[1].cards[1].kpi == ["소진량 126.0만원 / CTR 3.71% / CPC 47원"], "ID KPI")
    check(b.table.title == "▼ Shopee-CPAS <Partnership-Routine> 소재 지출 금액 TOP 10", "ID 표 제목 (실제 행 수)")
    check(b.note == "", "ID 주석 없음")


def end_to_end(work):
    print("[3] 생성 → pptx·HTML → 대조")
    if not any(lay.name == "MY - BR" for lay in Presentation(str(ROOT / "template" / "EAST_template.pptx")).slide_layouts):
        raise AssertionError("양식에 BR 레이아웃이 없습니다: python tools/add_br_template.py")
    out = work / "output"
    r = subprocess.run([sys.executable, str(ROOT / "run.py"), "--input", str(work / "input"), "--images", str(work / "images"),
                        "--out", str(out), "--created", "2026-10-20"], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout)
    check(r.returncode == 0, "run.py 성공")
    my, idf = out / "SKIN1004_26-10_EAST_MY_PR.pptx", out / "SKIN1004_26-10_EAST_ID_PR.pptx"
    check(my.exists() and idf.exists(), "MY·ID PR 파일 생성 (ID 는 BR 만 있어도 생성)")
    d = deck_slides(str(my))
    layouts = [x["layout"] for x in d]
    check(layouts.count("MY - BR") == 2, "MY: BR 간지 + BR 장표")
    br = [x for x in d if x["layout"] == "MY - BR" and x["br_cards"]][0]
    check(len(br["br_cards"]) == 4 and len(br["tables"]) == 1 and len(br["tables"][0]["cells"]) == 11, "BR 카드 4 + 표 1(10행)")
    texts = [sh.text_frame.text for sh in br["slide"].shapes if sh.has_text_frame]
    check(not any("서브헤더" in t for t in texts), "코멘트 박스 없음")
    check(sum(1 for sh in br["slide"].shapes if sh.shape_type == 13) == 1, "이미지 있는 카드 1개는 그림으로 교체")
    check("이미지 없음: VID_OG_UIN_TNB_MIX_Influencer_Partnership_tester2" in r.stdout, "이미지 없는 카드는 로그")
    di = deck_slides(str(idf))
    check([x["layout"] for x in di][:3] == ["EAST", "ID - OG", "ID - BR"], "ID: PR 간지 없이 BR 간지")
    html = (out / "SKIN1004_26-10_EAST_MY_PR.html").read_text(encoding="utf-8")
    check("MY - BR" in html and "[Partnership_tester1]" in html and "소진량 167.1만원" in html, "HTML 에 BR 장표")

    # 대조: 생성물 자신을 FN 으로 쓰면 0건, 소진량만 살짝 다르면 '참고', 크게 다르면 불일치
    fn = work / "fake_FN.pptx"
    shutil.copy(my, fn)
    p = Presentation(str(fn))
    for s in p.slides:
        for sh in s.shapes:
            if sh.has_text_frame:
                for para in sh.text_frame.paragraphs:
                    for run in para.runs:
                        run.text = run.text.replace("167.1만원", "1.7백만원").replace("153.4만원", "15.3만원")
    p.save(str(fn))
    g = verify.group_cards(str(my))[("MY", "BR")]
    f = verify.group_cards(str(fn))[("MY", "BR")]
    ok, issues, notes = verify.compare_br_cards(g["cards"], f["cards"])
    check(ok == 3 and len(issues) == 1 and "153.4만원" in issues[0], f"소진량 10배 차이 → 불일치 1건 ({issues})")
    check(len(notes) == 1 and "1.7백만원" in notes[0], "1.7백만원 vs 167.1만원 → 참고")
    cell_ok, ti = verify.compare_tables(g["tables"], f["tables"])
    check(not ti and cell_ok == 110, "BR 표 110칸 일치")

    # FN 이 BR 장표에 PR 레이아웃을 쓴 경우에도 BR 로 알아보는지 (실제 9월 FN 에서 BR 이 0장으로 잡혔던 문제)
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    fn2 = work / "fake_FN_pr_layout.pptx"
    p = Presentation(str(my))
    pr = next(lay for lay in p.slide_layouts if lay.name == "MY - PR")
    for s in p.slides:
        if s.slide_layout.name == "MY - BR":
            for rel in s.part.rels.values():
                if rel.reltype == RT.SLIDE_LAYOUT:
                    rel._target = pr.part
    p.save(str(fn2))
    f2 = verify.group_cards(str(fn2))
    check(len(f2[("MY", "BR")]["cards"]) == 4 and len(f2[("MY", "BR")]["tables"]) == 1, "PR 레이아웃의 BR 장표도 BR 로 분류")
    check(len(f2[("MY", "PR")]["tables"]) == 1, "PR 표는 PR 로 남음")

    # 실제 9월 FN 형식: 계정명 + KPI 가 한 글상자, 소진량은 손 변환(1.6백만원, 33만원), 계정명에 공백
    from pptx.util import Inches
    from pptx_read import slide_br_cards
    p = Presentation(str(my))
    s = p.slides.add_slide(p.slide_layouts[0])
    tb = s.shapes.add_textbox(Inches(1), Inches(4), Inches(3), Inches(0.6))
    tb.text_frame.text = "[Partnership_ tester1]"
    for line in ("소진량 1.6백만원 / CTR 2.81% / CPC 50원", "구매 248건 / ROAS 527%"):
        para = tb.text_frame.add_paragraph()
        para.add_run().text = line
    fc = slide_br_cards(s)
    check(len(fc) == 1 and fc[0]["account"] == "[Partnership_ tester1]" and fc[0]["kpi"].startswith("소진량 1.6백만원"),
          "한 글상자의 계정명·KPI 를 나눠 읽음")
    gen1 = [c for c in g["cards"] if c["account"] == "[Partnership_tester1]"]
    ok, issues, notes = verify.compare_br_cards(gen1, [dict(fc[0], slide=99)])
    check(ok == 1 and not issues and len(notes) == 1, f"계정명 공백은 같은 것으로, 1.6백만원은 참고 1건 ({notes})")


def main():
    work = Path(tempfile.mkdtemp(prefix="br_test_"))
    try:
        (work / "images").mkdir()
        from PIL import Image
        Image.new("RGB", (1080, 1920), (120, 160, 200)).save(
            work / "images" / "VID_OG_UIN_TNB_MIX_Influencer_Partnership_tester1_1080x1920_34s_MS.png")
        unit()
        plans(work)
        end_to_end(work)
        print("\n모두 통과")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
