@echo off
chcp 65001 > nul
echo ======================================================
echo  🚀 Auto Deploy to GitHub & Render.com
echo ======================================================
echo.

REM Check git status
git status --short

echo.
set /p commit_msg="👉 សូមបញ្ចូលចំណាំនៃការកែប្រែ (Commit message) [ចុច Enter យកលំនាំដើម]: "
if "%commit_msg%"=="" set commit_msg="Update voter system"

echo.
echo ⏳ កំពុងរៀបចំទិន្នន័យ (git add .)...
git add .

echo ⏳ កំពុងកត់ត្រាការកែប្រែ (git commit)...
git commit -m "%commit_msg%"

echo 🚀 កំពុងបញ្ជូនទៅកាន់ GitHub (git push)...
git push origin main

echo.
echo ======================================================
echo  ✅ ជោគជ័យ! Render.com នឹង Auto-Deploy ដោយស្វ័យប្រវត្តិក្នុរយៈពេល ១-២ នាទី!
echo  🌐 Live URL: https://voterlist-nokorpheas.onrender.com
echo ======================================================
pause
