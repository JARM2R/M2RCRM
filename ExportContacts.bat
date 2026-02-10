@echo off
REM M2R CRM Contact Export Launcher
REM This batch file launches the Contact Export tool

cd /d "%~dp0"
pythonw "crm_contact_export.py"
