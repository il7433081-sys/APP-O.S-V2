@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ============================================================
echo   Configurar ngrok (apenas uma vez por PC)
echo ============================================================
echo.
echo 1. Crie conta gratuita em: https://dashboard.ngrok.com/signup
echo 2. Acesse: https://dashboard.ngrok.com/get-started/your-authtoken
echo 3. Copie o Authtoken e cole abaixo quando pedir.
echo.

call "%~dp0_resolver_ngrok.bat"
if errorlevel 1 goto :fim

set /p NGROK_TOKEN="Cole seu Authtoken do ngrok: "
if "%NGROK_TOKEN%"=="" goto :token_vazio

"%NGROK_EXE%" config add-authtoken %NGROK_TOKEN%
if errorlevel 1 goto :falha_token

echo.
echo ngrok configurado com sucesso!
echo Agora use: iniciar_acesso_externo.bat
echo.
pause
goto :fim

:token_vazio
echo Nenhum token informado. Cancelado.
pause
exit /b 1

:falha_token
echo.
echo Falha ao configurar. Verifique o token e tente novamente.
pause
exit /b 1

:fim
endlocal
