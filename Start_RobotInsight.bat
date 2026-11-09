@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title RobotInsight

rem Only one copy may run; otherwise every copy hears the wake word and answers.
set "ROBOT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0modules\stop_previous_instance.ps1"

echo ==========================================
echo          RobotInsight - first run
echo ==========================================
echo.

where py >nul 2>nul
if errorlevel 1 goto MissingPython
py -3.11 --version >nul 2>nul
if errorlevel 1 goto MissingPython

if not exist ".venv\Scripts\python.exe" (
    echo Creating the private Python environment...
    py -3.11 -m venv .venv
    if errorlevel 1 goto SetupFailed
)

set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist ".setup_complete" (
    echo Installing Python packages. This can take several minutes on first run...
    "%PYTHON%" -m pip install --upgrade pip
    if errorlevel 1 goto SetupFailed
    "%PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 goto SetupFailed
    echo ready>.setup_complete
)

"%PYTHON%" -c "import cv2_enumerate_cameras" >nul 2>nul
if errorlevel 1 (
    echo Installing camera device detection...
    "%PYTHON%" -m pip install "cv2-enumerate-cameras>=1.2.2"
    if errorlevel 1 goto SetupFailed
)

"%PYTHON%" -c "import faster_whisper, kokoro_onnx" >nul 2>nul
if errorlevel 1 (
    echo Upgrading local speech engines...
    "%PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 goto SetupFailed
)

echo Checking offline speech and wake-word models...
"%PYTHON%" -m modules.setup_speech
if errorlevel 1 goto SetupFailed

if not exist "modules\en_US-hfc_female-medium.onnx" (
    echo Downloading the female fallback voice...
    "%PYTHON%" -m piper.download_voices en_US-hfc_female-medium --data-dir modules
    if errorlevel 1 goto SetupFailed
)

where ollama >nul 2>nul
if errorlevel 1 goto MissingOllama

rem Run a private Ollama on the integrated GPU; it is about 5x faster to read the
rem prompt than the CPU here. Set ROBOT_USE_IGPU=0 to use the regular Ollama instead.
if not "%ROBOT_USE_IGPU%"=="0" (
    set "OLLAMA_HOST=127.0.0.1:11435"
    set "OLLAMA_VULKAN=1"
    set "OLLAMA_IGPU_ENABLE=1"
    set "OLLAMA_NUM_PARALLEL=1"
)

ollama list >nul 2>nul
if not errorlevel 1 goto OllamaReady
echo Starting the Ollama service...
rem /b keeps it in this window, so it stops when RobotInsight's window closes.
start "" /b ollama serve >nul 2>nul
set /a attempts=0

:WaitForOllama
ollama list >nul 2>nul
if not errorlevel 1 goto OllamaReady
set /a attempts+=1
if %attempts% GEQ 30 goto OllamaUnavailable
timeout /t 1 /nobreak >nul
goto WaitForOllama

:OllamaReady
if not defined ROBOT_LLM_MODEL set "ROBOT_LLM_MODEL=qwen3:1.7b"
ollama list | findstr /i /c:"%ROBOT_LLM_MODEL%" >nul
if errorlevel 1 (
    echo Downloading the compact chat model %ROBOT_LLM_MODEL%...
    ollama pull "%ROBOT_LLM_MODEL%"
    if errorlevel 1 goto SetupFailed
)

ollama list | findstr /i /c:"moondream" >nul
if errorlevel 1 (
    echo Downloading the Moondream vision model...
    ollama pull moondream
    if errorlevel 1 goto SetupFailed
)

echo.
echo Starting RobotInsight. Type a message or say "Hey In Site" to wake it.
echo Use the fullscreen button to expand. Press Ctrl+C here to stop.
echo.
"%PYTHON%" main.py
echo.
echo RobotInsight has stopped.
pause
exit /b 0

:MissingPython
echo Python 3.11 x64 was not found.
echo Install it from https://www.python.org/downloads/release/python-3119/
echo During setup, enable the Python Launcher option.
start "" "https://www.python.org/downloads/release/python-3119/"
pause
exit /b 1

:MissingOllama
echo Ollama was not found. Install Ollama, then run this file again.
start "" "https://ollama.com/download/windows"
pause
exit /b 1

:OllamaUnavailable
echo Could not connect to Ollama. Open Ollama from the Start menu and try again.
pause
exit /b 1

:SetupFailed
echo.
echo Setup or startup failed. Read the error above, fix it, and run this file again.
pause
exit /b 1
