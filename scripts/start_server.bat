@echo off
REM FastAPI server startup script for Windows

cd backend
call ..\venv\Scripts\activate.bat
python run.py
pause
