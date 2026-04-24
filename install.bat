@echo off
:: KOPPA Language Installer for Windows
:: Run as Administrator for system-wide install, or run normally for user install.

SETLOCAL EnableDelayedExpansion
SET KOPPA_ROOT=%~dp0
SET KOPPA_ROOT=%KOPPA_ROOT:~0,-1%
SET INSTALL_DIR=%LOCALAPPDATA%\koppa

ECHO ============================================
ECHO   KOPPA Language Installer v2.0
ECHO ============================================
ECHO.

:: Check Python
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO [ERROR] Python not found. Please install Python 3.8+ from https://python.org
    EXIT /B 1
)
FOR /F "tokens=2" %%v IN ('python --version 2^>^&1') DO SET PY_VER=%%v
ECHO [OK] Python %PY_VER% found

:: Create install directory
IF NOT EXIST "%INSTALL_DIR%" MKDIR "%INSTALL_DIR%"
ECHO [OK] Install directory: %INSTALL_DIR%

:: Copy source files
XCOPY /E /Y /Q "%KOPPA_ROOT%\src\*"     "%INSTALL_DIR%\src\"     >nul
XCOPY /E /Y /Q "%KOPPA_ROOT%\stdlib\*"  "%INSTALL_DIR%\stdlib\"  >nul 2>&1
XCOPY /E /Y /Q "%KOPPA_ROOT%\examples\*" "%INSTALL_DIR%\examples\" >nul 2>&1
ECHO [OK] Files copied to %INSTALL_DIR%

:: Create launcher in install dir
(
ECHO @echo off
ECHO SET PYTHONPATH=%INSTALL_DIR%\src;%%PYTHONPATH%%
ECHO python "%INSTALL_DIR%\src\koppa.py" %%*
) > "%INSTALL_DIR%\koppa.bat"

:: Add to user PATH
SET "NEW_PATH=%INSTALL_DIR%"
REG QUERY "HKCU\Environment" /v PATH >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    FOR /F "tokens=3*" %%A IN ('REG QUERY "HKCU\Environment" /v PATH 2^>nul') DO SET "CURRENT_PATH=%%A %%B"
    ECHO !CURRENT_PATH! | FINDSTR /I "%INSTALL_DIR%" >nul
    IF %ERRORLEVEL% NEQ 0 (
        SETX PATH "!CURRENT_PATH!;%INSTALL_DIR%" >nul
        ECHO [OK] Added %INSTALL_DIR% to user PATH
    ) ELSE (
        ECHO [OK] Already in PATH
    )
) ELSE (
    SETX PATH "%INSTALL_DIR%" >nul
    ECHO [OK] Created user PATH with %INSTALL_DIR%
)

ECHO.
ECHO ============================================
ECHO   Installation Complete!
ECHO ============================================
ECHO.
ECHO   Restart your terminal, then run:
ECHO     koppa version
ECHO     koppa run examples\hello.kop
ECHO     koppa repl
ECHO.
ECHO   Examples are in: %INSTALL_DIR%\examples\
ECHO ============================================
