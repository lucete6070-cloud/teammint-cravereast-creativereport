"""FN 에서 뽑은 extracted.json 이 FN 원문과 맞는지 점검한다 (소재명·KPI 는 원문에 그대로 있어야 한다).

사용: python check_extract.py extracted.json FN원문.txt [FN원문2.txt ...]
  FN원문.txt : FN PDF/pptx 에서 뽑은 텍스트 (드라이브 커넥터 결과 저장본이나 pdftotext 결과). 여러 개면 합쳐서 본다.
문제가 없으면 '추출 점검 통과', 있으면 목록을 출력하고 종료 코드 1.
"""
import json
import re
import sys
from pathlib import Path

COUNTRIES = {"MY", "SG", "ID", "PH"}
KINDS = {"OG", "PR"}
FUNNELS = {"유입", "구매"}
CLASSES = ("우수", "저조", "혼합")


QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "′": "'", "＇": "'"})


def norm(t):
    t = t.replace("\\", "").translate(QUOTES)
    return re.sub(r"\s+", "", t)


def load_text(path):
    raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            raw = d.get("fileContent") or d.get("content") or raw
    except json.JSONDecodeError:
        pass
    return norm(raw)


def check(data, text):
    out = []
    if not re.fullmatch(r"\d{2}-\d{2}", data.get("month", "")):
        out.append("month 는 'YY-MM' (예: 26-11)")
    if not data.get("slides"):
        out.append("slides 가 비어 있음")
    for i, s in enumerate(data.get("slides", []), 1):
        tag = f"슬라이드 {i} ({s.get('title', '')[:30]})"
        if s.get("country") not in COUNTRIES:
            out.append(f"{tag}: country {s.get('country')!r}")
        if s.get("kind") not in KINDS:
            out.append(f"{tag}: kind {s.get('kind')!r} (OG/PR)")
        if s.get("funnel") not in FUNNELS:
            out.append(f"{tag}: funnel {s.get('funnel')!r} (유입/구매)")
        if not s.get("comment"):
            out.append(f"{tag}: comment(FN 코멘트 본문) 없음")
        for line in s.get("comment", []) + ([s["arrow"]] if s.get("arrow") else []):
            probe = norm(line)[:25]
            if probe and probe not in text:
                out.append(f"{tag}: 코멘트 줄이 원문에서 안 보임 — '{line[:30]}…' (줄 앞부분 25자 기준)")
        if not s.get("slots"):
            out.append(f"{tag}: slots 없음")
        for k, sl in enumerate(s.get("slots", []), 1):
            st = f"{tag} 슬롯{k}"
            if not str(sl.get("cls", "")).startswith(CLASSES):
                out.append(f"{st}: cls {sl.get('cls')!r} (우수/저조/혼합으로 시작)")
            if norm(sl.get("name", "")) not in text:
                out.append(f"{st}: 소재명이 원문에 없음 — {sl.get('name')}")
            for part in [p for p in sl.get("kpi", "").split("/") if p.strip()]:
                if norm(part) not in text:
                    out.append(f"{st}: KPI 조각이 원문에 없음 — '{part.strip()}'")
            if not sl.get("gist"):
                out.append(f"{st}: gist(코멘트 요지) 없음")
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    text = "".join(load_text(p) for p in sys.argv[2:])
    probs = check(data, text)
    n = sum(len(s.get("slots", [])) for s in data.get("slides", []))
    print(f"{data.get('month')} / 슬라이드 {len(data.get('slides', []))}장 / 슬롯 {n}개")
    for p in probs:
        print(f"  - {p}")
    print("추출 점검 통과" if not probs else f"점검 항목 {len(probs)}건")
    sys.exit(1 if probs else 0)


if __name__ == "__main__":
    main()
