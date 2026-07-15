@echo off
echo ============================================
echo  M2R CRM Build Script
echo ============================================
echo.

:: Save existing database before wiping dist
set DB_SOURCE=dist\M2R CRM\m2r_crm.db
set DB_BACKUP=%TEMP%\m2r_crm_build_backup.db
if exist "%DB_SOURCE%" (
    echo Saving existing database...
    copy /y "%DB_SOURCE%" "%DB_BACKUP%" >nul
    echo Done.
    echo.
)

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
    :: Restore database if build failed
    if exist "%DB_BACKUP%" (
        mkdir "dist\M2R CRM" >nul 2>&1
        copy /y "%DB_BACKUP%" "%DB_SOURCE%" >nul
    )
    pause
    exit /b 1
)

:: Restore database into fresh build
if exist "%DB_BACKUP%" (
    echo.
    echo Restoring database...
    copy /y "%DB_BACKUP%" "%DB_SOURCE%" >nul
    del "%DB_BACKUP%"
    echo Done.
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
