@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ============================================================
:: PocketLedger - Windows One-Click Startup
:: Zero dependencies on host: uses built-in Python
:: ============================================================

cd /d "%~dp0"
cd ..

set "VPY=python\python.exe"

:: Quick check: is the built-in Python present?
if not exist "%VPY%" (
    echo.
    echo   [FAIL] python\python.exe not found.
    echo   The project is incomplete - missing the built-in Python folder.
    echo.
    echo   Ask the sender to include the python\ folder in the copy.
    echo.
    pause
    exit 1
)

if not exist "logs" mkdir logs 2>nul

echo.
echo ==============================================================
echo   PocketLedger - Personal Finance Analysis System
echo   Python: built-in (no install needed)
echo ==============================================================

:: ============================================================
:: [1/3] Check dependencies
:: ============================================================
echo.
echo [1/3] Checking dependencies...

call "%VPY%" -c "import fastapi,pandas,numpy,openpyxl,mlxtend,prophet,statsmodels,tabulate,uvicorn,python_multipart" >nul 2>&1
if not errorlevel 1 (
    echo   [OK] All dependencies ready
    goto :check_data
)

echo   Some dependencies are missing. Installing now...
echo.

set "PIP_OK=0"

:: Phase 0: Local wheels (offline, zero network)
if exist "wheels\*.whl" (
    echo   [0/4] Offline mode - installing from wheels\ ...
    call "%VPY%" -m pip install --no-index --find-links="wheels" fastapi pandas numpy openpyxl mlxtend prophet statsmodels tabulate uvicorn python-multipart > "%TEMP%\pip_output.txt" 2>&1
    if not errorlevel 1 (
        set "PIP_OK=1"
    ) else (
        echo   [SKIP] Wheels incompatible - will try online
    )
)

:: Phase 1: Tsinghua mirror
if !PIP_OK! equ 0 (
    echo   [1/3] Tsinghua mirror...
    call "%VPY%" -m pip install fastapi pandas numpy openpyxl mlxtend prophet statsmodels tabulate uvicorn python-multipart -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn > "%TEMP%\pip_output.txt" 2>&1
    if not errorlevel 1 set "PIP_OK=1"
)

:: Phase 2: USTC mirror
if !PIP_OK! equ 0 (
    echo   [2/3] USTC mirror...
    call "%VPY%" -m pip install fastapi pandas numpy openpyxl mlxtend prophet statsmodels tabulate uvicorn python-multipart -i https://mirrors.ustc.edu.cn/pypi/web/simple --trusted-host mirrors.ustc.edu.cn > "%TEMP%\pip_output.txt" 2>&1
    if not errorlevel 1 set "PIP_OK=1"
)

:: Phase 3: Official PyPI (show errors)
if !PIP_OK! equ 0 (
    echo   [3/3] Official PyPI...
    echo   ----------------------------------------
    call "%VPY%" -m pip install fastapi pandas numpy openpyxl mlxtend prophet statsmodels tabulate uvicorn python-multipart 2>&1
    if not errorlevel 1 (
        set "PIP_OK=1"
    )
    echo   ----------------------------------------
)

if !PIP_OK! equ 0 (
    echo.
    echo   [FAIL] Could not install dependencies.
    echo.
    echo   Solutions:
    echo   [1] No internet - copy the wheels\ folder from the original PC
    echo   [2] Corporate VPN - set HTTP_PROXY and re-run
    echo   [3] Check pip error messages above for details
    echo.
    pause
    exit 1
)

:: Verify after install
call "%VPY%" -c "import fastapi,pandas,numpy,openpyxl,mlxtend,prophet,statsmodels,tabulate,uvicorn,python_multipart" >nul 2>&1
if errorlevel 1 (
    echo   [WARN] Import still fails. Trying once more...
    call "%VPY%" -m pip install fastapi pandas numpy openpyxl mlxtend prophet statsmodels tabulate uvicorn python-multipart 2>&1
    call "%VPY%" -c "import fastapi,pandas,numpy,openpyxl,mlxtend,prophet,statsmodels,tabulate,uvicorn,python_multipart" >nul 2>&1
    if errorlevel 1 (
        echo   [FAIL] Dependencies could not be verified.
        pause
        exit 1
    )
)
echo   [OK] Dependencies verified

:: ============================================================
:: [2/3] Data directories
:: ============================================================
:check_data
echo.
echo [2/3] Checking data directories...

for %%d in (data predata logs) do (
    if not exist "%%d" mkdir "%%d" 2>nul
)

if exist "data\my_payment.csv" (
    echo   [OK] data\my_payment.csv ready
) else (
    echo   [INFO] No data yet - upload bills via web UI
)

:: ============================================================
:: [3/3] Start server
:: ============================================================
if not exist "src\mypayment_api.py" (
    echo   [FAIL] src\mypayment_api.py not found
    pause
    exit 1
)

echo.
echo [3/3] Starting server on http://127.0.0.1:8765
echo ==============================================================
echo   Press Ctrl+C to stop ^| Close browser to auto-stop
echo.

set "CRASH_COUNT=0"

:run_loop
call "%VPY%" src\mypayment_api.py
set "EXIT_CODE=%errorlevel%"

if %EXIT_CODE% equ 0 goto :clean_exit

set /a "CRASH_COUNT=CRASH_COUNT+1"

if %CRASH_COUNT% gtr 3 goto :too_many_crashes

call "%VPY%" -c "import socket; s=socket.socket(); s.settimeout(1); r=s.connect_ex(('127.0.0.1',8765)); s.close(); exit(r)" >nul 2>&1
if errorlevel 1 (
    echo   [INFO] Server stopped. Auto-restarting in 3s (%CRASH_COUNT%/3)...
    timeout /t 3 /nobreak >nul
    goto :run_loop
)

echo   [INFO] Port 8765 occupied - server may still be running.
goto :clean_exit

:too_many_crashes
echo.
echo   [FAIL] Server crashed %CRASH_COUNT% times.
echo          Run manually: python\python.exe src\mypayment_api.py
echo.
choice /C YN /M "   Restart server [Y/N]?"
if errorlevel 2 goto :clean_exit
if errorlevel 1 (
    set "CRASH_COUNT=0"
    goto :run_loop
)

:clean_exit
echo   Server stopped.
pause
