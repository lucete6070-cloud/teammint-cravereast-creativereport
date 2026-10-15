"""진단: 소재명이 들어간 광고 후보들의 이미지를 모두 받아, FN 에 들어간 그림과 가장 닮은 광고가 어느 것인지 보여 준다.

사용법:
    python tools\\match_ad_to_fn.py --name "소재명" --country MY --fn "FN pptx 경로(생략하면 reference 폴더)"
무엇을 알 수 있나: FN 작성자가 어느 시기의 광고 이미지를 썼는지 → 광고 선택 규칙을 어떻게 고칠지 정하는 근거.
"""
import argparse
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from PIL import Image  # noqa: E402
from pptx import Presentation  # noqa: E402

from compare_images import best_distance, dhash  # noqa: E402
from extract_fn_images import iter_fn_images  # noqa: E402
from meta_api import DEFAULT_VERSION, MetaClient, MetaError, load_env  # noqa: E402


def rank_ads(client, ads, ref_hash):
    """[(거리, 광고명, 상태, 종류)] 가까운 순. 이미지를 못 받는 광고는 건너뛴다."""
    out = []
    for ad in ads:
        url, how = client.image_url_for(ad)
        if not url:
            continue
        try:
            data, _ = client.download(url)
            with Image.open(io.BytesIO(data)) as im:
                d = best_distance(im.convert("RGB"), ref_hash)
        except Exception:
            continue
        out.append((d, ad.get("name", ""), ad.get("effective_status", ""), how))
    return sorted(out)


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--country", required=True)
    ap.add_argument("--fn", default=str(next((ROOT / "reference").glob("*FN*.pptx"), "")))
    ap.add_argument("--env", default=str(ROOT / ".env"))
    a = ap.parse_args(argv)
    if not Path(a.fn).is_file():
        print("[멈춤] --fn 으로 FN pptx 경로를 알려 주세요.")
        return 1
    ref = None
    for _, nm, im in iter_fn_images(Presentation(a.fn), {a.name}):
        if nm and nm.casefold() == a.name.casefold():
            ref = dhash(im)
            break
    if ref is None:
        print("[멈춤] FN 에서 이 소재명의 이미지를 찾지 못했습니다.")
        return 1
    if client is None:
        env = load_env(a.env)
        cc = a.country.upper()
        try:
            client = MetaClient(env.get("META_ACCESS_TOKEN"), env.get(f"META_AD_ACCOUNT_ID_{cc}") or env.get("META_AD_ACCOUNT_ID"),
                                version=env.get("META_GRAPH_VERSION", DEFAULT_VERSION), base=env.get("GRAPH_BASE_URL"))
        except MetaError as e:
            print(f"[멈춤] {e}")
            return 1
    ads = [ad for _, lst, _ in client.candidates(a.name, limit=50) for ad in lst]
    print(f"후보 광고 {len(ads)}개의 이미지를 FN 그림과 비교합니다 (차이가 작을수록 같은 그림)")
    for d, n, st, how in rank_ads(client, ads, ref)[:12]:
        print(f"  {d:4.0%}  {n}  [{st}] {how}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
