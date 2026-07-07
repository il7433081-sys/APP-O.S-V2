@echo off
set "NGROK_EXE="

for /f "delims=" %%i in ('where ngrok 2^>nul') do (
    if not defined NGROK_EXE set "NGROK_EXE=%%i"
)

if not defined NGROK_EXE if exist "%LOCALAPPDATA%\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" (
    set "NGROK_EXE=%LOCALAPPDATA%\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"
)

if not defined NGROK_EXE if exist "%ProgramFiles%\ngrok\ngrok.exe" (
    set "NGROK_EXE=%ProgramFiles%\ngrok\ngrok.exe"
)

if not defined NGROK_EXE (
    echo [ERRO] ngrok nao encontrado.
    echo Instale com: winget install ngrok.ngrok
    echo Depois rode este arquivo de novo.
    pause
    exit /b 1
)

exit /b 0
