# MAXEK ERP — Complete Android Mobile App

React UI + FastAPI + Capacitor Android.

## Architecture

| Layer | Folder | Run |
|-------|--------|-----|
| API | `api_app.py` | `python -m uvicorn api_app:app --host 0.0.0.0 --port 8001` |
| Mobile UI | `frontend/` | Vite React (built into APK) |
| Android shell | `mobile/android/` | Open in Android Studio |

## One-time setup

```powershell
pip install -r requirements.txt
cd frontend
& "C:\Program Files\nodejs\npm.cmd" install
cd ..\mobile
& "C:\Program Files\nodejs\npm.cmd" install
```

## Build & install on phone (every update)

### Terminal 1 — API (must run on PC or VPS)

```powershell
cd "C:\Users\rajee\OneDrive - Bab Al Theqa (1)\MAXEK_ERP"
python -m uvicorn api_app:app --host 0.0.0.0 --port 8001
```

### Terminal 2 — Build React + sync Android

```powershell
cd "C:\Users\rajee\OneDrive - Bab Al Theqa (1)\MAXEK_ERP\mobile"
npm run cap:sync
```

### Android Studio

1. **File → Open** → `mobile\android`
2. Select your **phone** → **Run ▶**

### First login on phone

- **API server:** `http://YOUR_PC_IP:8001` (same Wi‑Fi as phone)
- **Username / password:** same as ERP (`admin` / `1234` by default)

Emulator API URL: `http://10.0.2.2:8001`

## Modules in the app

- Dashboard (KPIs)
- Attendance (create + list)
- Payroll approval (MD/Admin)
- DPR (create + list)
- Store / material requests (create + approve)
- Expenses (create + list)

## Share APK internally

Android Studio → **Build → Build APK(s)**  
Output: `mobile\android\app\build\outputs\apk\debug\app-debug.apk`

## Production (VPS — 72.61.224.204)

1. Deploy API:
   ```powershell
   python scripts\push_mobile_api.py --password "<ssh-password>"
   ```
2. Confirm: http://72.61.224.204:8001/api/health
3. Build APK (`scripts\build-mobile.ps1`) — production URL is in `frontend/.env.production`
4. Install APK on staff phones; login with `http://72.61.224.204:8001` (pre-filled after build)

Optional: put Nginx in front of port 8001 with HTTPS and update `VITE_API_BASE` before rebuilding the APK.
