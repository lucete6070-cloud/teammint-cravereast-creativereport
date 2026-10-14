# EAST Creative Report 생성기 (P1-1 MVP)

시트 국가 탭 CSV + 소재 이미지 → 국가×유형(OG/PR)별 pptx 초안. 작업 규칙은 `CLAUDE.md`, 설계는 `docs/SPEC.md`.

## 실행 (복사해서 붙여넣기)
```
pip install -r requirements.txt     # 처음 한 번만
python run.py                       # 또는 run.bat 더블클릭
python verify.py                    # reference/ 의 FN 과 대조 (불일치 목록 출력)
```
1. `input/` 에 국가 탭 CSV(`MY_OG&TEST.csv`, `MY_PR&BR.csv` …, UTF-8)를 넣는다. 파일명에 `(08_24-09_20)` 같은 데이터 기간이 있어야 한다.
2. `images/` 에 `소재명.png|jpg` 로 이미지를 넣는다 (없으면 회색 사각형 + 로그에 "이미지 없음").
3. `output/` 에 pptx, 같은 이름의 .html(보기용, 글꼴 걱정 없이 브라우저에서 열림) 과 `생성로그.txt` 가 생긴다. CSV 글자가 깨져 있으면 아무것도 만들지 않고 멈춘다.

## 폴더
`template/` 양식(+TOP10 표) · `input/ images/ reference/ output/ .env` 는 git 제외(광고주 데이터) · `config/labels.json` 라벨 이름 바꾸기 · `src/` 코드 · `tools/` 개발용(양식 만들기, FN 이미지 추출)

## 이번 범위 밖
BR(파트너십), 콜아웃, 코멘트(빈 박스 유지), Meta API 이미지 수집(P1-2)
