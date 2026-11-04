"""Apps Script 웹 앱(appsscript/)의 자동 생성 파일 두 개를 저장소 내용으로 다시 만든다.

- appsscript/template_js.html : template/EAST_template.pptx 를 base64 로 넣은 것 (BR 레이아웃·간지 포함)
- appsscript/labels_js.html   : config/labels.json 과 같은 내용

양식이나 라벨 설정이 바뀌면 이 스크립트를 돌리고, 두 파일을 Apps Script 편집기에 붙여넣은 뒤 "배포 관리 → 새 버전".
사용법:  python tools/make_appsscript.py
"""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "appsscript"


def main():
    tpl = ROOT / "template" / "EAST_template.pptx"
    b64 = base64.b64encode(tpl.read_bytes()).decode()
    (OUT / "template_js.html").write_text(
        "<script>\n"
        "// template/EAST_template.pptx 를 base64 로 넣은 것 (tools/make_appsscript.py 로 생성). 양식이 바뀌면 다시 생성해 붙여넣는다.\n"
        f'var CR_TEMPLATE_NAME = "{tpl.name}";\n'
        f'var CR_TEMPLATE_B64 = "{b64}";\n'
        "</script>", encoding="utf-8")
    labels = json.loads((ROOT / "config" / "labels.json").read_text(encoding="utf-8"))
    (OUT / "labels_js.html").write_text(
        "<script>\n// config/labels.json 과 같은 내용 (tools/make_appsscript.py 로 생성)\n"
        f"var CR_LABELS = {json.dumps(labels, ensure_ascii=False, indent=1)};\n</script>", encoding="utf-8")
    print(f"만들었습니다: template_js.html ({len(b64) // 1024} KB), labels_js.html")


if __name__ == "__main__":
    main()
