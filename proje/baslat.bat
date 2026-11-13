@echo off
title Steam Yorum Analizi
cd /d "%~dp0"
echo Uygulama baslatiliyor, tarayici birazdan acilacak...
echo (Kapatmak icin bu pencereyi kapatin)
echo.
where python >nul 2>nul
if %errorlevel%==0 (
    python -m streamlit run app.py
) else (
    py -m streamlit run app.py
)
pause
