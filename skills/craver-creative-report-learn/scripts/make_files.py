"""extracted.json → 드라이브에 올릴 월간 파일 2개.

사용: python make_files.py extracted.json 출력폴더
출력:
  소재이력_YY-MM.md  : 국가별 소재 이력 표 (기존 소재이력_MY/SG/ID/PH.md 와 같은 열) + 연속성 메모
  FN코멘트_YY-MM.md  : 슬라이드별 FN 코멘트 원문 (다음 달 코멘트 스킬이 '전월 문장과 겹치지 않게'(R3) 확인용)
"""
import json
import sys
from pathlib import Path

ORDER = ["MY", "SG", "ID", "PH"]


def cell(t):
    return str(t or "").replace("|", "/").replace("\n", " ").strip()


def history(d):
    m = d["month"]
    out = [f"# 소재 이력 — {m[:2]}년 {int(m[3:])}월 추가분",
           "",
           f"- 근거: {', '.join(d.get('sources', [])) or '(FN 파일명 기입)'}. 데이터 기준 {d.get('period', '(기간)')}",
           f"- 작성: {d.get('written', '')} / 국가별 기존 파일(`소재이력_MY/SG/ID/PH.md`)과 이전 `소재이력_YY-MM.md` 뒤에 이어지는 달로 읽는다",
           "- 구분은 슬라이드 제목·슬롯 라벨 기준. 코멘트 요지는 FN 원문 요약. 슬라이드 공통 서술만 있는 슬롯은 \"(슬라이드 공통)\""]
    present = [c for c in ORDER if any(s["country"] == c for s in d["slides"])]
    missing = [c for c in ORDER if c not in present]
    if missing:
        out.append(f"- {'·'.join(missing)}: 이번 달 FN 에 본문 없음")
    out.append("")
    for c in present:
        out += [f"## {c}", "", "| 소재명 | 월 | 유형 | 퍼널 | 캠페인 라벨 | 구분 | 코멘트 요지 |", "|---|---|---|---|---|---|---|"]
        for s in d["slides"]:
            if s["country"] != c:
                continue
            for sl in s["slots"]:
                out.append(f"| {cell(sl['name'])} | {m} | {s['kind']} | {s['funnel']} | {cell(sl.get('label'))} | "
                           f"{cell(sl['cls'])} | {cell(sl.get('gist'))} |")
        out.append("")
    if d.get("continuity"):
        out += [f"## {int(m[3:])}월 연속성 메모 (FN 원문 기준)", "", "| 소재 | FN 표현 |", "|---|---|"]
        out += [f"| {cell(x.get('item'))} | {cell(x.get('fn'))} |" for x in d["continuity"]]
        out.append("")
    return "\n".join(out)


def fn_comments(d):
    m = d["month"]
    out = [f"# FN 코멘트 원문 — {m[:2]}년 {int(m[3:])}월",
           "",
           f"- 근거: {', '.join(d.get('sources', []))}",
           "- 용도: 다음 달 코멘트 초안이 같은 슬라이드의 전월 문장과 겹치지 않게 확인 (리뷰어규칙 R3). 띄어쓰기는 PDF 추출 상태 그대로일 수 있음",
           ""]
    for s in d["slides"]:
        out.append(f"## {s['country']} {s['kind']} — {s['title']}")
        out += [f"- {line}" for line in s.get("comment", [])]
        if s.get("arrow"):
            out.append(f"- ▶ {s['arrow'].lstrip('▶ ').strip()}")
        if s.get("callouts"):
            out.append(f"- 콜아웃: {' / '.join(s['callouts'])}")
        out.append("")
    return "\n".join(out)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    a = out / f"소재이력_{d['month']}.md"
    b = out / f"FN코멘트_{d['month']}.md"
    a.write_text(history(d), encoding="utf-8")
    b.write_text(fn_comments(d), encoding="utf-8")
    n = sum(len(s["slots"]) for s in d["slides"])
    print(f"{a} (슬롯 {n}행)\n{b} (슬라이드 {len(d['slides'])}장)")


if __name__ == "__main__":
    main()
