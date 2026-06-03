# backend/

This folder is the **ERP backend UI** (currently Streamlit).

## Run (local)

From repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run web_app.py
```

> Note: The main Streamlit entrypoint remains `web_app.py` at repo root for now.

