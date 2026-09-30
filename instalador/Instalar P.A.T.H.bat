@echo off
chcp 65001 >nul
title Instalar P.A.T.H.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" %*
if errorlevel 1 pause & exit /b 1
ping -n 4 127.0.0.1 >nul
