@echo off
setlocal DisableDelayedExpansion
for %%I in ("%~dp0..\..\..") do set "EBONUPDATER_GAME=%%~fI"
if not exist "%EBONUPDATER_GAME%\Interface\AddOns\EbonUpdater\EbonUpdater.toc" goto badlocation
set "stage=%TEMP%\EbonUpdater-%RANDOM%-%RANDOM%-%RANDOM%"
mkdir "%stage%" 2>nul || goto failed
copy /y "%~dp0Helper\run.cmd" "%stage%\run.cmd" >nul || goto failedstage
if exist "%~dp0Helper\EbonUpdater.exe" (
    copy /y "%~dp0Helper\EbonUpdater.exe" "%stage%\EbonUpdater.exe" >nul || goto failedstage
) else (
    copy /y "%~dp0Helper\updater.py" "%stage%\updater.py" >nul || goto failedstage
)
start "EbonUpdater" /D "%stage%" "%ComSpec%" /D /C run.cmd
if errorlevel 1 goto failedstage
exit /b 0
:badlocation
echo Install the complete EbonUpdater folder in Interface\AddOns first.
pause
exit /b 1
:failedstage
rd /s /q "%stage%"
:failed
echo Could not prepare the temporary updater.
pause
exit /b 1
