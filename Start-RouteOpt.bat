@echo off
setlocal
cd /d "%~dp0"

set "ROUTEOPT_PY=%CD%\.venv\Scripts\python.exe"

if not exist "%ROUTEOPT_PY%" (
    echo Creating RouteOpt virtual environment...
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
        if errorlevel 1 (
            echo Python 3.10 or newer is required. Install it and try again.
            goto :failed
        )
        py -3 -m venv .venv
    ) else (
        where python >nul 2>nul
        if errorlevel 1 (
            echo Python 3 is required. Install Python 3.10 or newer and try again.
            goto :failed
        )
        python -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
        if errorlevel 1 (
            echo Python 3.10 or newer is required. Install it and try again.
            goto :failed
        )
        python -m venv .venv
    )
    if errorlevel 1 goto :failed
)

"%ROUTEOPT_PY%" -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 (
    echo RouteOpt needs Python 3.10 or newer in its virtual environment.
    goto :failed
)

"%ROUTEOPT_PY%" -c "import pandas, streamlit" >nul 2>nul
if errorlevel 1 (
    echo Installing RouteOpt dependencies...
    "%ROUTEOPT_PY%" -m pip install -r requirements.txt
    if errorlevel 1 goto :failed
)

echo Starting RouteOpt at http://localhost:8501
echo Keep this window open while using the app. Press Ctrl+C to stop it.
"%ROUTEOPT_PY%" -m streamlit run app.py
if errorlevel 1 goto :failed

endlocal
exit /b 0

:failed
echo.
echo RouteOpt could not start. Check the messages above, then try again.
pause
endlocal
exit /b 1
