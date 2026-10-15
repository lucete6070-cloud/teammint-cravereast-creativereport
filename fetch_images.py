"""체크된 소재의 이미지를 Meta 광고관리자(API)에서 받아 images/소재명.png|jpg 로 저장한다 (P1-2).

사용법:
    python fetch_images.py --dry-run     # 받을 소재 목록만 보기 (토큰 불필요)
    python fetch_images.py               # 이미 images/ 에 있는 소재는 건너뛰고 나머지를 내려받기
    python fetch_images.py --candidates 소재명 --country MY   # 진단: 그 소재명이 들어간 광고 후보 보기
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
from run import PERIOD, find_inputs, report_year  # noqa: E402
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


def report_period(input_dir):
    """CSV 파일명의 (08_24-09_20) → (시작일, 끝일) date. 못 읽으면 None."""
    from datetime import date
    for _, _, p in find_inputs(input_dir):
        m = PERIOD.search(p.name)
        if m:
            sm, sd, em, ed = (int(x) for x in m.groups())
            y = report_year(em, ed, date.today())
            return date(y if sm <= em else y - 1, sm, sd), date(y, em, ed)
    return None


def show_candidates(a, client_factory=None):
    cc = (a.country or "").upper()
    if not cc:
        print("[멈춤] --country MY 처럼 국가를 알려 주세요.")
        return 1
    env = load_env(a.env)
    try:
        if client_factory:
            client = client_factory(cc)
        else:
            ids = env.get(f"META_AD_ACCOUNT_ID_{cc}") or env.get("META_AD_ACCOUNT_ID")
            client = MetaClient(env.get("META_ACCESS_TOKEN"), ids, version=env.get("META_GRAPH_VERSION", DEFAULT_VERSION),
                                base=env.get("GRAPH_BASE_URL"))
    except MetaError as e:
        print(f"[멈춤] {e}")
        return 1
    chosen = None
    for acc, ads, err in client.candidates(a.candidates):
        print(f"\n[{cc}] 계정 {acc}: 후보 광고 {len(ads)}개" + (f" (오류: {err[:120]})" if err else ""))
        for ad in ads:
            cr = ad.get("creative") or {}
            kind = "이미지" if cr.get("image_url") else ("영상" if cr.get("video_id") else "썸네일만" if cr.get("thumbnail_url") else "없음")
            note = ""
            if cr.get("video_id"):
                try:
                    note = " / 영상 큰 썸네일 조회 성공" if client.video_thumbnail(cr["video_id"]) else " / 영상 썸네일 없음"
                except MetaError as e:
                    note = f" / 영상 썸네일 조회 실패: {str(e)[:90]}"
            print(f"  - {ad.get('name', '')}  [{ad.get('effective_status', '')}] {kind}{note}")
    period = report_period(a.input)
    best = pick_ad([ad for _, ads, _ in client.candidates(a.candidates) for ad in ads], a.candidates, period)
    if best:
        print(f"\n선택되는 광고: {best.get('name', '')}" + (f"  (보고서 기간 {period[0]} ~ {period[1]} 기준)" if period else "  (보고서 기간을 몰라 날짜 기준 없이 선택)"))
    return 0


def main(argv=None, client_factory=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=str(ROOT / "input"))
    ap.add_argument("--images", default=str(ROOT / "images"))
    ap.add_argument("--env", default=str(ROOT / ".env"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="이미 있는 이미지도 다시 받기")
    ap.add_argument("--candidates", metavar="소재명", help="진단: 소재명이 들어간 광고 후보(광고명·상태·이미지 종류)를 보여 준다")
    ap.add_argument("--country", help="--candidates 와 함께: MY, SG ...")
    a = ap.parse_args(argv)
    if a.candidates:
        return show_candidates(a, client_factory)
    try:
        names = needed_names(a.input)
    except EncodingProblem as e:
        print(e)
        return 2
    have = ImageIndex(a.images)
    todo = [(cc, n) for cc, n in names
            if (a.force and n.casefold() not in have.manual_keys) or (not a.force and not have.find(n))]
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
    period = report_period(a.input)
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
            ad = pick_ad(ads, n, period)
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
