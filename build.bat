@echo off
echo ============================================
echo  M2R CRM Build Script
echo ============================================
echo.

echo Cleaning previous build...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
echo Done.
echo.

echo Running PyInstaller...
pyinstaller m2r_crm.spec --noconfirm
if errorlevel 1 (
    echo.
    echo *** BUILD FAILED ***
    pause
    exit /b 1
)

echo.
echo ============================================
echo  BUILD SUCCESSFUL
echo ============================================
echo.
echo Output: dist\M2R CRM\
echo.
dir "dist\M2R CRM\*.exe"
echo.
pause
