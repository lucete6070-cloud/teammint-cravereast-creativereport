"""appsscript/ 의 붙여넣기용 파일을 다시 만든다: plan.js/build.js → *_js.html, config/labels.json → labels_js.html.
사용: python tools/make_appsscript.py   (plan.js·build.js·labels.json 을 고친 뒤 실행)"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "appsscript"
for n in ("plan", "build"):
    (A / f"{n}_js.html").write_text("<script>\n" + (A / f"{n}.js").read_text(encoding="utf-8") + "\n</script>\n", encoding="utf-8")
cfg = json.loads((ROOT / "config" / "labels.json").read_text(encoding="utf-8"))
(A / "labels_js.html").write_text("<script>\n// config/labels.json 과 같은 내용 (tools/make_appsscript.py 로 생성)\nvar CR_LABELS = "
                                  + json.dumps(cfg, ensure_ascii=False, indent=1) + ";\n</script>\n", encoding="utf-8")
print("appsscript/: plan_js.html, build_js.html, labels_js.html 갱신")
