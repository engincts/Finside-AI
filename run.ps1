# Finside AI — Windows UTF-8 Safe PowerShell Launcher (run.ps1)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Finside AI - Kurumsal Kredi Tahsis Karar Destek Sistemi" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan

# 1. Python & Pip Bağımlılık Yüklemesi
Write-Host "Bagimliliklar (pydantic, google-genai, openai, anthropic, huggingface-hub, streamlit) kontrol ediliyor..." -ForegroundColor Yellow
python -m pip install --quiet -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "Paket yuklemesi tamamlandi..." -ForegroundColor Yellow
}

# 2. Streamlit Web Uygulamasını Başlatma
Write-Host "Streamlit Web Kullanici Arayuzu baslatiliyor..." -ForegroundColor Green
Write-Host "Tarayicinizda acin: http://localhost:8501" -ForegroundColor Cyan
streamlit run app.py
