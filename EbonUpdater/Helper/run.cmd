@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if exist "%~dp0EbonUpdater.exe" (
    "%~dp0EbonUpdater.exe" "%EBONUPDATER_GAME%"
) else (
    where py >nul 2>&1
    if errorlevel 1 (
        python "%~dp0updater.py" "%EBONUPDATER_GAME%"
    ) else (
        py -3 "%~dp0updater.py" "%EBONUPDATER_GAME%"
    )
)
echo.
pause
cd /d "%TEMP%"
rd /s /q "%~dp0"
