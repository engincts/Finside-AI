# Finside AI — Windows UTF-8 Safe PowerShell Launcher (run.ps1)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Finside AI - Kurumsal Kredi Tahsis Karar Destek Sistemi" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan

Set-Location -Path $PSScriptRoot

# --- 0. venv (proje bağımlılıkları BURADA — sistem Python'ı DEĞİL) ---
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Sanal ortam (.venv) bulunamadi, olusturuluyor..." -ForegroundColor Yellow
    python -m venv .venv
    if (-not (Test-Path $venvPython)) {
        Write-Host "HATA: .venv olusturulamadi. Python 3.10+ kurulu mu?" -ForegroundColor Red
        exit 1
    }
}

# --- 1. Bağımlılıklar (langgraph, streamlit, LLM SDK'lari, rapidfuzz...) ---
Write-Host "Bagimliliklar kontrol ediliyor (.venv)..." -ForegroundColor Yellow
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet -r requirements.txt

# --- 2. Streamlit Web Uygulamasi (mutlaka .venv'den) ---
Write-Host "Streamlit baslatiliyor: http://localhost:8501" -ForegroundColor Cyan
& $venvPython -m streamlit run app.py
