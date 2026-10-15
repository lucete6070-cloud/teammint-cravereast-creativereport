# 서버 배포 요청 (복사해서 보내는 용도)

안녕하세요. 광고 소재 리포트(Creative Report) 초안을 만드는 사내 도구를 보조 인력들이 설치 없이 쓰도록, 웹 주소로 올리려고 합니다. 아래 두 가지만 도와 주실 수 있을까요?

**1. Google Cloud 프로젝트 하나**
- 결제 계정 연결 (사용량이 적어 월 몇 달러 이하 예상)
- 아래 API 사용 설정: Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Google Sheets API
- 제가(또는 배포 담당자가) 다음을 할 수 있는 권한: Cloud Run 배포, OAuth 클라이언트 생성, Secret 생성

**2. 팀민트 구글 계정 전용 로그인**
- OAuth 동의 화면을 "내부(Internal)"로 설정 (팀민트 계정만 사용 가능)
- 시트 읽기 전용 권한(`spreadsheets.readonly`) 사용 허용

**데이터 취급**
- 광고주 성과 CSV(시트)와 소재 이미지가 서버를 지나가며, 작업이 끝나거나 3시간이 지나면 자동 삭제됩니다. 별도 저장은 하지 않습니다.
- 접속은 @team-mint.io 구글 계정 로그인으로만 가능합니다.

자세한 설정 순서는 저장소의 `docs/서버_배포.md` 에 정리되어 있습니다.
