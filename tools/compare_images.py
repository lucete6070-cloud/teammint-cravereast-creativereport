"""images/ 의 이미지가 FN(정답지)에 들어간 같은 소재의 이미지와 같은 그림인지 자동 점검한다.

사용법:  python tools/compare_images.py --fn reference/xxx_FN.pptx
         (images/ 폴더의 소재명.png|jpg 를 FN 슬라이드의 같은 소재명 이미지와 비교)
방식: 그림을 작게 줄여 밝기 변화 패턴(dHash 256비트)을 비교한다. 크기·압축 차이와, FN 에서 사람이 최대 약 15% 잘라 쓴 경우까지
      (images/ 쪽을 100·95·90·85·80% 중앙 크롭으로 여러 번 비교해 가장 가까운 값 사용) 같은 그림으로 본다.
결과: 일치 / 다름(의심) / FN 에 없음 으로 나눠 보여 준다. 사람이 최종 확인할 대상만 좁혀 주는 용도다.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from PIL import Image, ImageOps  # noqa: E402
from pptx import Presentation  # noqa: E402

from extract_fn_images import csv_names, iter_fn_images  # noqa: E402

HASH = 16            # 16x16 → 256비트
SAME = 0.20          # 비트 차이 20% 이하면 같은 그림. 합성 테스트(9월 이미지 40장): 같은 그림 최대 4%, 서로 다른 그림 최소 36% [추정: 실제 Meta↔FN 쌍은 미검증]
SCALES = (1.0, 0.95, 0.90, 0.85, 0.80)


def dhash(im, size=HASH):
    im = ImageOps.exif_transpose(im).convert("L")
    w, h = im.size
    s = min(w, h)                                   # 정사각 중앙 크롭 (양식도 정사각)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((size + 1, size), Image.LANCZOS)
    px = list(im.tobytes())
    bits = []
    for r in range(size):
        row = px[r * (size + 1):(r + 1) * (size + 1)]
        bits += [row[c] > row[c + 1] for c in range(size)]
    return bits


def distance(a, b):
    return sum(x != y for x, y in zip(a, b)) / len(a)


def best_distance(im, ref):
    """im 을 여러 크롭 단계로 잘라 본 해시 중 ref 와 가장 가까운 거리."""
    w, h = im.size
    s = min(w, h)
    best = 1.0
    for sc in SCALES:
        cs = int(s * sc)
        x, y = (w - cs) // 2, (h - cs) // 2
        best = min(best, distance(dhash(im.crop((x, y, x + cs, y + cs))), ref))
    return best


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fn", default=str(next((ROOT / "reference").glob("*FN*.pptx"), "")))
    ap.add_argument("--images", default=str(ROOT / "images"))
    a = ap.parse_args(argv)
    if not Path(a.fn).is_file():
        print("[멈춤] --fn 으로 FN pptx 경로를 알려 주세요.")
        return 1
    known = set()
    try:
        known = csv_names()
    except Exception:
        pass
    fn = {}
    for _, name, im in iter_fn_images(Presentation(a.fn), known):
        if name:
            fn.setdefault(name.casefold(), (name, dhash(im)))
    ok, bad, missing = [], [], []
    for p in sorted(Path(a.images).iterdir()):
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        ref = fn.get(p.stem.casefold())
        if not ref:
            missing.append(p.stem)
            continue
        with Image.open(p) as im:
            d = best_distance(im.convert('RGB'), ref[1])
        (ok if d <= SAME else bad).append((p.stem, d))
    print(f"비교 결과: 같은 그림 {len(ok)}개 / 다른 그림 의심 {len(bad)}개 / FN 에 없는 소재 {len(missing)}개")
    for n, d in sorted(bad, key=lambda x: -x[1]):
        print(f"  ⚠ 다름(차이 {d:.0%}) {n}")
    for n in missing:
        print(f"  - FN 에 없음 {n}")
    return 0 if not bad else 3


if __name__ == "__main__":
    sys.exit(main())
