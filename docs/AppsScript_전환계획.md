# Apps Script 웹앱 전환 계획 (설치·서버·결제 없는 방식)

> 작성: 2026-10-25 | 결정: 10/25 지윤님 ("개인 클라우드 비용 없이, 보조는 주소만 열면 되게")
> 표기: [확인됨] 자료·실행으로 확인 / [추정] 근거 있는 추론 / [미확인] 시험으로 확인 필요

---

## 1. 왜 바꾸나 (한 줄)

서버 방식(Cloud Run, `docs/서버_배포.md`)은 결제 카드가 묶인 Google Cloud 프로젝트가 있어야 하는데 회사에 그게 없다. Google Workspace에 이미 들어 있는 **Apps Script**로 같은 화면을 올리면 결제·서버·IT 승인 없이 보조가 주소만 열어 쓸 수 있다.

| | 파이썬 패키지(현재 P3) | 서버(Cloud Run) | **Apps Script 웹앱** |
|---|---|---|---|
| 보조가 설치할 것 | Python + ZIP | 없음 | 없음 |
| 돈·결제 카드 | 없음 | 필요 | 없음 |
| 회사 인프라 승인 | 없음 | 필요 | 없음 (워크스페이스 기본 기능) |
| 토큰을 보조가 보나 | 봄 (.env 입력) | 안 봄 | 안 봄 (스크립트 속성에 보관) |
| 팀민트 계정만 접속 | 해당 없음 | OAuth 설정 필요 | 배포 옵션 체크 한 번 |
| 새로 만들 코드 | 없음 | 없음 | pptx 생성부를 JS로 재작성 |
| Windows 스마트 앱 컨트롤 차단 | 겪음 [확인됨] | 무관 | 무관 (브라우저만 사용) |

---

## 2. 목표 구조

```
[보조 브라우저]                              [Apps Script (구글 안에서 실행)]
 주소 열기 → 팀민트 계정 자동 확인  ◀──────  HtmlService: 화면(web/index.html 재사용)
 시트 주소 붙여넣기 ─────────────────────▶  readTabs(sheetId): 국가 탭을 '표시된 값' 그대로 읽음
 국가 선택 → [생성]                          fetchImage(country, name): Meta Graph API 호출 (토큰은 서버 속성)
   ├ 시트 값 → 슬라이드 계획 (plan.js)       getTemplate(): 양식 pptx를 base64로 전달
   ├ 이미지 정사각 크롭 (canvas)
   ├ 양식 pptx 열어 XML 수정 (JSZip, build.js)
   └ 완성 pptx 다운로드 + 생성로그 표시
```

- **브라우저가 하는 일**: 시트 값 해석, 슬라이드 계획, 이미지 크롭, pptx 조립, 다운로드. 광고주 데이터는 브라우저 메모리에만 있고 Drive 등에 저장하지 않는다.
- **Apps Script가 하는 일**: 로그인 확인, 시트 읽기, Meta 이미지 받아 넘기기, 양식 파일 전달. 토큰은 **스크립트 속성(Script Properties)** 에만 두고 코드·로그에 쓰지 않는다.
- **유지하는 규칙**: `CLAUDE.md` 1~6 (숫자 문자열 그대로, 체크박스만, ≤5 한 장, 사각형 위치에 크롭 교체, SKU 뒤 줄바꿈, 코멘트 비움)은 그대로 적용한다.
- **검증 기준은 그대로**: 생성된 pptx를 지윤님 PC에서 `python verify.py`로 9월 FN과 대조한다. 파이썬 쪽 코드는 개발·검증 도구로 남긴다.

---

## 3. 하루 시험 (본 작업 전 반드시 통과)

실행자: 지윤님 (Apps Script는 구글 계정이 있어야 해서 개발 환경에서 대신할 수 없음). 각 항목 30분~1시간.
스크립트는 **지윤님 개인 계정이 아니라 팀 공용 계정**으로 만드는 것을 권장한다 (담당자 변경 대비). 공용 계정이 없으면 일단 개인 계정으로 시험하고 본 작업 때 옮긴다.

