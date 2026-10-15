"""보조에게 전달할 ZIP(dist/creative-report-assistant.zip)을 만든다.

들어가는 것: 실행 파일(setup.bat, run_all.bat), 코드, 양식, 설정, 가이드. 광고주 데이터(input/images/output/reference)와 .env 는 넣지 않는다.
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["setup.bat", "start_app.bat", "run_all.bat", "app.py", "web/index.html", "run_all.py", "check.py", "run.py", "fetch_images.py", "requirements.txt", ".env.example",
         "GUIDE.html", "README.md", "template/EAST_template.pptx", "config/labels.json"]
FOLDERS = ["src"]


def main():
    out = ROOT / "dist" / "creative-report-assistant.zip"
    out.parent.mkdir(exist_ok=True)
    names = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(ROOT / f, f"creative-report/{f}")
            names.append(f)
        for folder in FOLDERS:
            for p in sorted((ROOT / folder).rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    rel = p.relative_to(ROOT).as_posix()
                    z.write(p, f"creative-report/{rel}")
                    names.append(rel)
        for d in ("input", "images", "images_manual", "output"):   # 빈 폴더
            z.writestr(f"creative-report/{d}/.keep", "")
    bad = [n for n in names if n.startswith(("input", "images", "output", "reference")) or n == ".env"]
    assert not bad, bad
    print(f"만들었습니다: {out} ({out.stat().st_size // 1024} KB, 파일 {len(names)}개)")
    return out


if __name__ == "__main__":
    main()
