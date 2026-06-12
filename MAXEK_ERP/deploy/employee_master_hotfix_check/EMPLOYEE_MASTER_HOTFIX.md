# Employee Master Hotfix

This hotfix removes the old Employee Master heading/help text and fixes the next employee code.

Upload these files to the live ERP application folder:

- `app.py` -> `/var/www/maxek_erp/app.py`
- `templates/staff.html` -> `/var/www/maxek_erp/templates/staff.html`

After upload, restart the ERP service:

```bash
sudo systemctl restart maxek-erp
```

Then refresh the browser with Ctrl+F5.

The Employee Master page should show:

- Form heading: `Employee Data Entry`
- Table heading: `Employee Records`
- Employee code column in the employee list
