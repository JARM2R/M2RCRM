@echo off
REM M2R Newsletter Sender Launcher

cd /d "%~dp0"
setlocal enabledelayedexpansion

REM -----------------------------------------------------------------------
REM Find the most recently modified newsletter-*.html file in this folder
REM -----------------------------------------------------------------------
set "DEFAULT_FILE="
for /f "delims=" %%f in ('dir /b /o-d newsletter-*.html 2^>nul') do (
    if not defined DEFAULT_FILE set "DEFAULT_FILE=%%f"
)
if not defined DEFAULT_FILE set "DEFAULT_FILE=newsletter.html"

:input_file
echo.
echo  Most recent newsletter file: %DEFAULT_FILE%
set "NEWSLETTER=%DEFAULT_FILE%"
set /p "NEWSLETTER=  Enter filename (or press Enter to accept): "

if not exist "%NEWSLETTER%" (
    echo.
    echo  File not found: %NEWSLETTER%
    goto input_file
)

:menu
echo.
echo  M2R Newsletter Sender  ^|  %NEWSLETTER%
echo  -----------------------------------------------
echo  1) Dry run   (preview first 10 recipients, no emails sent)
echo  2) Send for real
echo  3) Change file
echo  4) Exit
echo.
set /p "CHOICE=  Choose [1-4]: "

if "%CHOICE%"=="1" (
    echo.
    python send_newsletter.py "%NEWSLETTER%" --dry-run
    echo.
    pause
    goto menu
)
if "%CHOICE%"=="2" (
    echo.
    python send_newsletter.py "%NEWSLETTER%"
    echo.
    pause
    goto menu
)
if "%CHOICE%"=="3" goto input_file
if "%CHOICE%"=="4" exit /b
goto menu
