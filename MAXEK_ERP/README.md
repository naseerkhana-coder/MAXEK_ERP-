# MAXEK ERP Browser App

A browser-based construction ERP for MAXEK built with Python Flask and SQLite.

## Folder Structure

- `app.py` - Browser ERP application entrypoint
- `database/maxek.db` - SQLite database file (created automatically)
- `templates/` - Jinja2 page templates
- `static/css/` - CSS styles
- `static/js/` - JavaScript logic
- `static/uploads/` - Uploaded documents and proofs
- `static/photos/` - Uploaded staff/worker photos
- `reports/` - Generated Excel reports

## Features

- Dashboard overview
- Company Staff management
- Sub Contractor master
- Worker master with category logic
- Clients and Projects management
- Attendance with auto hour/OT calculation
- Petty Cash expense tracking
- Salary record management
- Excel export reports
- Role-based login

## Run

1. Open PowerShell in the project root.
2. Create/activate the virtual environment and install dependencies:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Run the app:
   ```powershell
   python app.py
   ```
4. Open in browser:
   ```text
   http://127.0.0.1:5000
   ```

## Default Login

- Username: `admin`
- Password: `admin`

## Notes

- The database is initialized automatically on first run.
- Reports are exported to the `reports/` folder.
- Uploaded photos and proof files are stored in `static/photos/` and `static/uploads/`.
