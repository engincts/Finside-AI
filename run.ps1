# Finside AI — Windows UTF-8 Safe PowerShell Launcher (run.ps1)
param (
    [switch]$mock,
    [switch]$cli
)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Finside AI - Kurumsal Kredi Tahsis Karar Destek Sistemi" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan

Set-Location -Path $PSScriptRoot

# --- 0. venv kontrolü ---
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Sanal ortam (.venv) bulunamadi, olusturuluyor..." -ForegroundColor Yellow
    python -m venv .venv
    if (-not (Test-Path $venvPython)) {
        Write-Host "HATA: .venv olusturulamadi. Python 3.10+ kurulu mu?" -ForegroundColor Red
        exit 1
    }
}

# --- 1. Bağımlılıklar ---
Write-Host "Bagimliliklar kontrol ediliyor (.venv)..." -ForegroundColor Yellow
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet -r requirements.txt

# --- 2. Uygulama Çalıştırma ---
if ($cli -or $mock) {
    Write-Host "CLI Test Motoru Calistiriliyor..." -ForegroundColor Cyan
    & $venvPython run_poc.py --mock
} else {
    Write-Host "Streamlit baslatiliyor: http://localhost:8501" -ForegroundColor Cyan
    & $venvPython -m streamlit run app.py
}