| # | 시험 | 하는 법 | 통과 기준 | 상태 |
|---|---|---|---|---|
| T1 | 팀민트 계정만 접속 | script.google.com → 새 프로젝트 → `doGet`이 "안녕" 반환 → 배포 > 웹앱 > "실행: 나", "액세스: team-mint.io 사용자" | 팀민트 계정은 열리고 gmail 계정은 거부 | [미확인] |
| T2 | 시트 읽기 | `SpreadsheetApp.openById(id).getSheets()` 중 `MY_OG&TEST` 등 → `getDataRange().getDisplayValues()` | `₩910,734` / `6.92%` / `TRUE` / `#N/A` 가 CSV 다운로드와 같은 글자로 나옴 | [미확인] |
| T3 | Meta 이미지 수집 시간 | `UrlFetchApp.fetch(graph.facebook.com/...)` 로 9월 체크 소재 38개 받기, 토큰은 스크립트 속성에서 읽음. 소재 1개당 호출 1회로 설계 | 1회 호출이 6분 제한 안 (예상 수 초) · 38개 전부 수집 · 로그에 토큰 없음 | [미확인] |
| T4 | 브라우저에서 pptx 만들기 | HtmlService 화면에 JSZip(CDN) 넣고 양식 pptx(base64) 열기 → 슬라이드 XML에서 글자 1개 바꾸기 → `Blob` 다운로드 | PowerPoint에서 열리고 바뀐 글자가 보임 | [미확인] |
| T5 | 이미지 크롭·삽입 | T4에 이어 canvas로 정사각 크롭 → `ppt/media/`에 추가 → `소재 이미지` 사각형 자리에 `<p:pic>` 삽입 | 사각형 위치·크기와 같은 자리에 이미지가 들어감 | [미확인] |
| T6 | 큰 데이터 왕복 | 이미지 1장(약 100~500KB)을 base64로 서버→브라우저 전달 | 끊김 없이 받아짐. 안 되면 이미지를 Drive 임시 폴더에 두고 주소로 전달하는 대안 검토 | [미확인] |

T1~T3는 서버 쪽, T4~T6는 브라우저 쪽이라 **반나절씩 나눠** 해도 된다. 하나라도 실패하면 본 작업에 들어가기 전에 개발 쪽에 그 화면을 보내 대안을 정한다.

### 시험용 코드 조각 (복사해서 붙여넣기)
`doGet` + T2 시트 읽기 최소 예:
```javascript
function doGet() {
  return HtmlService.createHtmlOutput('<p>안녕 ' + Session.getActiveUser().getEmail() + '</p>');
}
function readTabs(sheetId) {
  var out = {};
  SpreadsheetApp.openById(sheetId).getSheets().forEach(function (sh) {
    var t = sh.getName();
    if (/^[A-Za-z]{2}_(OG&TEST|PR&BR)$/.test(t)) out[t] = sh.getDataRange().getDisplayValues();
  });
  return out;
}
```
T3 Meta 호출 최소 예 (토큰은 **프로젝트 설정 > 스크립트 속성**에 `META_ACCESS_TOKEN`으로 넣고, 코드·채팅에 쓰지 않는다):
```javascript
function metaGet(path, params) {
  var token = PropertiesService.getScriptProperties().getProperty('META_ACCESS_TOKEN');
  var q = Object.keys(params).map(function (k) { return k + '=' + encodeURIComponent(params[k]); }).join('&');
  var res = UrlFetchApp.fetch('https://graph.facebook.com/v21.0/' + path + '?' + q + '&access_token=' + token,
                              { muteHttpExceptions: true });
  return JSON.parse(res.getContentText());
}
```

---

## 4. 본 작업 범위 (시험 통과 후)

### 4-1. 파이썬 → JS 대응표
| 파이썬 (현재) | 줄 수 | JS (새로) | 비고 |
|---|---|---|---|
| `src/sheet.py` CSV 읽기·블록 파싱 | 107 | `sheet.js` | CSV 대신 T2의 2차원 배열을 입력으로. 인코딩 검사는 불필요(시트에서 직접 읽음) |
| `src/plan.py` 슬라이드 계획 | 202 | `plan.js` | 그대로 옮김. `config/labels.json`은 스크립트에 포함 |
| `src/pptx_util.py` 도형 복제·글자 교체 | 117 | `pptx_util.js` | lxml → DOMParser/XMLSerializer. run 단위 교체 규칙 유지 |
| `src/build.py` 덱 조립 | 272 | `build.js` | python-pptx 없이 슬라이드 XML·rels·`[Content_Types].xml`을 직접 다룸. **가장 큰 작업** |
| `src/meta_api.py` 광고 검색·선택 규칙 | 197 | `Code.gs` (서버) | 선택 규칙(소재명 시작 > 기간 겹침 > ACTIVE > 이미지 > 시작일) 그대로 |
| `src/sheets_source.py` | 77 | `Code.gs` | `SpreadsheetApp`으로 대체, 대폭 줄어듦 |
| `web/index.html` 화면 | 207 | 재사용 | `fetch('/api/…')` → `google.script.run` 으로 바꿈 |
| `src/html_out.py` 보기용 HTML | 132 | 선택 | 화면에서 바로 미리보기 가능하면 생략 |
| `verify.py`, `check.py`, `tools/` | | 유지 (파이썬) | 검증·진단은 지윤님 PC에서 계속 사용 |

