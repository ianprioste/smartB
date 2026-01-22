@echo off
REM Celery worker startup script for Windows

cd backend
call ..\venv\Scripts\activate.bat
python celery_worker_windows.py
pause
