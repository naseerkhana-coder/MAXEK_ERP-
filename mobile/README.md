# MAXEK ERP — Android (Capacitor)

Native Android app wrapping the React mobile UI. Data comes from **FastAPI** on port **8001** (not Streamlit).

## Architecture

| Part | Location |
|------|----------|
| React UI | `frontend/` → built into APK |
| API | `api_app.py` on VPS `:8001` |
| Android shell | `mobile/android/` |

## One-time setup (Windows)

```powershell
pip install -r requirements.txt
cd frontend
npm install
cd ..\mobile
npm install
```

## Build APK (every UI change)

```powershell
cd "C:\Users\rajee\OneDrive - Bab Al Theqa (1)\MAXEK_ERP"
.\scripts\build-mobile.ps1
```

Then **Android Studio** → **File → Open** → `mobile\android` → **Build → Build APK(s)**  
APK: `mobile\android\app\build\outputs\apk\debug\app-debug.apk`

## Deploy API to VPS

```powershell
python scripts\push_mobile_api.py --password "<ssh-password>"
```

Health check: http://72.61.224.204:8001/api/health

## Login on phone

| Environment | API server URL |
|-------------|----------------|
| Production (VPS) | `http://72.61.224.204:8001` |
| Office Wi‑Fi (PC) | `http://YOUR_PC_IP:8001` |
| Android emulator | `http://10.0.2.2:8001` |

Use the same ERP username/password as the web app.

## App modules

- Dashboard (KPIs)
- Attendance (create, edit, delete)
- Payroll approval (Admin / MD)
- DPR (create + list)
- Store / material requests (create + approve)
- Expenses (create + list)

See also `MOBILE_APP.md` in the project root.