### 4-2. 작업 순서와 기간 [추정]
1. 시험 T1~T6 (1일)
2. `sheet.js` + `plan.js` 옮기고, 9월 시트로 계획 결과가 파이썬과 같은지 비교 (2일)
3. `build.js`: 표지·간지·3/4/5슬롯·분할 배경·TOP10 표 (4~5일)
4. 서버 쪽 `Code.gs`: 시트 읽기, 이미지 수집, 양식 전달, 로그 (1~2일)
5. 화면 연결, 한국어/베트남어, 생성로그 표시 (1일)
6. 9월 데이터로 생성 → `verify.py` 대조 → 불일치 0건까지 수정 (1~2일)
7. 보조 1명과 리허설, `GUIDE.html` 갱신 (반나절)

합계 약 2주. 파이썬 버전으로 이미 규칙이 전부 확정돼 있어 "무엇을 만들지" 고민은 없고 "옮기기"만 있다.

---

## 5. 운영 (전환 후)

| 일 | 누가 | 하는 법 |
|---|---|---|
| 매월 생성 | 보조 | 주소 열기 → 시트 주소 붙여넣기 → 담당 국가 체크 → 생성 → 다운로드 |
| 토큰 갱신 (약 60일) | 지윤 | Apps Script 편집기 > 프로젝트 설정 > 스크립트 속성에서 `META_ACCESS_TOKEN` 값 교체. 화면에 "발급 50일 경과" 안내가 뜨도록 `META_TOKEN_ISSUED`도 함께 적음 |
| 프로그램 수정 | 개발 → 지윤 | 코드 붙여넣기 → 배포 > 배포 관리 > 새 버전. 주소는 바뀌지 않음 |
| 접근 제한 | 자동 | team-mint.io 계정만. 보조 퇴사 시 워크스페이스 계정 정지로 끝 |
| 데이터 취급 | 자동 | 시트 값·이미지는 브라우저 메모리에만. Drive·스크립트에 저장하지 않음. 실행 로그에 토큰·광고주 수치 남기지 않음 |

---

## 6. 알아둘 제약과 대응

- **서버 호출 1회 6분 제한** [확인됨: Apps Script 공식 한도] → 이미지는 소재 1개당 1회 호출. 브라우저가 순서대로 부른다.
- **하루 UrlFetch 호출 한도** (워크스페이스 계정 기준 수만 회) [추정] → 월 수백 회 수준이라 여유.
- **화면은 HtmlService 샌드박스 안에서 실행** → 외부 라이브러리(JSZip)는 CDN 주소로 넣는다. 파일 다운로드는 `Blob` + 링크 클릭으로 처리 (T4에서 확인).
- **동시 사용**: 보조 3명이 같은 날 써도 각자 브라우저에서 생성하므로 서로 섞이지 않는다.
- **글꼴**: pptx 조립만 하므로 글꼴 문제 없음. PowerPoint가 연다.
- **영상 소재**: 파이썬 버전과 같이 광고 기본 썸네일 사용 (큰 썸네일은 앱 권한 부족 [확인됨: SPEC 4장]).
- **양식 pptx 보관**: 스크립트 프로젝트 안에 base64 문자열로 넣거나, 공용 Drive 폴더에 두고 `DriveApp`으로 읽음. 공용 Drive 쪽이 양식 교체가 쉬움 [추정].

---

## 7. 지윤님이 정할 것

1. **스크립트 소유 계정**: 개인 계정 vs 팀 공용 계정. 공용 권장.
2. **양식 pptx 위치**: 공용 Drive 폴더 (권장) vs 스크립트 내장.
3. **보조별 국가 제한 여부**: 지금은 화면에서 본인이 체크. 계정별로 국가를 고정할지.
4. **회사 공용 Google Cloud 프로젝트 안건**: 이번 도구는 Apps Script로 피해 가지만, 앞으로의 자동화를 위해 `docs/IT_요청문.md`를 별도 안건으로 올릴지.

---

## 8. 기존 문서·코드와의 관계

- `docs/운영_프로세스.md` (방식 A: 보조 각자 PC) → 전환 완료 전까지 **예비 수단**으로 유지.
- `docs/서버_배포.md`, `docs/IT_요청문.md` → **보류**. 회사 공용 클라우드가 생기면 다시 꺼낸다.
- `app.py`(로컬·서버 모드), `run_all.py`, `.bat` → 유지. 지윤님 PC 개발·검증용.
- `verify.py` → 전환 후에도 **정답 대조 도구**로 계속 사용.
