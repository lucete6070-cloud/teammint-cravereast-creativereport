"""슬라이드 계획(plan)을 보기용 HTML 한 파일로 만든다 (이미지는 파일 안에 포함, 글꼴 걱정 없이 브라우저에서 열림).

pptx 와 같은 plan 에서 만들기 때문에 KPI·소재명·표 값이 항상 같다. 편집·코멘트는 pptx 에서 한다.
"""
import base64
import io
from html import escape
from pathlib import Path

from PIL import Image

from build import ImageIndex
from pptx_util import split_sku

CSS = """
:root{--brown:#947645;--beige:#ddd0bb;--ink:#222;--line:#e4dccd;--green:#e2f0d9;--pink:#fadadd;--bg:#ecebe7}
@media (prefers-color-scheme:dark){:root{--bg:#1d1d1d}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);font-family:Pretendard,"Noto Sans KR","Malgun Gothic","Apple SD Gothic Neo",sans-serif;color:var(--ink)}
.wrap{max-width:1280px;margin:0 auto;padding:16px}
h1.doc{font-size:15px;font-weight:600;margin:4px 0 12px;color:#777}
.slide{position:relative;width:100%;aspect-ratio:16/9;background:#fff;margin:0 0 18px;overflow:hidden;box-shadow:0 1px 6px rgba(0,0,0,.18);container-type:inline-size}
.chip{position:absolute;left:3.6cqw;top:2.2cqw;font-size:1cqw;color:#333}
.brand{position:absolute;right:3.6cqw;top:2.2cqw;font-size:1.2cqw;font-weight:800}
.rule{position:absolute;left:3.6cqw;right:3.6cqw;top:4cqw;border-top:1px solid #ddd}
.title{position:absolute;left:3.6cqw;top:5.6cqw;font-size:2.2cqw}
.comment{position:absolute;left:4.2cqw;right:4.2cqw;top:10.8cqw;height:8cqw;border:1px dashed #ddd;border-radius:4px;color:#bbb;font-size:1cqw;padding:.6cqw 1cqw}
.cards{position:absolute;left:3.2cqw;right:3.2cqw;top:22cqw;bottom:2cqw;display:flex;gap:.3cqw}
.panel{flex:1 1 0;display:flex;flex-direction:column;border:1px solid var(--line);border-radius:2.2cqw;background:#fdfbf7;padding:0 .8cqw 1cqw;min-width:0}
.panel.g{flex-grow:var(--n)}
.plabel{align-self:center;background:var(--brown);color:#fff;font-size:1.05cqw;padding:.25cqw 1.2cqw;margin-top:-.4cqw}
.grp{display:flex;flex:1;justify-content:space-around;min-width:0}
.card{flex:1 1 0;display:flex;flex-direction:column;align-items:center;min-width:0;padding:0 .4cqw}
.lab{background:var(--brown);color:#fff;font-size:1.05cqw;padding:.25cqw .8cqw;margin:-.4cqw 0 .8cqw;max-width:100%;text-align:center}
.img{width:min(100%,var(--s));aspect-ratio:1;background:#d9d9d9;display:flex;align-items:center;justify-content:center;color:#888;font-size:1cqw;overflow:hidden}
.img img{width:100%;height:100%;object-fit:cover}
.kpi{font-size:.85cqw;margin-top:.7cqw;text-align:center;color:#c44}
.nm{font-size:.8cqw;margin-top:.3cqw;text-align:center;word-break:break-all;line-height:1.25}
.divider{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#fff;font-size:2cqw}
.divider span{padding:0 3cqw;position:relative}
.divider span:before{content:"/";position:absolute;left:0}.divider span:after{content:"/";position:absolute;right:0}
.cover{background:#fff}.cover h2{position:absolute;left:5cqw;top:19cqw;font-size:3cqw;margin:0;font-weight:500}
.cover .bar{position:absolute;left:5cqw;top:25cqw;width:28cqw;border-top:.5cqw solid var(--brown)}
.cover .pd{position:absolute;left:5cqw;top:26.3cqw;font-size:1.1cqw}.cover .dt{position:absolute;left:5cqw;top:29cqw;font-size:1.4cqw}
table{position:absolute;left:4.2cqw;width:calc(100% - 8.4cqw);border-collapse:collapse;font-size:.8cqw}
th{background:#111;color:#fff;font-weight:600;padding:.2cqw .3cqw}
td{border:1px solid #bbb;padding:.2cqw .3cqw;text-align:right;white-space:nowrap}td:first-child{text-align:left;white-space:normal;word-break:break-all}
th:first-child{text-align:center}
tr.hi td{background:var(--green)}tr.lo td{background:var(--pink)}
.th{position:absolute;left:4.2cqw;font-size:1cqw;font-weight:600}
.sub{position:absolute;left:4.2cqw;top:10.8cqw;font-size:1cqw}
"""


