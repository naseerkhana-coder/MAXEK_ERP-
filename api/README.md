# api/

This folder is the **mobile API layer** for the MAXEK INDIA Construction ERP.

## Run API (local)

From repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn api_app:app --host 0.0.0.0 --port 8001
```

## Endpoints (current)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/login` | User login |
| GET | `/api/attendance` | List attendance |
| POST | `/api/attendance` | Record attendance |
| GET | `/api/payroll` | Payroll summary |
| GET | `/api/materials` | Material / purchase requisitions |
| POST | `/api/materials` | Submit requisition |
| POST | `/api/materials/{request_id}/status` | Approve / reject requisition |

## ERP menu alignment

The desktop ERP (`web_app.py`) exposes **14 modules** with ~170 screens. The mobile API currently covers field operations (attendance, payroll, material requests). Planned expansion:

- DPR submission
- Petty cash / site expenses
- Store issue requests
- Leave applications
- Approval inbox (pending items by role)

Menu definition and page keys live in `modules/navigation.py`. Route handlers: `modules/erp_router.py`.

## Authentication

All endpoints except `/api/health` and `/api/login` require a Bearer token returned from login.
