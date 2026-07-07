@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ============================================
echo   Ordem de Servico Digital - Servidor
echo ============================================
echo.
echo Encerrando servidores antigos na porta 5000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000" ^| findstr LISTENING') do (
    taskkill /F /PID %%p >nul 2>&1
)
timeout /t 2 /nobreak >nul
echo.
echo Seu IP na rede Wi-Fi:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do echo   http://%%a:5000
echo.
echo No celular/tablet: use o endereco acima (mesma Wi-Fi).
echo Apos abrir a pagina, use Ctrl+F5 para atualizar sem cache.
echo.
python app.py
pause
