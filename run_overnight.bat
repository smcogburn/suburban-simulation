@echo off
echo ============================================================
echo OVERNIGHT PIPELINE RUN
echo Scenarios: policy_b, policy_ab (+ optionally policy_a)
echo Each ~90 min with VIZ_DET_ORIGINS=10
echo Started: %DATE% %TIME%
echo ============================================================

set JAVA_TOOL_OPTIONS=-Xmx10g
cd /d "%~dp0"

echo.
echo [1/2] Running policy_b (full detailed)...
echo Started: %TIME%
python -m analysis.run_pipeline --scenario policy_b
if %ERRORLEVEL% neq 0 (
    echo ERROR: policy_b failed with exit code %ERRORLEVEL%
    echo %DATE% %TIME% - policy_b FAILED >> overnight_log.txt
    pause
    exit /b %ERRORLEVEL%
)
echo policy_b DONE: %TIME%
echo %DATE% %TIME% - policy_b completed >> overnight_log.txt

echo.
echo [2/2] Running policy_ab (full detailed)...
echo Started: %TIME%
python -m analysis.run_pipeline --scenario policy_ab
if %ERRORLEVEL% neq 0 (
    echo ERROR: policy_ab failed with exit code %ERRORLEVEL%
    echo %DATE% %TIME% - policy_ab FAILED >> overnight_log.txt
    pause
    exit /b %ERRORLEVEL%
)
echo policy_ab DONE: %TIME%
echo %DATE% %TIME% - policy_ab completed >> overnight_log.txt

echo.
echo ============================================================
echo ALL DONE: %DATE% %TIME%
echo ============================================================
echo %DATE% %TIME% - ALL COMPLETE >> overnight_log.txt
