# EAST Creative Report 생성기 (P1-1 MVP)

시트 국가 탭 CSV + 소재 이미지 → 국가×유형(OG/PR)별 pptx 초안. 작업 규칙은 `CLAUDE.md`, 설계는 `docs/SPEC.md`.

## 방향 (10/25): Apps Script 웹앱으로 전환 검토
서버 방식은 결제 카드가 묶인 Google Cloud 프로젝트가 필요해 보류. 대신 Google Workspace에 포함된 Apps Script 위에 같은 화면을 올리면 설치·서버·결제 없이 보조가 주소만 열면 된다. 하루 시험 항목과 전환 범위는 `docs/AppsScript_전환계획.md`. 아래 서버·로컬·보조용 방식은 전환 전까지 그대로 쓴다.

## 서버 방식 (설치 없이 주소만 열기)
`APP_MODE=server` 로 같은 화면을 서버(Cloud Run)에 올리면 보조는 주소 접속 → 팀민트 구글 로그인 → **구글 시트 주소 붙여넣기** → 생성 → 다운로드만 하면 된다. 사용자별 작업 폴더 분리, 로그아웃/3시간 후 자동 삭제, 토큰은 서버 설정. 올리는 방법은 `docs/서버_배포.md`, 인프라 담당자에게 보낼 요청문은 `docs/IT_요청문.md`.

## 웹 화면 (로컬)
`start_app.bat` 더블클릭 → 브라우저 화면(CSV 끌어놓기, 담당 국가 선택, 생성, 다운로드, 한국어/Tiếng Việt). 코드는 `app.py` + `web/index.html`, 점검·수집·생성은 아래 `run_all` 과 같은 코드를 쓴다. 이 PC 안(127.0.0.1)에서만 접속된다.

## 보조용 (더블클릭) — P3
`setup.bat`(처음 한 번) → 매달 `run_all.bat`. 점검 → Meta 이미지 수집 → pptx/HTML 생성을 한 번에 하고 `output\실행기록_*.txt` 를 남긴다.
자세한 순서(한국어·Tiếng Việt)는 `GUIDE.html`. 보조에게 줄 ZIP 은 `python tools/make_package.py` 로 `dist/creative-report-assistant.zip` 을 만든다(광고주 데이터·`.env` 제외).

## 실행 (개발자용, 복사해서 붙여넣기)
```
pip install -r requirements.txt     # 처음 한 번만
python run.py                       # 또는 run.bat 더블클릭
python verify.py                    # reference/ 의 FN 과 대조 (불일치 목록 출력)
```
1. `input/` 에 국가 탭 CSV(`MY_OG&TEST.csv`, `MY_PR&BR.csv` …, UTF-8)를 넣는다. 파일명에 `(08_24-09_20)` 같은 데이터 기간이 있어야 한다.
2. `images/` 에 `소재명.png|jpg` 로 이미지를 넣는다 (없으면 회색 사각형 + 로그에 "이미지 없음").
3. `output/` 에 pptx, 같은 이름의 .html(보기용, 글꼴 걱정 없이 브라우저에서 열림) 과 `생성로그.txt` 가 생긴다. CSV 글자가 깨져 있으면 아무것도 만들지 않고 멈춘다.

## 이미지 자동 수집 (P1-2)
```
copy .env.example .env              # 열어서 META_ACCESS_TOKEN, META_AD_ACCOUNT_ID 입력 (.env 는 git 제외)
python fetch_images.py --dry-run    # 받을 소재 목록만 확인
python fetch_images.py              # 체크된 소재 중 images/ 에 없는 것만 내려받기
```
광고명에 소재명이 포함된 광고를 찾아 image_url → (영상) 큰 썸네일 → thumbnail_url 순으로 저장한다. 못 찾은 소재는 목록으로 알려 주고, `run.py` 는 그 자리를 회색 사각형으로 남긴다. 토큰은 채팅·문서에 붙여넣지 않는다.
(검증: `python tests/test_meta_mock.py` — 가짜 서버로 전 과정 확인. 실제 Meta 계정 연동은 아직 미확인.)

## 폴더
`template/` 양식(+TOP10 표) · `tools/compare_images.py` 받은 이미지가 FN 의 같은 소재 그림인지 점검 · `input/ images/ reference/ output/ .env` 는 git 제외(광고주 데이터) · `config/labels.json` 라벨 이름 바꾸기 · `src/` 코드 · `tools/` 개발용(양식 만들기, FN 이미지 추출)

## 이번 범위 밖
BR(파트너십), 콜아웃, 코멘트(빈 박스 유지), Meta API 이미지 수집(P1-2)
