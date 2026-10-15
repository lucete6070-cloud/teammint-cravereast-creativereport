"""체크된 소재의 이미지를 Meta 광고관리자(API)에서 받아 images/소재명.png|jpg 로 저장한다 (P1-2).

사용법:
    python fetch_images.py --dry-run     # 받을 소재 목록만 보기 (토큰 불필요)
    python fetch_images.py               # 이미 images/ 에 있는 소재는 건너뛰고 나머지를 내려받기
준비: .env.example 을 .env 로 복사해 META_ACCESS_TOKEN 과 국가별 광고계정(META_AD_ACCOUNT_ID_MY, _SG ...)을 채운다 (.env 는 git 제외).
국가별 칸이 없으면 META_AD_ACCOUNT_ID(쉼표로 여러 개 가능)를 쓴다.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from build import ImageIndex  # noqa: E402
from meta_api import DEFAULT_VERSION, MetaClient, MetaError, ext_for, load_env, pick_ad, safe_name  # noqa: E402
from plan import plan_deck  # noqa: E402
from run import find_inputs  # noqa: E402
from sheet import EncodingProblem, parse_blocks, read_csv  # noqa: E402


def needed_names(input_dir):
    """[(국가, 소재명)] — 같은 소재명이 여러 국가에 있으면 먼저 나온 국가 한 번만 (이미지 파일이 이름 하나로 저장되므로)."""
    names, seen = [], set()
    for cc, kind, p in find_inputs(input_dir):
        plan = plan_deck(cc, kind, parse_blocks(read_csv(p)))
        for cs in plan.slides:
            for s in cs.slots:
                if s.name.casefold() not in seen:
                    seen.add(s.name.casefold())
                    names.append((cc, s.name))
    return names


def main(argv=None, client_factory=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=str(ROOT / "input"))
    ap.add_argument("--images", default=str(ROOT / "images"))
    ap.add_argument("--env", default=str(ROOT / ".env"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="이미 있는 이미지도 다시 받기")
    a = ap.parse_args(argv)
    try:
        names = needed_names(a.input)
    except EncodingProblem as e:
        print(e)
        return 2
    have = ImageIndex(a.images)
    todo = [(cc, n) for cc, n in names if a.force or not have.find(n)]
    print(f"체크된 소재 {len(names)}개 중 이미지 필요 {len(todo)}개 (이미 있음 {len(names) - len(todo)}개)")
    if a.dry_run:
        for cc, n in todo:
            print(f"  - [{cc}] {n}")
        return 0
    if not todo:
        return 0
    env = load_env(a.env)

    def default_factory(cc):
        ids = env.get(f"META_AD_ACCOUNT_ID_{cc}") or env.get("META_AD_ACCOUNT_ID")
        return MetaClient(env.get("META_ACCESS_TOKEN"), ids, version=env.get("META_GRAPH_VERSION", DEFAULT_VERSION),
                          base=env.get("GRAPH_BASE_URL"))

    factory = client_factory or default_factory
    clients = {}
    Path(a.images).mkdir(exist_ok=True)
    ok, fail = 0, []
    for cc, n in todo:
        try:
            if cc not in clients:
                try:
                    clients[cc] = factory(cc)
                except MetaError:
                    clients[cc] = None
                    print(f"[건너뜀] {cc}: .env 에 META_ACCESS_TOKEN 또는 META_AD_ACCOUNT_ID_{cc} 가 없습니다.")
            client = clients[cc]
            if client is None:
                fail.append((n, f"{cc} 광고계정 ID 없음"))
                continue
            ads = client.find_ads(n)
            ad = pick_ad(ads, n)
            if not ad:
                fail.append((n, "광고명 검색 결과 없음"))
                continue
            url, how = client.image_url_for(ad)
            if not url:
                fail.append((n, "광고에 이미지/썸네일 없음"))
                continue
            data, ctype = client.download(url)
            (Path(a.images) / f"{safe_name(n)}{ext_for(ctype, data)}").write_bytes(data)
            ok += 1
            print(f"  받음 [{cc}/{how}] {n}")
        except MetaError as e:
            fail.append((n, str(e)))
            if "190" in str(e) or "OAuth" in str(e):   # 토큰 만료·무효면 더 시도하지 않는다
                print("[멈춤] 토큰이 만료됐거나 권한이 없습니다. 새 토큰을 .env 에 넣어 주세요.")
                break
    print(f"\n완료: {ok}개 저장, 실패 {len(fail)}개")
    for n, why in fail:
        print(f"  실패: {n} — {why}")
    return 0 if not fail else 3


if __name__ == "__main__":
    sys.exit(main())
