@echo off
chcp 65001 >nul
python run.py
if errorlevel 1 (echo.
 echo 위 메시지를 확인해 주세요.)
pause
