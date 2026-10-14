@echo off
rem ======================================================================
rem  Lightning Monitor for Windows
rem
rem    run.bat              run in this window (Ctrl+C to stop)
rem    run.bat install      run in the background: start at boot, restart
rem                         if it crashes, open the dashboard port in the
rem                         firewall (asks for administrator rights)
rem    run.bat start        start the background task now
rem    run.bat stop         stop the background task
rem    run.bat status       show task state, dashboard port and recent log
rem    run.bat uninstall    stop and remove the background task
rem
rem  Background output goes to lightning.log next to this file.
rem ======================================================================
setlocal EnableExtensions DisableDelayedExpansion
set "HERE=%~dp0"
set "SELF=%~f0"
set "TASK=Lightning Monitor"
set "LOG=%HERE%lightning.log"
set "LM_TASK=%TASK%"
set "LM_DIR=%HERE%"
set "LM_LOG=%LOG%"

if /i "%~1"=="service"   goto :service
if /i "%~1"=="install"   goto :install
if /i "%~1"=="uninstall" goto :uninstall
if /i "%~1"=="start"     goto :start
if /i "%~1"=="stop"      goto :stop
if /i "%~1"=="status"    goto :status
if /i "%~1"=="help"      goto :help
if /i "%~1"=="-h"        goto :help
if /i "%~1"=="/?"        goto :help
if not "%~1"=="" goto :help

rem ---------------- run in this window ----------------
call :ensuredeps || goto :failpause
call :ensureconfig
"%PY%" "%HERE%lightning.py"
if errorlevel 1 goto :failpause
exit /b 0

:failpause
rem Keep the window open when started by double-click so errors can be read.
echo.
pause
exit /b 1


rem ---------------- install background task ----------------
:install
call :needadmin install || exit /b 0
call :ensuredeps || goto :done
echo Python: %PY%
"%PY%" -c "import sys; sys.exit(1 if 'windowsapps' in (sys.base_prefix + sys.executable).lower() else 0)" >nul 2>&1
if errorlevel 1 goto :storepython
"%PY%" -c "import flask, sys; sys.exit(1 if 'AppData' in flask.__file__ and 'site-packages' in flask.__file__ and sys.prefix.lower() not in flask.__file__.lower() else 0)" >nul 2>&1
if errorlevel 1 goto :userpackages
if not exist "%HERE%config.json" goto :noconfig

call :killmonitor
set "LM_BAT=%SELF%"
set "LM_PY=%PY%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $q=[char]34; $arg='/c '+$q+$q+$env:LM_BAT+$q+' service '+$q+$env:LM_PY+$q+$q; $a=New-ScheduledTaskAction -Execute $env:ComSpec -Argument $arg -WorkingDirectory $env:LM_DIR; $t=New-ScheduledTaskTrigger -AtStartup; $p=New-ScheduledTaskPrincipal -UserId 'NT AUTHORITY\SYSTEM' -LogonType ServiceAccount -RunLevel Highest; $s=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew; Register-ScheduledTask -TaskName $env:LM_TASK -Description 'Lightning Monitor collector and dashboard' -Action $a -Trigger $t -Principal $p -Settings $s -Force | Out-Null; $port=8097; try { $c=Get-Content -Raw -Encoding UTF8 (Join-Path $env:LM_DIR 'config.json') | ConvertFrom-Json; if ($c.web.port) { $port=[int]$c.web.port } } catch {}; Get-NetFirewallRule -DisplayName $env:LM_TASK -ErrorAction SilentlyContinue | Remove-NetFirewallRule; New-NetFirewallRule -DisplayName $env:LM_TASK -Direction Inbound -Protocol TCP -LocalPort $port -Action Allow -Profile Domain,Private | Out-Null; Start-ScheduledTask -TaskName $env:LM_TASK; Write-Host ('Dashboard: http://localhost:'+$port+'/  (firewall opened on port '+$port+' for private/domain networks)')"
if errorlevel 1 goto :regfail
echo.
echo Installed and started. Lightning Monitor now starts at boot and restarts if it stops.
echo Log file: %LOG%
echo Check it any time with:  run.bat status
goto :done

:storepython
echo.
echo The Microsoft Store version of Python cannot run as a background task.
echo Install Python from https://www.python.org/downloads/ and run "run.bat install" again.
goto :done

:userpackages
echo.
echo The Python packages are installed only for your Windows account, so the
echo background task (which runs as the system account) cannot see them.
echo Create a virtual environment in this folder and install into it:
echo   "%PY%" -m venv "%HERE%venv"
echo   "%HERE%venv\Scripts\python.exe" -m pip install -r "%HERE%requirements.txt"
echo then run "run.bat install" again.
goto :done

:noconfig
call :ensureconfig
echo Edit config.json first (coordinates, e-mail, Zabbix), then run "run.bat install" again.
goto :done

:regfail
echo.
echo Registering the background task failed - see the message above.
goto :done


rem ---------------- start / stop / uninstall ----------------
:start
call :needadmin start || exit /b 0
powershell -NoProfile -Command "Start-ScheduledTask -TaskName $env:LM_TASK"
if errorlevel 1 (echo Task not found - run "run.bat install" first.) else (echo Started.)
goto :done

:stop
call :needadmin stop || exit /b 0
call :killmonitor
echo Stopped. It will start again at the next boot; "run.bat uninstall" removes it.
goto :done

