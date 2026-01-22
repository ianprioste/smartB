#!/bin/bash
# FastAPI server startup script for Linux/Mac

cd "$(dirname "$0")/backend" || exit 1
source ../.venv/bin/activate
python run.py
