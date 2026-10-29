"""슬라이드 노트에 코멘트 근거를 적는다 (코멘트 스킬이 읽는 입력).

- 숫자는 시트 문자열 그대로. 계산하지 않는다.
- 코멘트 박스는 여전히 비워 둔다. 노트의 '스킬 메모' 칸은 스킬이 채운다.
"""
HEADER = "=== 코멘트 근거 (생성기 자동 기입 · 수정하지 마세요) ==="
SKILL = "=== 코멘트 스킬 메모 (초안 근거·플래그·콜아웃 후보) ==="
CLS = {"hi": "우수", "lo": "저조", "mix": "혼합"}


def funnel_of(title):
    return "유입" if "유입" in title else "구매"


def grade_of(cs):
    kinds = {s.cls for s in cs.slots}
    if kinds == {"hi"}:
        return "우수"
    if kinds == {"lo"}:
        return "저조"
    return "우수<>저조"


def render(plan, cs, meta, prev_sources):
    p = meta["period"]
    zone = "상시(OG)" if plan.kind == "OG" else "프로모션(PR)"
    lines = [
        HEADER,
        f"리포트: SKIN1004 EAST {meta['yy']}-{meta['mm']:02d} / 데이터 기간 {p[0]:02d}/{p[1]:02d} - {p[2]:02d}/{p[3]:02d}",
        f"슬라이드: {plan.country} {zone} {funnel_of(cs.title)} / {grade_of(cs)}",
        f"제목: {cs.title.strip()}",
        f"전월 비교 자료: {prev_sources}",
        "",
    ]
    for i, s in enumerate(cs.slots, 1):
        lines.append(f"[슬롯 {i}] {CLS.get(s.cls, s.cls)} | {s.label} | {s.name}")
        if s.cells:
            lines.append("  지표: " + " · ".join(f"{h} {v}" for h, v in s.cells))
        else:
            lines.append("  KPI: " + " / ".join(s.kpi))
        if s.memo:
            lines.append(f"  시트 메모: {s.memo}")
        if s.prev:
            lines.append(f"  전월: {s.prev}")
    lines += ["", SKILL, ""]
    return "\n".join(lines)


def write(slide, text):
    """노트 슬라이드는 양식에 없던 새 개체라 서식 보존 대상이 아니다."""
    slide.notes_slide.notes_text_frame.text = text
