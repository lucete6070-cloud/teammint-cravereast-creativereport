"""판정결과.md 새 버전 만들기: 이번 달 판정 절을 '최신 판정' 자리(기존 판정 절들 위)에 끼워 넣고, 머리말에 갱신 줄을 단다.
변경내역.md 새 버전 만들기: 표 끝에 이번 달 행을 붙인다.

사용:
  python update_judgments.py judgments 기존_판정결과.md 이번달_판정절.md 출력.md "2026-12-03 (11월 FN 반영 N건)"
  python update_judgments.py changelog 기존_변경내역.md 추가행.md 출력.md
  python update_judgments.py next-id 기존_판정결과.md            → 이번 달 판정에 쓸 다음 O-번호
기존 파일은 드라이브 커넥터 저장본(JSON)이어도 된다 (이스케이프를 풀어서 쓴다).

판정절 파일 예 (맨 위 '## ' 제목 포함):
  ## 26년 11월 FN 반영 판정 (2026-12-03, 지윤님 판정)   ← 번호 없이. 기존 절 번호는 그대로 둔다
  | # | 대상 (기존 ID) | 11월 근거 | 판정 | 초안 적용 |
  ...
추가행 파일 예: 변경내역 표 형식의 행들 (| 날짜 | 반영 월 | 파일 | 변경 | 실행 | 판정 |)
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from read_ref import load  # noqa: E402


PRIORITY_OLD = re.compile(r"같은 ID가 이 파일 안에 두 번 있으면[^\n]*")
PRIORITY_NEW = ("같은 주제·ID가 이 파일 안에 여러 번 있으면 **날짜가 최신인 절**을 따른다 "
                "(새 판정 절은 위쪽에 쌓인다).")


def next_o_number(text):
    nums = [int(n) for n in re.findall(r"\bO-(\d+)\b", text)]
    return max(nums, default=0) + 1


def judgments(old, section, stamp):
    lines = old.splitlines()
    # 머리말 갱신 줄
    for i, l in enumerate(lines):
        if re.match(r"^- \d차 작성|^- 1차 작성", l):
            lines[i] = l.rstrip() + f" / 갱신: {stamp}"
            break
    text = PRIORITY_OLD.sub(PRIORITY_NEW, "\n".join(lines))
    # 0장(공통 규칙) 뒤, 그다음 첫 '## ' 앞에 끼워 넣는다 → 최신 판정이 항상 위. 기존 절 번호는 건드리지 않는다.
    zero = re.search(r"^## 0\. ", text, flags=re.M)
    start = zero.end() if zero else 0
    m = re.search(r"^## ", text[start:], flags=re.M)
    sec = section.strip()
    if not sec.startswith("## "):
        sec = "## " + sec.lstrip("# ").strip()
    if not m:
        return text.rstrip() + "\n\n" + sec + "\n"
    pos = start + m.start()
    return text[:pos] + sec + "\n\n" + text[pos:]


def changelog(old, rows):
    lines = old.rstrip().splitlines()
    last = max(i for i, l in enumerate(lines) if l.startswith("|"))
    add = [r for r in rows.strip().splitlines() if r.startswith("|")]
    return "\n".join(lines[:last + 1] + add + lines[last + 1:]) + "\n"


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "next-id":
        print(f"O-{next_o_number(load(sys.argv[2])):02d}")
        return
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    mode, old, new, out = sys.argv[1], load(sys.argv[2]), Path(sys.argv[3]).read_text(encoding="utf-8"), Path(sys.argv[4])
    if mode == "judgments":
        stamp = sys.argv[5] if len(sys.argv) > 5 else "(날짜)"
        out.write_text(judgments(old, new, stamp), encoding="utf-8")
    elif mode == "changelog":
        out.write_text(changelog(old, new), encoding="utf-8")
    else:
        print(__doc__)
        sys.exit(1)
    print(f"→ {out}")


if __name__ == "__main__":
    main()
