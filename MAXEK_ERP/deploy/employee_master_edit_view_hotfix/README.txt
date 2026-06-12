Employee Master Edit/View Hotfix

Upload these files to the same paths on the ERP server:

app.py -> MAXEK_ERP/app.py
templates/staff.html -> MAXEK_ERP/templates/staff.html
static/css/maxek-dashboard.css -> MAXEK_ERP/static/css/maxek-dashboard.css

After upload, restart the ERP service/application.

What this hotfix adds:
- View button for saved employee details.
- Edit button to correct and update saved employee records.
- Existing uploaded photo/documents stay saved unless a replacement file is selected.
- Search and export controls on Employee Records.
