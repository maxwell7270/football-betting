@echo off
REM Football Betting MVP - Auto Setup für C:\Users\Marc\Desktop\Wetten\football-mvp\
title Football MVP Auto-Setup
color 0A

REM Wechsle in richtigen Ordner
cd /d "C:\Users\Marc\Desktop\Wetten\football-mvp"

echo.
echo ⚽ Installing dependencies in C:\Users\Marc\Desktop\Wetten\football-mvp\
pip install pyyaml requests pandas --quiet --upgrade

echo.
echo 🚀 Starting Football Betting MVP...
echo ==========================================
python main.py

echo.
echo ✅ Fertig! Doppelklick erneut für neuen Update.
pause >nul