$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (!(Test-Path $Python)) {
    python -m venv (Join-Path $Root ".venv")
}

& $Python -m pip install -r (Join-Path $Root "requirements.txt")
& $Python (Join-Path $Root "scripts\extract_material_icons.py")
& $Python (Join-Path $Root "scripts\create_app_icon.py")
$env:PYTHONPATH = Join-Path $Root "src"
& $Python -m lockheart_bulk_sale
