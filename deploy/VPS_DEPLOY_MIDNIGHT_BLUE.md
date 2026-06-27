# VPS deploy — Midnight Blue Executive dashboard theme

**VPS app root:** `/var/www/maxek-erp-flask/`  
**After upload:** `sudo systemctl restart maxek-erp`

| # | Local path | VPS remote path |
|---|------------|-----------------|
| 1 | `app.py` | `/var/www/maxek-erp-flask/app.py` |
| 2 | `ui_shell_config.py` | `/var/www/maxek-erp-flask/ui_shell_config.py` |
| 3 | `templates/base_maxek.html` | `/var/www/maxek-erp-flask/templates/base_maxek.html` |
| 4 | `templates/dashboard.html` | `/var/www/maxek-erp-flask/templates/dashboard.html` |
| 5 | `templates/department_workspace.html` | `/var/www/maxek-erp-flask/templates/department_workspace.html` |
| 6 | `templates/partials/dashboard_shell_sidebar.html` | `/var/www/maxek-erp-flask/templates/partials/dashboard_shell_sidebar.html` |
| 7 | `static/css/maxek-pro-dashboard.css` | `/var/www/maxek-erp-flask/static/css/maxek-pro-dashboard.css` |

**Verify:** Hard-refresh `/dashboard` — slate-900 background, blue sidebar gradient, blue KPI glow (no pink/teal/amber mix); department tiles use blue-family accents; sidebar active nav shows blue glow bar.
