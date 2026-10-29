@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== 처음 한 번만: 설치 / Chỉ làm một lần: cài đặt =====
echo %~dp0 | findstr /i "OneDrive" >nul && (
  echo [주의] 이 폴더가 OneDrive 안에 있습니다. 광고주 데이터와 토큰이 클라우드로 올라가므로 C:\creative-report 로 옮겨 주세요.
  echo [LƯU Ý] Thư mục này nằm trong OneDrive. Dữ liệu quảng cáo và token sẽ bị tải lên đám mây. Hãy chuyển sang C:\creative-report.
  pause
  exit /b 1
)
set PY=
rem 윈도우 기본 "python" 은 스토어로 연결만 하는 가짜일 수 있어, 실제로 실행되는지로 확인한다
python -c "import sys" >nul 2>nul && set PY=python
if "%PY%"=="" py -3 -c "import sys" >nul 2>nul && set PY=py -3
if "%PY%"=="" (
  echo [오류] Python 이 설치돼 있지 않습니다. 열리는 사이트에서 Python 을 설치하세요. 설치 첫 화면에서 "Add python.exe to PATH" 에 꼭 체크!
  echo [LỖI] Chưa cài Python. Hãy cài Python từ trang web vừa mở. Ở màn hình cài đặt đầu tiên nhớ tick "Add python.exe to PATH"!
  start https://www.python.org/downloads/
  pause
  exit /b 1
)
echo.
echo [1/3] 필요한 부품 설치 / Cài thư viện ...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo [오류] 부품 설치에 실패했습니다. 위 영어 메시지를 캡처해 지윤님께 보내 주세요. / [LỖI] Cài thư viện thất bại. Chụp màn hình thông báo tiếng Anh ở trên gửi cho Jiyoon.
  pause
  exit /b 1
)
echo.
echo [2/3] 폴더 만들기 / Tạo thư mục ...
if not exist input mkdir input
if not exist images mkdir images
if not exist images_manual mkdir images_manual
if not exist output mkdir output
echo.
echo [3/3] 토큰 파일(.env) / File token (.env) ...
if not exist .env (
  copy .env.example .env >nul
  echo 메모장이 열립니다. 지윤님께 받은 토큰과 광고계정 ID 를 = 뒤에 붙여넣고 저장(Ctrl+S) 후 닫으세요.
  echo Notepad sẽ mở. Dán token và ID tài khoản (nhận từ Jiyoon) sau dấu =, lưu (Ctrl+S) rồi đóng.
  notepad .env
)
echo.
%PY% check.py
echo.
pause
