@echo off
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
python main.py