def _data_uri(path, size=520):
    """정사각 중앙 크롭 후 줄여 JPEG 로 포함 (파일 크기 절약)."""
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        s = min(w, h)
        im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((size, size))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _card(sp, imgs, size):
    img = imgs.find(sp.name)
    body = f'<img src="{_data_uri(img)}" alt="">' if img else "소재 이미지"
    nm = "<br>".join(escape(x) for x in split_sku(sp.name))
    return (f'<div class="card"><div class="lab">{escape(sp.label)}</div>'
            f'<div class="img" style="--s:{size}cqw">{body}</div>'
            f'<div class="kpi">{escape(" / ".join(sp.kpi))}</div><div class="nm">{nm}</div></div>')


def _content(cc, kind, cs, imgs):
    n = len(cs.slots)
    size = {3: 20, 4: 18.4, 5: 16}.get(max(3, min(5, n)), 16)
    if cs.split:
        hi = "".join(_card_nolabel(s, imgs, size) for s in cs.slots[:cs.n_hi])
        lo = "".join(_card_nolabel(s, imgs, size) for s in cs.slots[cs.n_hi:])
        cards = (f'<div class="panel g" style="--n:{cs.n_hi}"><div class="plabel">{escape(cs.group_labels[0])}</div><div class="grp">{hi}</div></div>'
                 f'<div class="panel g" style="--n:{cs.n_lo}"><div class="plabel">{escape(cs.group_labels[1])}</div><div class="grp">{lo}</div></div>')
    else:
        cards = f'<div class="panel"><div class="grp" style="padding-top:.8cqw">{"".join(_card(s, imgs, size) for s in cs.slots)}</div></div>'
    return (f'<section class="slide"><div class="chip">{cc} - {kind}</div><div class="brand">teammint</div><div class="rule"></div>'
            f'<div class="title">{escape(cs.title)}</div><div class="comment">코멘트 (비워 둠)</div><div class="cards">{cards}</div></section>')


def _card_nolabel(sp, imgs, size):
    html = _card(sp, imgs, size)
    start = html.index('<div class="lab">')
    end = html.index("</div>", start) + 6
    return html[:start] + html[end:]


def _table_slide(cc, kind, specs):
    zone = "상시" if kind == "OG" else "프로모션"
    parts = [f'<section class="slide"><div class="chip">{cc} - {kind}</div><div class="brand">teammint</div><div class="rule"></div>'
             f'<div class="title">SKIN1004 {cc} {zone} 캠페인별 우수 소재 상세 효율</div>'
             f'<div class="sub">구매 효율 우수 소재 (*지출 상위 소재 중 평균 대비 ROAS 및 구매 CVR 우수 소재)</div>']
    tops = (14.2, 36.5)
    for i, sp in enumerate(specs):
        head = "".join(f"<th>{escape(h)}</th>" for h in ["소재명"] + sp.headers)
        rows = "".join(f'<tr class="{c}">' + "".join(f"<td>{escape(v)}</td>" for v in [n] + vals) + "</tr>" for n, vals, c in sp.rows)
        parts.append(f'<div class="th" style="top:{tops[i] - 2.2}cqw">▼ &lt;{escape(sp.label)}&gt; 소재 지출 금액 TOP {len(sp.rows)}</div>'
                     f'<table style="top:{tops[i]}cqw"><tr>{head}</tr>{rows}</table>')
    parts.append("</section>")
    return "".join(parts)


def _divider(cc, kind, text, color):
    return (f'<section class="slide" style="background:{color}"><div class="chip" style="color:#fff">{cc} - {kind}</div>'
            f'<div class="divider"><span>{escape(text)}</span></div></section>')


def write_html(plan, meta, images_dir, out_path):
    cc, kind = plan.country, plan.kind
    imgs = ImageIndex(images_dir)
    sm, sd, em, ed = meta["period"]
    cover = (f'<section class="slide cover"><h2>SKIN1004 EAST {em:02d}월 Creative Report</h2><div class="bar"></div>'
             f'<div class="pd">데이터 기준 : {sm:02d}/{sd:02d} - {em:02d}/{ed:02d}</div>'
             f'<div class="dt">{meta["yy"]}-{meta["created"].month:02d}-{meta["created"].day:02d} / PERFORMANCE ARCHITECT</div></section>')
    slides = [cover, _divider(cc, "OG", cc, "#947645"), _divider(cc, kind, kind, "#ddd0bb")]
    slides += [_content(cc, kind, cs, imgs) for cs in plan.slides]
    slides += [_table_slide(cc, kind, plan.tables[i:i + 2]) for i in range(0, len(plan.tables), 2)]
    slides.append(_divider(cc, kind, "E.O.D.", "#947645"))
    html = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>SKIN1004 {cc} {kind} Creative Report</title><style>{CSS}</style></head><body><div class="wrap">'
            f'<h1 class="doc">SKIN1004 EAST {em:02d}월 Creative Report · {cc} {kind} (보기용 · 편집은 pptx)</h1>{"".join(slides)}</div></body></html>')
    Path(out_path).write_text(html, encoding="utf-8")
    return out_path
