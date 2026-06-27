# VPS deploy — Thick pro sidebar (reference dashboard style)

**VPS app root:** `/var/www/maxek-erp-flask/`  
**After upload:** `sudo systemctl restart maxek-erp`

| # | Local path | VPS remote path |
|---|------------|-----------------|
| 1 | `templates/partials/dashboard_shell_sidebar.html` | `/var/www/maxek-erp-flask/templates/partials/dashboard_shell_sidebar.html` |
| 2 | `static/css/maxek-pro-dashboard.css` | `/var/www/maxek-erp-flask/static/css/maxek-pro-dashboard.css` |
| 3 | `static/js/maxek-pro-dashboard.js` | `/var/www/maxek-erp-flask/static/js/maxek-pro-dashboard.js` |

**Verify:** Hard-refresh `/dashboard` — sidebar is 256px wide, nav rows ~46px tall, active item shows full-width rounded pill (blue / cornflower / purple per theme). Department portal **Tools** list uses same row style. No user block or sign-out in sidebar. Theme switcher (Midnight / Business / Classic) still works.
