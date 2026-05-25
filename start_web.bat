@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
python -m streamlit run web_app.py --server.address 0.0.0.0 --server.port 8501