:uninstall
call :needadmin uninstall || exit /b 0
call :killmonitor
powershell -NoProfile -Command "Unregister-ScheduledTask -TaskName $env:LM_TASK -Confirm:$false -ErrorAction SilentlyContinue; Get-NetFirewallRule -DisplayName $env:LM_TASK -ErrorAction SilentlyContinue | Remove-NetFirewallRule"
echo Background task and firewall rule removed. Your files, config.json and lightning.db are untouched.
goto :done


rem ---------------- status ----------------
:status
powershell -NoProfile -Command "$t=Get-ScheduledTask -TaskName $env:LM_TASK -ErrorAction SilentlyContinue; if (-not $t) { 'Background task: not installed' } else { $i=$t | Get-ScheduledTaskInfo; 'Background task: '+$t.State+'   (last start '+$i.LastRunTime+')' }; $port=8097; try { $c=Get-Content -Raw -Encoding UTF8 (Join-Path $env:LM_DIR 'config.json') | ConvertFrom-Json; if ($c.web.port) { $port=[int]$c.web.port } } catch {}; if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { 'Dashboard: running - http://localhost:'+$port+'/' } else { 'Dashboard: not listening on port '+$port }; if (Test-Path -LiteralPath $env:LM_LOG) { ''; 'Last lines of lightning.log:'; Get-Content -LiteralPath $env:LM_LOG -Tail 15 -Encoding UTF8 }"
goto :done


rem ---------------- background loop (started by the task) ----------------
:service
set "PY=%~2"
if not defined PY call :findpy
if not defined PY exit /b 1
set "LIGHTNING_SUPERVISED=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%HERE%"
:serviceloop
call :rotatelog
>>"%LOG%" echo [%date% %time%] starting Lightning Monitor
"%PY%" "%HERE%lightning.py" >>"%LOG%" 2>&1
set "RC=%errorlevel%"
>>"%LOG%" echo [%date% %time%] Lightning Monitor exited with code %RC%
rem 75 = restart requested from the dashboard: come back immediately.
if "%RC%"=="75" goto :serviceloop
rem Anything else (crash, network trouble at boot): wait 10 s, try again.
rem (ping instead of timeout: timeout fails without a console window)
ping -n 11 127.0.0.1 >nul
goto :serviceloop


rem ---------------- helpers ----------------
:ensuredeps
rem Find Python; on first run create venv\ and install requirements.txt into it.
call :findpy || exit /b 1
"%PY%" -c "import flask, websockets, requests, PIL" >nul 2>&1
if not errorlevel 1 exit /b 0
echo.
echo First run: installing the required Python packages (one time only)...
if exist "%HERE%venv\Scripts\python.exe" goto :pipinstall
echo Creating a virtual environment in "%HERE%venv" ...
"%PY%" -m venv "%HERE%venv"
if errorlevel 1 goto :venvfailed
set "PY=%HERE%venv\Scripts\python.exe"
:pipinstall
"%PY%" -m pip install --disable-pip-version-check -r "%HERE%requirements.txt"
if errorlevel 1 goto :pipfailed
"%PY%" -c "import flask, websockets, requests, PIL" >nul 2>&1
if errorlevel 1 goto :pipfailed
echo Packages installed.
echo.
exit /b 0
:venvfailed
echo Could not create the virtual environment with "%PY%".
exit /b 1
:pipfailed
echo.
echo Installing the packages failed - see the messages above.
echo Check the internet connection, then run run.bat again.
exit /b 1

:ensureconfig
if exist "%HERE%config.json" exit /b 0
copy /y "%HERE%config.example.json" "%HERE%config.json" >nul
echo Created config.json from config.example.json.
echo Edit it to set your coordinates, e-mail and Zabbix settings.
echo.
exit /b 0

:findpy
set "PY="
if exist "%HERE%venv\Scripts\python.exe" set "PY=%HERE%venv\Scripts\python.exe"
if defined PY exit /b 0
if exist "%HERE%.venv\Scripts\python.exe" set "PY=%HERE%.venv\Scripts\python.exe"
if defined PY exit /b 0
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%P"
if defined PY exit /b 0
for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%P"
if defined PY exit /b 0
echo Python 3 was not found. Install it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during setup.
exit /b 1

:needadmin
net session >nul 2>&1
if not errorlevel 1 exit /b 0
echo Administrator rights are needed - please confirm the Windows prompt.
set "LM_SELF=%SELF%"
set "LM_ARG=%~1"
powershell -NoProfile -Command "Start-Process -FilePath $env:LM_SELF -ArgumentList $env:LM_ARG,'elevated' -Verb RunAs"
exit /b 1

:killmonitor
rem Stop the task (ends its loop), then any lightning.py from this folder.
powershell -NoProfile -Command "Stop-ScheduledTask -TaskName $env:LM_TASK -ErrorAction SilentlyContinue; $pat='*'+$env:LM_DIR+'lightning.py*'; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like $pat } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
exit /b 0

:rotatelog
if not exist "%LOG%" exit /b 0
for %%F in ("%LOG%") do if %%~zF GTR 10485760 move /y "%LOG%" "%LOG%.old" >nul
exit /b 0

:help
echo Usage: run.bat [install ^| start ^| stop ^| status ^| uninstall]
echo   (no argument)  run Lightning Monitor in this window
echo   install        run in the background, start at boot, restart on crash
echo   start / stop   start or stop the background task
echo   status         show whether it is running, plus the last log lines
echo   uninstall      remove the background task and firewall rule
goto :done

:done
rem Keep the elevated window open so the result can be read.
if /i "%~2"=="elevated" pause
endlocal
exit /b 0
