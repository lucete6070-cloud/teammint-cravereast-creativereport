"""드라이브 커넥터가 크다고 파일로 저장한 참고 파일(JSON)을 읽기 쉬운 md 로 풀고, 필요한 부분만 찾는다.

사용:
  python read_ref.py 저장된파일 출력.md                 → md 로 풀기 (\\#, \\_, \\| 같은 이스케이프 제거)
  python read_ref.py 출력.md --find 소재명1 소재명2 ...   → 소재명이 들어간 줄만 (앞뒤 표 머리글 포함)
  python read_ref.py 출력.md --ids P-MY-01 J-03 ...       → 패턴·판정 ID 가 들어간 단락만
  python read_ref.py 출력.md --toc                        → 제목(#) 목록과 줄 번호
"""
import json
import re
import sys
from pathlib import Path


def unescape(text):
    return re.sub(r"\\([#_|*\[\]()~>`!-])", r"\1", text).replace("  \n", "\n")


def load(path):
    raw = Path(path).read_text(encoding="utf-8")
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            raw = d.get("fileContent") or d.get("content") or raw
    except json.JSONDecodeError:
        pass
    return unescape(raw)


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(1)
    if len(a) >= 2 and not a[1].startswith("--"):
        text = load(a[0])
        Path(a[1]).write_text(text, encoding="utf-8")
        print(f"{a[1]} ({len(text.splitlines())}줄)")
        return
    lines = Path(a[0]).read_text(encoding="utf-8").splitlines()
    mode, keys = a[1], a[2:]
    if mode == "--toc":
        for i, l in enumerate(lines, 1):
            if l.startswith("#"):
                print(f"{i}: {l}")
    elif mode == "--find":
        header = ""
        for i, l in enumerate(lines, 1):
            if l.startswith("|") and i < len(lines) and re.match(r"^\|[-| ]+\|$", lines[i]):
                header = l
            if any(k.casefold() in l.casefold() for k in keys):
                print(f"   (표 머리글) {header}\n{i}: {l}" if header and l != header else f"{i}: {l}")
    elif mode == "--ids":
        block, hit = [], False
        for l in lines + ["#"]:
            if l.startswith("#"):
                if hit:
                    print("\n".join(block) + "\n")
                block, hit = [l], any(k in l for k in keys)
            else:
                block.append(l)
                hit = hit or (l.startswith("|") and any(re.search(rf"\b{re.escape(k)}\b", l) for k in keys))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
