# MAXEK Construction ERP — Module Definition of Done

A module is **complete** only when every item in the checklist below passes in the browser. Use this document for Phase 2 module validation, QA sign-off, and Cursor task completion.

**Related docs:** [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md) · [PHASE2_MODULE_VALIDATION.md](./PHASE2_MODULE_VALIDATION.md) (if present) · [PHASE2_CURSOR_TASKS.md](./PHASE2_CURSOR_TASKS.md) (if present)

---

## Checklist (all 20 items required)

| # | Item | Pass criteria |
|---|------|---------------|
| 1 | Dashboard opens | Main dashboard loads after login with no blank screen or error banner |
| 2 | Module opens | Module page loads from sidebar/menu without 404 or redirect loop |
| 3 | New works | **New** creates a blank form or draft record |
| 4 | Save works | **Save** persists data; reload shows saved values |
| 5 | Open works | **Open** loads an existing record from list or picker |
| 6 | View works | **View** shows read-only detail without edit controls (or read-only mode) |
| 7 | Edit works | **Edit** loads record in editable form; changes can be saved |
| 8 | Delete works | **Delete** removes record (with confirm); list updates |
| 9 | Search works | Search/filter text returns matching rows |
| 10 | Status filter works | Status dropdown/tabs filter list correctly |
| 11 | Date filter works | Date range or date picker filters list correctly |
| 12 | Sort works | Column sort or sort control orders rows as expected |
| 13 | Refresh works | **Refresh** reloads list/data without full page error |
| 14 | Export Excel works | Excel export downloads and opens with expected data |
| 15 | Export PDF works | PDF export downloads and displays expected content |
| 16 | Print works | Print preview/page prints without layout break or missing data |
| 17 | Run Report works | Report runs and shows or downloads output |
| 18 | No 404 errors | Network tab and page show no HTTP 404 for module routes/assets |
| 19 | No 500 errors | Network tab and page show no HTTP 500 for module API calls |
| 20 | No JavaScript console errors | Browser DevTools Console has no errors during full flow |

---

## How to verify each item (browser testing)

Use Chrome or Edge with DevTools open (**F12**). Log in as a user with access to the module under test.

### 1. Dashboard opens

1. Log in at `http://127.0.0.1:5000` (or deployed URL).
2. Confirm dashboard renders: KPIs, menu, and no error toast.
3. **Pass:** Page title and main content visible; no 404/500 in Network tab.

### 2. Module opens

1. Click the module in the sidebar or department hub.
2. **Pass:** Module list or landing page loads; URL matches expected route; no 404.

### 3. New works

1. Click **New** (or equivalent).
2. **Pass:** Empty form or new draft appears; required fields are editable.

### 4. Save works

1. Fill required fields with test data (use a unique reference if applicable).
2. Click **Save**.
3. Reload the page or re-open the record.
4. **Pass:** Success message (if shown); data persists after reload.

### 5. Open works

1. From the list, select a row and click **Open** (or double-click row).
2. **Pass:** Record detail/form loads with correct ID and field values.

### 6. View works

1. Open a record in view mode (View button or view-only URL).
2. **Pass:** All fields visible; save/delete disabled or absent unless policy allows.

### 7. Edit works

1. Open a record in edit mode; change a non-key field.
2. Save and re-open.
3. **Pass:** Changes persist; validation errors shown for invalid input.

### 8. Delete works

1. Create or pick a disposable test record.
2. Click **Delete**; confirm if prompted.
3. **Pass:** Record removed from list; API returns success; no 500.

### 9. Search works

1. Enter a known substring in the search box (name, number, project code).
2. **Pass:** List shows only matching rows; clearing search restores full list.

### 10. Status filter works

1. Change status filter (e.g. Active / Closed / Draft).
2. **Pass:** List updates; rows match selected status; counts consistent if shown.

### 11. Date filter works

1. Set from/to dates covering known records.
2. **Pass:** Only records in range appear; boundary dates behave correctly.

### 12. Sort works

1. Click sortable column header or sort dropdown.
2. **Pass:** Order changes ascending/descending; data order is logically correct.

### 13. Refresh works

1. Click **Refresh** (or toolbar reload).
2. **Pass:** List reloads; latest data shown; no full-page error.

### 14. Export Excel works

1. Click **Export Excel** (with or without filters applied).
2. **Pass:** `.xlsx` or `.xls` downloads; opens in Excel/LibreOffice with expected columns and rows.

### 15. Export PDF works

1. Click **Export PDF**.
2. **Pass:** PDF downloads; content readable; headers and totals correct.

### 16. Print works

1. Click **Print** or use browser print on print template.
2. **Pass:** Print preview shows complete layout; no clipped tables or missing headers.

### 17. Run Report works

1. Select report parameters if required; click **Run Report**.
2. **Pass:** Report displays or downloads; data matches module records for same filters.

### 18. No 404 errors

1. Perform full flow: open module, list, new, save, open, export.
2. In DevTools **Network**, filter by **404**.
3. **Pass:** Zero 404 responses for HTML, API, JS, CSS used by the module.

### 19. No 500 errors

1. Same flow as above; filter Network by **500**.
2. **Pass:** Zero 500 responses on module routes and APIs.

### 20. No JavaScript console errors

1. With **Console** tab open, repeat the full CRUD + filter + export flow.
2. **Pass:** No red errors; warnings only if documented and accepted.

---

## Module sign-off template

Copy this table per module. All rows must be **Pass** before the module is marked done.

**Module name:** _________________________  
**Date tested:** _________________________  
**Tester:** _________________________  
**Environment:** ☐ Local (`127.0.0.1:5000`) ☐ Staging ☐ Production  
**Build / commit:** _________________________

| # | Checklist item | Pass / Fail | Notes |
|---|----------------|-------------|-------|
| 1 | Dashboard opens | | |
| 2 | Module opens | | |
| 3 | New works | | |
| 4 | Save works | | |
| 5 | Open works | | |
| 6 | View works | | |
| 7 | Edit works | | |
| 8 | Delete works | | |
| 9 | Search works | | |
| 10 | Status filter works | | |
| 11 | Date filter works | | |
| 12 | Sort works | | |
| 13 | Refresh works | | |
| 14 | Export Excel works | | |
| 15 | Export PDF works | | |
| 16 | Print works | | |
| 17 | Run Report works | | |
| 18 | No 404 errors | | |
| 19 | No 500 errors | | |
| 20 | No JavaScript console errors | | |

**Overall result:** ☐ **PASS** (all 20 Pass) ☐ **FAIL** (list failing items: _______________)

**Sign-off:** _________________________ **Date:** _________________________

---

## Policy

- A Phase 2 module task or Cursor task is **not complete** until all 20 items pass.
- Partial completion (e.g. CRUD only without export) does **not** satisfy Definition of Done.
- Log failures in module validation tracker with item number and reproduction steps.
- Fix backend routes and APIs before re-testing UI (see [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md)).
