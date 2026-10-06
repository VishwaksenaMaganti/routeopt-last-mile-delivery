@echo off
setlocal
cd /d "%~dp0"

set "ROUTEOPT_URL=http://127.0.0.1:8501"
powershell -NoProfile -Command "try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8501/_stcore/health' -TimeoutSec 2; if ($response.StatusCode -eq 200) { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 (
    echo RouteOpt is already running. Opening the dashboard...
    start "" "%ROUTEOPT_URL%"
    exit /b 0
)

set "ROUTEOPT_PY=%CD%\.venv\Scripts\python.exe"
if exist "%ROUTEOPT_PY%" goto :check_python

where python >nul 2>nul
if errorlevel 1 goto :create_venv
python -c "import sys, pandas, streamlit; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto :create_venv
set "ROUTEOPT_PY=python"
goto :check_dependencies

:create_venv
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
    if errorlevel 1 goto :create_venv_with_python
    py -3 -m venv .venv
    if errorlevel 1 goto :failed
    goto :set_venv
)

:create_venv_with_python
where python >nul 2>nul
if errorlevel 1 goto :python_missing
python -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto :python_too_old
python -m venv .venv
if errorlevel 1 goto :failed

:set_venv
set "ROUTEOPT_PY=%CD%\.venv\Scripts\python.exe"

:check_python
"%ROUTEOPT_PY%" -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto :python_too_old

:check_dependencies
"%ROUTEOPT_PY%" -c "import pandas, streamlit" >nul 2>nul
if errorlevel 1 (
    echo Installing RouteOpt dependencies...
    "%ROUTEOPT_PY%" -m pip install -r requirements.txt
    if errorlevel 1 goto :failed
)

echo Starting RouteOpt at http://localhost:8501
echo Keep this window open while using the app. Press Ctrl+C to stop it.
"%ROUTEOPT_PY%" -m streamlit run app.py --server.port 8501
if errorlevel 1 goto :failed

endlocal
exit /b 0

:python_missing
echo Python 3.10 or newer is required. Install Python and try again.
goto :failed

:python_too_old
echo RouteOpt needs Python 3.10 or newer.
goto :failed

:failed
echo.
echo RouteOpt could not start. Check the messages above, then try again.
pause
endlocal
exit /b 1
