$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (!(Test-Path $Python)) {
    python -m venv (Join-Path $Root ".venv")
}

& $Python -m pip install -r (Join-Path $Root "requirements.txt")
& $Python (Join-Path $Root "scripts\extract_material_icons.py")
& $Python (Join-Path $Root "scripts\create_app_icon.py")

$AddData = "assets;assets"
$Icon = Join-Path $Root "assets\app_icon.ico"
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --uac-admin `
    --name "LockHeart_Bulksale" `
    --icon $Icon `
    --add-data $AddData `
    --paths (Join-Path $Root "src") `
    (Join-Path $Root "src\lockheart_bulk_sale\launcher.py")

Write-Host ""
Write-Host "Done: $Root\dist\LockHeart_Bulksale\LockHeart_Bulksale.exe"
