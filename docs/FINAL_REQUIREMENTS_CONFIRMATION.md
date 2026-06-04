# MAXEK ERP — Final Requirements Confirmation

**Status:** Approved baseline for Phase 1 go-live  
**Source:** User final requirements confirmation (June 2026)

This document is the authoritative requirements snapshot for Phase 1 planning, gap analysis, and acceptance testing.

---

## 1. User Roles

**Approved roles:** Super Admin, Management, HR, Accounts, Purchase, Store, Project Manager, Site Engineer, Subcontractor, Client (View Only).

Role-based permissions are required across all modules.

---

## 2. Attendance

- Manual entry
- Mobile entry
- Future GPS support
- Workers may be assigned to **multiple projects on the same day**

---

## 3. Payroll

**Category A:** 8 Hour Worker  
**Category B:** 10 Hour Worker

| Scenario | Rule |
|----------|------|
| Less than standard hours | Pay actual worked hours only |
| Standard hours | Full day salary |
| More than standard hours | Full day + OT |
| Hourly rate | 8hr = Daily Wage ÷ 8; 10hr = Daily Wage ÷ 10 |

---

## 4. Subcontractor Billing

- Designation-wise billing
- Worked days
- Worked hours
- OT hours
- Different rates per designation (Carpenter, Mason, Helper, Electrician, Plumber, Welder, Painter, etc.)

---

## 5. Advance Management

- Advance entry
- Outstanding balance tracking
- Auto deduction from salary
- Partial recovery

---

## 6. Food & Camp Recovery

- Daily entry
- Monthly recovery
- Worker-wise tracking

---

## 7. Approval Workflow

**Standard flow:**

`Draft` → `Prepared` → `Checked` → `Approved` → `Payment Released` → `Paid`

Audit trail is required for all status transitions.

---

## 8. Inventory

- Project-wise stock
- Material issue
- Material return
- Stock transfer
- Auto stock deduction on issue (and related movements)

---

## 9. Document Management

**Document types:** Contracts, Drawings, Invoices, POs, Letters, Site Photos, Technical Documents.

Version control is required.

---

## 10. Reports

| Report | Export |
|--------|--------|
| Attendance | PDF, Excel |
| Payroll | PDF, Excel |
| Subcontractor Bill | PDF, Excel |
| Material Consumption | PDF, Excel |
| Project Cost | PDF, Excel |
| Cash Flow | PDF, Excel |
| P&L | PDF, Excel |

---

## 11. Mobile App

**Future phase** (architecture must remain API-ready):

- Attendance
- Site photos
- Daily progress
- Approvals

---

## 12. Notifications

- **Required now:** In-app + Email
- **Future:** WhatsApp

---

## 13. PDF & Excel

Every module must support:

- PDF export
- Excel export
- Print

---

## 14. Future Modules

Architecture must be ready for (not Phase 1 go-live):

- BOQ
- Tender
- Equipment
- Vehicle
- Asset
- AI Reporting

---

## UI Requirements

- Modern executive dashboard
- Professional login screen
- Collapsible sidebar
- KPI cards
- Mobile responsive layout
- Corporate blue theme
- ERPNext / Odoo style presentation

---

## Phase 1 Go-Live Priority

The following modules **must be completed and tested first** before broader rollout:

| # | Module |
|---|--------|
| 1 | Dashboard |
| 2 | Attendance |
| 3 | Payroll |
| 4 | Subcontractor Billing |
| 5 | Inventory |
| 6 | Purchase |
| 7 | Petty Cash |
| 8 | Accounts |
| 9 | Document Management |
| 10 | Reports |

---

## Cross-Cutting (Phase 1)

These apply across the priority modules above:

- Approved role model and permission matrix
- Unified approval workflow with audit trail
- Multi-project same-day attendance
- PDF / Excel / Print on every Phase 1 screen
- In-app and email notifications
