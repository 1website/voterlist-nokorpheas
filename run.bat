@echo off
chcp 65001 > nul
cd /d "%~dp0"
title ប្រព័ន្ធគ្រប់គ្រងអ្នកចុះឈ្មោះបោះឆ្នោត រដ្ឋបាលឃុំនគរភាស

echo ======================================================================
echo   🇰🇭  ប្រព័ន្ធគ្រប់គ្រងអ្នកចុះឈ្មោះបោះឆ្នោត រដ្ឋបាលឃុំនគរភាស
echo       (១០ ភូមិ • ១៤ ការិយាល័យបោះឆ្នោត)
echo ======================================================================
echo.
echo  🚀 កំពុងចាប់ផ្តើម Server សូមរង់ចាំ...
echo  ⚠️  សូមកុំបិទផ្ទាំង Command Prompt នេះក្នុងពេលកំពុងប្រើប្រាស់ប្រព័ន្ធ!
echo.

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py main.py
    goto end
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python main.py
    goto end
)

echo ❌ មិនអាចស្វែងរក Python (py/python) ក្នុងម៉ាស៊ីនបានទេ!
echo សូមប្រាកដថា Python ត្រូវបានដំឡើងត្រឹមត្រូវ។
echo.

:end
pause
