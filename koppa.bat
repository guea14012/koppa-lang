@echo off
:: KOPPA Language Launcher (Windows)
:: Place this file in a folder that's on your PATH, or run from project root.
SETLOCAL

SET KOPPA_ROOT=%~dp0
SET PYTHONPATH=%KOPPA_ROOT%src;%PYTHONPATH%

:: Direct file execution: koppa myscript.kop
IF "%~x1"==".kop" (
    python "%KOPPA_ROOT%src\koppa.py" run "%~1" %2 %3 %4 %5 %6 %7 %8 %9
    EXIT /B %ERRORLEVEL%
)
IF "%~x1"==".apo" (
    python "%KOPPA_ROOT%src\koppa.py" run "%~1" %2 %3 %4 %5 %6 %7 %8 %9
    EXIT /B %ERRORLEVEL%
)
IF "%~x1"==".kpc" (
    python "%KOPPA_ROOT%src\koppa.py" run_bytecode "%~1" %2 %3 %4 %5 %6 %7 %8 %9
    EXIT /B %ERRORLEVEL%
)

:: Pass all arguments through to the Python runner
python "%KOPPA_ROOT%src\koppa.py" %*
EXIT /B %ERRORLEVEL%
