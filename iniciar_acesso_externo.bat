@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

call "%~dp0_resolver_ngrok.bat"
if errorlevel 1 goto :fim

set "NGROK_DOMAIN="
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
        if /i "%%a"=="NGROK_DOMAIN" if not "%%b"=="" set "NGROK_DOMAIN=%%b"
    )
)

echo.
echo ============================================================
echo   Ordem de Servico - Acesso externo (4G / outra rede)
echo ============================================================
echo.

"%NGROK_EXE%" config check >nul 2>&1
if errorlevel 1 goto :ngrok_nao_configurado

echo Atualizando ngrok se necessario...
"%NGROK_EXE%" update >nul 2>&1

echo Encerrando servidores antigos na porta 5000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000" ^| findstr LISTENING') do (
    taskkill /F /PID %%p >nul 2>&1
)
echo Encerrando tuneis ngrok antigos neste PC...
taskkill /F /IM ngrok.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo.
echo [1/2] Abrindo SERVIDOR (janela: OS Digital - Servidor)...
start "OS Digital - Servidor" cmd /k "cd /d "%~dp0" && echo Servidor Flask - mantenha esta janela aberta && python app.py"

echo Aguardando o servidor Flask na porta 5000...
call "%~dp0_aguardar_flask.bat"
if errorlevel 1 goto :flask_falhou
echo Servidor Flask OK.

echo [2/2] Abrindo TUNEL ngrok (esta janela)...
echo.
if defined NGROK_DOMAIN (
    echo URL publica: https://%NGROK_DOMAIN%
    echo Se esta janela fechar sozinha, leia a mensagem de erro abaixo.
    echo.
    "%NGROK_EXE%" http 5000 --url=https://%NGROK_DOMAIN% --pooling-enabled
) else (
    echo Quando aparecer a URL https://..., o QR Code ja funciona em 4G.
    echo.
    "%NGROK_EXE%" http 5000
)

echo.
echo O tunel ngrok encerrou. Veja a mensagem acima.
echo.
echo Se apareceu ERR_NGROK_334 (endpoint ja online):
echo   - Feche outro PC que use o mesmo dominio ngrok, OU
echo   - Acesse https://dashboard.ngrok.com/endpoints e encerre o tunel antigo, OU
echo   - Rode este .bat de novo (agora encerra ngrok local antes de abrir).
pause
goto :fim

:flask_falhou
echo.
echo [ERRO] O servidor Flask NAO respondeu em http://127.0.0.1:5000
echo Veja a janela "OS Digital - Servidor" - deve haver erro em vermelho do Python.
echo Corrija o erro, feche tudo e rode este .bat de novo.
echo.
pause
exit /b 1

:ngrok_nao_configurado
echo [AVISO] ngrok ainda nao configurado neste PC.
echo Rode configurar_ngrok.bat uma vez antes de continuar.
echo.
pause
exit /b 1

:fim
endlocal
