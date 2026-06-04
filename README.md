# MAXEK ERP SYSTEM

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run web_app.py
```

Or double-click `start_web.bat`.

## Recommended folder structure (in-progress)

```text
erp-project/
├── backend/     # Streamlit ERP UI (currently still uses root web_app.py)
├── api/         # FastAPI layer for mobile app
├── frontend/    # Future React/web frontend (optional)
├── mobile/      # Capacitor / Android / iOS wrapper
├── uploads/     # user uploads (files/photos)
└── database/    # SQLite db file lives here (not in git)
```

## Stack (current)

| Layer | Technology |
|-------|------------|
| UI | Streamlit (`web_app.py`) |
| Database | **SQLite** — `database/maxek_payroll.db` |
| Modules | Finance, DPR, Billing, Clients & Projects, etc. |

GitHub and production deploy: see **[DEPLOY.md](DEPLOY.md)**.

## Project Type
Construction Company ERP System

## Project Overview
MAXEK ERP System is a professional ERP platform designed for construction company operations, labor management, payroll management, client and project tracking, subcontractor management, payments, expenses, and daily office usage.

**Approved Phase 1 requirements:** [docs/FINAL_REQUIREMENTS_CONFIRMATION.md](docs/FINAL_REQUIREMENTS_CONFIRMATION.md) · **Gap analysis:** [docs/PHASE1_GAP_ANALYSIS.md](docs/PHASE1_GAP_ANALYSIS.md) · **Executive summary:** [docs/PHASE1_EXECUTIVE_SUMMARY.md](docs/PHASE1_EXECUTIVE_SUMMARY.md)

**UAT:** [docs/UAT_HANDOFF.md](docs/UAT_HANDOFF.md) (post-deploy login & credentials) · [docs/UAT_ACCEPTANCE_CRITERIA.md](docs/UAT_ACCEPTANCE_CRITERIA.md) · [docs/UAT_TEST_CASES.md](docs/UAT_TEST_CASES.md) · [docs/UAT_READINESS_REPORT.md](docs/UAT_READINESS_REPORT.md) · [docs/REMAINING_PARTIAL_ITEMS_REVIEW.md](docs/REMAINING_PARTIAL_ITEMS_REVIEW.md) (10 partial items, go-live sign-off) · [docs/PRODUCTION_DEPLOYMENT_CHECKLIST.md](docs/PRODUCTION_DEPLOYMENT_CHECKLIST.md)

The system should support daily business operations with a clean modern UI, role-based access, automation of repetitive tasks, and a structure that can grow from SQLite to PostgreSQL in the future.

## Technology Stack

### Frontend
- Streamlit or React
- Responsive UI
- Mobile-friendly layout

### Backend
- Python Flask

### Database
- SQLite for the initial version
- Easily upgradeable to PostgreSQL later

## Main Menu Structure (14 modules)

The Streamlit sidebar is defined in `modules/navigation.py` with collapsible sub-groups.

1. **Dashboard** — Management, Project, Accounts, HR, Store dashboards; Pending Approvals; Notifications; Calendar
2. **Master Management** — Client, Contractor, Vendor, Employee, Material, Equipment, Vehicle, Location masters
3. **Project Management** — Project setup, Site, BOQ, Work orders, DPR, Billing, Project costing
4. **Purchase Management** — Requisition → RFQ → Quotation → PO → GRN → Invoice → Vendor payment
5. **Store & Inventory** — Receipt, Issue, Return, Transfer, Adjustment, Site stock, Alerts, Valuation
6. **HR & Payroll** — Attendance, Leave, Transfer, Overtime, Payroll, Salary slip, Labour attendance
7. **Accounts & Finance** — COA, Vouchers, Banking, GST, Cash/Bank books, TB, P&L, Balance sheet
8. **Petty Cash Management** — Request → Allocation → Expense → Verification → Approval → Settlement
9. **Asset & Equipment Management** — Register, Allocation, Fuel, Maintenance, Breakdown, Costing
10. **Vehicle Management** — Allocation, Trip sheet, Fuel, Service, Insurance, Cost reports
11. **Document & Letter Management** — Incoming/outgoing letters, Document control (contracts, drawings, site, legal)
12. **Approval Center** — Purchase, Payment, Petty cash, Leave, Work order, Vendor, Client, Project
13. **Reports & MIS** — Project, Accounts, Store, HR, Management profitability and cash flow
14. **Settings & Administration** — Users, Roles, Email, WhatsApp, Number series, Backup, Audit, ERP config

### Business workflow

```
Client → Project → Site → BOQ → Work Order → Purchase → Store → Accounts → Billing → Reports
Sub Contractor → Work Order → Attendance → Billing → Payment
Site Petty Cash → Expense Entry → Invoice Upload → Accounts Verification → Approval → Settlement
```

Screen routing: `modules/erp_router.py` · New module screens: `modules/erp_screens.py` · Data layer: `modules/erp_data.py`

### PDF document templates

Shared layout: `modules/pdf_templates.py` (company block, tables, ₹ formatting, signature). Generators: `modules/document_pdfs.py`.

| Document | Generator | UI path |
|----------|-----------|---------|
| Worker salary slip (8hr/10hr) | `generate_worker_salary_slip_pdf` | HR → Worker Payroll → **Salary Slip** tab |
| Staff payslip | `generate_staff_payslip_pdf` | HR → Staff Payroll → **Payroll Register** → Download PDF |
| Client invoice / bill | `generate_client_invoice_pdf` | Project → Billing → **Register & Print** |
| Sub-contractor bill | `generate_subcontractor_bill_pdf` | Project → Billing → **Register & Print** |
| Purchase / expense invoice | `generate_purchase_invoice_pdf` | Accounts → Finance Register → Expense invoices |
| Payment voucher | `generate_payment_voucher_pdf` | `document_pdfs` (wire to finance UI when needed) |

Legacy Tk payslip (`src/pdf_generator.py`) is superseded by the modules above.

## Important UI Requirements
- Modern clean UI
- White background
- Blue theme
- Responsive design
- Mobile-friendly screens
- Searchable dropdowns
- Sticky save button
- Auto-calculation fields
- Table filters
- Export to PDF and Excel
- Use `DD/MM/YYYY` date format everywhere

## Region Rule
Remove these fields:
- Country
- State
- Emirate

Use only:
- Region

Example regions:
- Kerala
- Tamil Nadu
- Karnataka
- Nepal

## Client Master Module
Fields:
- Client ID
- Company Name
- Contact Person
- Mobile Number
- Alternate Number
- Email
- GST Number
- PAN Number
- Address
- Region
- City
- Agreement Start Date
- Agreement End Date
- Client Type
- Status
- Notes
- Document Upload

## Project Master Module
Fields:
- Project ID
- Client Name
- Project Name
- Project Code
- Location
- Region
- Site Incharge
- Start Date
- End Date
- Labour Count
- Budget
- Status
- Remarks

## Employee Management Module

### Employee Types
- Company Staff
- Sub Contractor Worker

### Basic Details
- Employee ID
- Employee Name
- Photo Upload
- Mobile Number
- Address
- Region
- Native Place
- Blood Group
- Aadhaar Number
- PAN Number
- Joining Date
- Leaving Date
- Status

### Job Details
- Company or Sub Contractor
- Project
- Department
- Designation
- Reporting Manager
- Salary Type
- Salary Amount
- OT Applicable
- OT Rate
- Shift
- Experience
- Skills
- Remarks

### Document Attachments
- Aadhaar
- PAN
- Passport
- Visa
- Certificates
- Agreement

## Attendance Module
Fields:
- Date
- Employee Name
- Employee ID
- Employee Type
- Department
- Designation
- Project
- Sub Contractor
- In Time
- Out Time
- Break Time
- Total Hours
- OT Hours
- Status
- Remarks

## Payroll Module
Automatic payroll calculation is required for:
- Monthly staff
- Daily workers
- OT
- Advance deductions
- Final salary

## Payments Module
Fields:
- Voucher Number
- Date
- Payment Type
- Payment Head
- Pay To Type
- Pay To Name
- Project
- Client
- Amount
- Payment Mode
- Reference Number
- Remarks
- Bill Upload

### Payment Type Options
- Salary Payment
- Advance Payment
- Sub Contractor Payment
- Material Payment
- Fuel Expense
- Site Expense
- Transport Expense
- Office Expense
- Labour Payment
- Other Expense

## Expenses Module
Fields:
- Expense ID
- Date
- Expense Head
- Project
- Client
- Paid To
- Amount
- Payment Mode
- Approved By
- Bill Upload
- Remarks

## Sub Contractor Module
Fields:
- Sub Contractor ID
- Company Name
- Contact Person
- Mobile Number
- Aadhaar Number
- PAN Number
- Address
- Trade
- Agreement Upload
- Active Projects
- Worker Count
- Status

## Dashboard
Show:
- Total Employees
- Total Workers
- Active Projects
- Total Clients
- Today Attendance
- Pending Salary
- Monthly Expense
- Cash In Hand

## Reports Module
- Attendance Report
- Salary Report
- Expense Report
- Client Payment Report
- OT Report
- Employee Joining Report
- Employee Exit Report
- Project-wise Labour Report

## Settings Module
- Departments
- Designations
- Regions
- Projects
- Expense Heads
- Payment Heads
- Salary Rules
- OT Rules

## Database Tables
- `clients`
- `projects`
- `employees`
- `attendance`
- `payroll`
- `payments`
- `expenses`
- `subcontractors`
- `departments`
- `designations`
- `regions`
- `document_uploads`

## Automations
- Auto Employee ID
- Auto Voucher Number
- Auto OT Calculation
- Auto Salary Calculation
- Auto Attendance Summary

## Daily Cash Flow
- Opening Balance
- Cash In
- Cash Out
- Closing Balance

## Role-Based Login
- Admin
- HR
- Accountant
- Project Manager
- Site Engineer

## Final Note
Build a professional ERP system optimized for:
- Construction company operations
- Labour management
- Payroll management
- Client and project tracking
- Sub contractor management
- Daily office usage
