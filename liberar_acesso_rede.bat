@echo off
chcp 65001 >nul
echo.
echo Liberando porta 5000 no Firewall (TODAS as redes: Privada + Publica)...
echo Execute como Administrador (clique direito ^> Executar como administrador).
echo.

netsh advfirewall firewall delete rule name="Flask OS Porta 5000" >nul 2>&1
netsh advfirewall firewall add rule name="Flask OS Porta 5000" dir=in action=allow protocol=TCP localport=5000 profile=any enable=yes

if %errorlevel% equ 0 (
    echo OK - Porta 5000 liberada em qualquer tipo de rede.
    echo.
    echo Seu IP na rede Wi-Fi:
    for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do echo   http://%%a:5000
    echo.
    echo No celular: mesma Wi-Fi, com http:// no inicio. Nao use 4G.
) else (
    echo ERRO - Execute como Administrador.
)

echo.
pause
