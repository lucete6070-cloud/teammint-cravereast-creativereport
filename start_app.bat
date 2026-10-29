@echo off
chcp 65001 >nul
cd /d "%~dp0"
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
echo 웹 화면을 엽니다. 이 검은 창은 닫지 마세요 (닫으면 화면도 꺼집니다).
echo Đang mở màn hình web. Đừng đóng cửa sổ đen này (đóng là màn hình cũng tắt).
%PY% app.py
echo.
pause
