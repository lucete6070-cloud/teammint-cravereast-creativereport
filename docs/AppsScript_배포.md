# Apps Script 웹 앱 갱신 (설치 없이 주소로 쓰는 방식)

웹 앱 코드는 저장소의 `appsscript/` 폴더에 있다. Apps Script 편집기의 파일과 이름이 1:1 로 같다.

| 저장소 파일 | 편집기 파일 | 직접 고치나 |
|---|---|---|
| `appsscript/Code.gs` | Code.gs | 직접 |
| `appsscript/Index.html` | Index.html | 직접 |
| `appsscript/plan_js.html` | plan_js.html | 직접 (파이썬 `src/plan.py`, `src/plan_br.py` 와 같게) |
| `appsscript/build_js.html` | build_js.html | 직접 (파이썬 `src/build.py` 와 같게) |
| `appsscript/labels_js.html` | labels_js.html | **생성** — `python tools/make_appsscript.py` |
| `appsscript/template_js.html` | template_js.html | **생성** — `python tools/make_appsscript.py` (양식 pptx 를 base64 로 넣음) |
| `appsscript/appsscript.json` | (프로젝트 설정) | 거의 안 바뀜 |

## 갱신 순서 (지윤님)
1. 바뀐 파일을 연다 (GitHub 에서 받은 ZIP 을 풀어 메모장으로 열거나, GitHub 파일 화면의 "Raw").
2. 내용 전체 선택(`Ctrl+A`) → 복사(`Ctrl+C`).
3. Apps Script 편집기에서 같은 이름의 파일을 열고 전체 선택 → 붙여넣기(`Ctrl+V`) → 저장(`Ctrl+S`). 바뀐 파일마다 반복.
4. 오른쪽 위 **배포 → 배포 관리 → (연필) 수정 → 버전: 새 버전 → 배포**. (새 배포를 만들면 주소가 바뀌므로 꼭 "배포 관리"에서 기존 배포를 수정)
5. 웹 앱 주소를 새로고침 → 왼쪽 위 버전이 바뀌었는지 확인.

권한을 새로 쓰는 코드가 들어간 경우에만: 편집기에서 함수 `authorize` 를 한 번 실행해 승인한 뒤 4번.

## 2.1.4 (11/05) — 긴 소재명
- 바뀐 파일: Code.gs, build_js.html (2개)
- 상세 효율표·BR 표의 소재명 칸: 한 줄에 안 들어갈 이름만 그 칸 글씨를 줄여 한 줄로 (기본 9pt → 최소 6.5pt). 최소 글씨로도 넘칠 때만 로그 경고

## 2.1.3 (11/05) — 상세 효율표
- 바뀐 파일: Code.gs, plan_js.html, build_js.html (3개)
- 상세 효율표 두 개가 겹치던 문제: 머리글을 양식·FN 표기 `(장바구니)` 로 줄이고, 아래 표를 위 표의 실제 높이(긴 소재명 줄바꿈 추정) 밑으로 내림. 장 밖으로 넘칠 것 같으면 로그에 경고
- 표에서 카탈로그 소재가 빠지던 문제: 카탈로그는 카드에서만 빼고 TOP10 표에는 넣는다 (10월 SG RT FN 기준)

## 2.1.2 (11/05) — 이미지 그림 효과
- 바뀐 파일: Code.gs, build_js.html (2개)
- 넣은 이미지에 양식 '소재 이미지' 사각형의 그림 효과(바깥쪽 그림자 – 오프셋: 오른쪽 아래)를 그대로 적용 (OG·PR·BR 모든 이미지)

## 2.1.1 (11/05) — 10월 최종본 대조 오류 2건
- 바뀐 파일: Code.gs, plan_js.html, build_js.html (3개)
- 상시 구매(오른쪽) 우수+저조 합계 ≤5 면 한 장 `… 구매 효율 우수 <> 저조 소재`. 캠페인(RT, UA-LIN …)마다 배경·라벨 하나, 카드 위에 '구매 효율 우수/저조' 표시 (10월 SG FN 형식)
- 체크박스가 둘 다 비었는데 메모에 '우수'/'저조' 하나만 있으면 메모대로 넣고 로그에 "체크 누락 보정" 경고 (10월 MY RT `Product_Comparison_3` 사례)
- 프로모션(PR) 장표의 우수+저조 합치기는 그대로(따로) — FN 확인 전 [미확인]

## 2.1.0 (11/04) — BR(브랜딩 파트너십) 장표
- 바뀐 파일: Code.gs, Index.html, plan_js.html, build_js.html, labels_js.html, template_js.html (6개)
- `PR&BR` 탭 오른쪽 블록의 체크로 BR 간지 + BR 장표 생성 (파이썬과 같은 결과, `tests/test_br.py` 의 가짜 데이터로 대조)
- BR 카드 캡처 2장: 1번은 자동 수집(세로형으로 잘림), 2번은 화면 3단계 "직접 넣을 이미지"에 `소재명_2.png` 로 올림
- 양식: 코드에 포함된 양식(`template_js`, BR 레이아웃 포함)을 우선 사용. 스크립트 속성 `TEMPLATE_FILE_ID`(드라이브 양식)는 포함 양식이 없을 때만 쓴다
- 이미지 검색 결과에 썸네일이 없을 때 나던 오류(`body` 미정의) 수정

## 시험 (개발자)
웹 앱 코드는 Node 에서도 돌아간다 (`module.exports`). 파이썬과 같은 결과인지 확인하려면 가짜 데이터(`tests/br_fixture.py`)로 양쪽을 만들어 `verify.py` 의 비교 함수로 대조한다.
