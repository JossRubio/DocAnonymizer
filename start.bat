@echo off
echo Starting Document Anonymizer...

set PYTHON=C:\Users\joman\AppData\Local\Programs\Python\Python312\python.exe
set ROOT=%~dp0

echo Checking dependencies...
%PYTHON% -m pip show fastapi >/dev/null 2>&1
if %ERRORLEVEL% neq 0 (
    echo Dependencies not found. Installing from requirements.txt...
    %PYTHON% -m pip install -r "%ROOT%requirements.txt"
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
    echo Dependencies installed successfully.
) else (
    echo Dependencies OK.
)

cd /d "%ROOT%backend"
echo Starting server on http://localhost:8001 ...
start "" %PYTHON% -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
timeout /t 3 /nobreak >nul
start http://localhost:8001
