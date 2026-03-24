@echo off
echo ================================================
echo  Suburban Simulation - Visualization Server
echo ================================================
cd /d "%~dp0"
echo Server root: %CD%
echo.
echo Open this URL in your browser:
echo   http://localhost:8081/visualization/
echo.
echo Press Ctrl+C to stop.
echo ================================================
python -m http.server 8081
