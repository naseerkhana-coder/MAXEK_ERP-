# VPS deploy — Pro dashboard theme switcher (3 dark themes)

**VPS app root:** `/var/www/maxek-erp-flask/`  
**After upload:** `sudo systemctl restart maxek-erp`

| # | Local path | VPS remote path |
|---|------------|-----------------|
| 1 | `templates/base_maxek.html` | `/var/www/maxek-erp-flask/templates/base_maxek.html` |
| 2 | `templates/partials/dashboard_shell_header.html` | `/var/www/maxek-erp-flask/templates/partials/dashboard_shell_header.html` |
| 3 | `templates/partials/dashboard_shell_module_header.html` | `/var/www/maxek-erp-flask/templates/partials/dashboard_shell_module_header.html` |
| 4 | `templates/partials/dashboard_shell_theme_switcher.html` | `/var/www/maxek-erp-flask/templates/partials/dashboard_shell_theme_switcher.html` |
| 5 | `static/css/maxek-pro-dashboard.css` | `/var/www/maxek-erp-flask/static/css/maxek-pro-dashboard.css` |
| 6 | `static/js/maxek-pro-dashboard.js` | `/var/www/maxek-erp-flask/static/js/maxek-pro-dashboard.js` |

**Verify:** Hard-refresh `/dashboard` — header shows **Midnight / Business / Classic** pill switcher. Click each theme; choice persists after reload and on module/department pages (`localStorage` key `maxek_pro_theme`).

| Theme | `data-pro-theme` | Look |
|-------|------------------|------|
| Midnight Blue Executive (default) | `midnight` | Slate `#0f172a`, blue `#3b82f6` accents |
| Business Dark | `business` | Deep navy cards, cornflower `#4f7cff` active nav |
| ERP Classic Dark | `erp-classic` | `#121212` base, purple/green action card accents |
