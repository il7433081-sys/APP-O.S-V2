$ErrorActionPreference = "Stop"
$BuildDir = $PSScriptRoot
$Raiz = Split-Path -Parent $BuildDir
$ExeDist = Join-Path (Join-Path $BuildDir "dist") "App_OS_Digital.exe"
$InputDir = Join-Path $BuildDir "installer_input"
$Iss = Join-Path $BuildDir "App_OS_Digital.iss"
$CfgInno = Join-Path $BuildDir "config_distrib.json"
$CfgTemplate = Join-Path $BuildDir "config.ini.template"
$Icon = Join-Path $BuildDir "icone_os_digital.ico"

Write-Host "=== 1/3 PyInstaller ===" -ForegroundColor Cyan
Push-Location $BuildDir
try {
    pyinstaller --noconfirm App_OS_Digital.spec
} finally {
    Pop-Location
}

if (-not (Test-Path $ExeDist)) {
    throw "Executavel nao gerado: $ExeDist"
}

Write-Host "=== 2/3 Preparar pasta do instalador ===" -ForegroundColor Cyan
if (Test-Path $InputDir) {
    Remove-Item $InputDir -Recurse -Force
}
New-Item -ItemType Directory -Path $InputDir | Out-Null

Copy-Item $ExeDist (Join-Path $InputDir "App_OS_Digital.exe")
Copy-Item $CfgInno (Join-Path $InputDir "config.json")
Copy-Item $Icon (Join-Path $InputDir "icone_os_digital.ico")

Write-Host "Preparando config.ini com senha de suporte (barquiboboriginal)..." -ForegroundColor Cyan
python (Join-Path $BuildDir "preparar_config_instalador.py") (Join-Path $InputDir "config.ini")
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao preparar config.ini. Crie barquiboboriginal/suporte_build.json com senha_suporte."
}

if (-not (Test-Path $Icon)) {
    Write-Host "Icone nao encontrado em: $Icon" -ForegroundColor Yellow
}

Write-Host "=== 3/3 Inno Setup ===" -ForegroundColor Cyan
$IsccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LocalAppData\Programs\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    Write-Host ""
    Write-Host "Inno Setup 6 nao encontrado." -ForegroundColor Red
    Write-Host "Instale em: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Write-Host "Depois rode este script novamente." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Arquivos prontos para compilar manualmente em:" -ForegroundColor Green
    Write-Host "  $InputDir"
    Write-Host "  $Iss"
    exit 1
}

& $Iscc $Iss
$SetupOut = Join-Path (Join-Path $BuildDir "installer_output") "Setup_App_OS_Digital.exe"
if (Test-Path $SetupOut) {
    Write-Host ""
    Write-Host "Instalador gerado:" -ForegroundColor Green
    Write-Host "  $SetupOut"
} else {
    throw "Compilacao do Inno Setup nao gerou o arquivo esperado."
}
