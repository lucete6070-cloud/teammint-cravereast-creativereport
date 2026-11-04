"""초안 자동 점검 (작성형식·리뷰어규칙 중 기계로 볼 수 있는 것).

사용: python check_drafts.py 작업폴더   (작업폴더/slides.json, 작업폴더/drafts.json 필요)
문제가 없으면 '점검 통과', 있으면 슬라이드별 목록을 출력하고 종료 코드 1.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ENDINGS = ["양상", "경향성", "확인", "기록", "판단", "사료", "해석", "가능성", "견인", "유도", "약화", "유지", "추정", "분석"]
ARROW_ENDINGS = ["필요", "제언", "의견", "제안", "검토", "권장"]
ASSERT = [r"때문", r"원인은", r"이다\.?$", r"했다\.?$", r"한다\.?$"]
NUM = re.compile(r"₩[\d,]+|(RM|Rp|S?\$|₱|P)\s?[\d][\d,.]*|\d[\d,.]*\s*%p?|\d[\d,.]*(원|만원|건)")
MAX_LEN = 110


def numbers_in(text):
    return {m.group(0).replace(" ", "").rstrip(".,") for m in NUM.finditer(text)}


def check(slide, draft):
    out = []
    body, arrow = draft.get("body", []), draft.get("arrow", "")
    allowed = set()
    for s in slide["slots"]:
        allowed |= numbers_in(s["kpi"]) | numbers_in(s["name"])
    allowed |= numbers_in(" ".join(draft.get("allowed_numbers", [])))
    if not 2 <= len(body) <= 4:
        out.append(f"본문 줄 수 {len(body)} (2~4줄)")
    if not arrow:
        out.append("▶ 줄 없음")
    ends = []
    for i, line in enumerate(body + ([arrow] if arrow else []), start=1):
        t = line.strip()
        tag = "▶" if arrow and line is arrow else f"{i}줄"
        if t.endswith(".") or t.endswith("다"):
            out.append(f"{tag}: '~다.' 종결 — 명사형으로")
        if t.endswith(",") or t.endswith("며") or t.endswith("고"):
            out.append(f"{tag}: 미완성 문장(쉼표·연결어미로 끝남)")
        for pat in ASSERT:
            if re.search(pat, t):
                out.append(f"{tag}: 단정 표현 의심 ('{pat}') — R1")
        if len(t) > MAX_LEN:
            out.append(f"{tag}: {len(t)}자 (최대 {MAX_LEN}자)")
        bad = numbers_in(t) - allowed
        if bad:
            out.append(f"{tag}: 슬라이드 KPI 에 없는 숫자 {sorted(bad)} — 계산·추측 금지 (카피 인용이면 allowed_numbers 에 근거 기입)")
        e = next((w for w in ENDINGS + ARROW_ENDINGS if t.rstrip(" .").endswith(w)), None)
        if e:
            ends.append(e)
    for w, n in Counter(ends).items():
        if n >= 3:
            out.append(f"같은 어미 '{w}' {n}회 반복")
    if arrow and not any(arrow.rstrip(" .").endswith(w) for w in ARROW_ENDINGS):
        out.append("▶ 줄이 처방형 어미(필요·제언·의견·제안·검토·권장)로 끝나지 않음")
    return out


def main():
    work = Path(sys.argv[1])
    slides = {s["slide_no"]: s for s in json.loads((work / "slides.json").read_text(encoding="utf-8"))}
    drafts = json.loads((work / "drafts.json").read_text(encoding="utf-8"))
    bad = 0
    for d in drafts:
        s = slides.get(d["slide_no"])
        if s is None:
            print(f"#{d['slide_no']}: slides.json 에 없는 슬라이드")
            bad += 1
            continue
        probs = check(s, d)
        if probs:
            bad += 1
            print(f"#{d['slide_no']} {s['title']}")
            for p in probs:
                print(f"  - {p}")
    missing = set(slides) - {d["slide_no"] for d in drafts}
    if missing:
        print(f"초안이 없는 슬라이드: {sorted(missing)}")
        bad += 1
    print("점검 통과" if not bad else f"점검 항목 있는 슬라이드 {bad}장")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
