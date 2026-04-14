@echo off
chcp 65001 >nul
echo ========================================
echo   Fluent Todo - Single File Build
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "FluentTodo.spec" del /q "FluentTodo.spec"

echo.
echo [INFO] Building single file EXE...
echo.

pyinstaller ^
    --noconfirm ^
    --windowed ^
    --onefile ^
    --name "FluentTodo" ^
    --icon "assets\icon.ico" ^
    --add-data "assets\icon.ico;." ^
    --add-data "qss;qss" ^
    --collect-all "qfluentwidgets" ^
    --collect-submodules "PySide6" ^
    --hidden-import "darkdetect" ^
    --hidden-import "shiboken6" ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Done!
echo   Output: dist\FluentTodo.exe
echo ========================================
echo.
pause
