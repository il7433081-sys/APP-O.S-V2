@echo off
REM Aguarda ate 30s o Flask responder em http://127.0.0.1:5000
for /L %%i in (1,1,30) do (
    ping 127.0.0.1 -n 2 >nul
    powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5000/' -TimeoutSec 2).StatusCode | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 exit /b 0
)
exit /b 1
