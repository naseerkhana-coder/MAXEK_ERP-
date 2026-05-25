# MAXEK ERP SYSTEM

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run web_app.py
```

Or double-click `start_web.bat`.

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

## Main Menu Structure
1. Dashboard
2. Employee Management
3. Attendance
4. Payroll
5. Payments
6. Expenses
7. Clients
8. Projects
9. Sub Contractors
10. Reports
11. Settings

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
