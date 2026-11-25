@echo off
cd /d "%~dp0"
py -3 -m PyInstaller --onefile --name EbonUpdater --distpath . updater.py
if errorlevel 1 echo Install PyInstaller first: py -3 -m pip install pyinstaller
pause
