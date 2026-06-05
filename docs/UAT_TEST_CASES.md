# MAXEK ERP — UAT Test Cases

Structured user acceptance test cases for pre–go-live validation. Execute in a test database with representative master data.

| ID | Module | Scenario | Steps | Expected Result | Role |
|----|--------|----------|-------|-----------------|------|
| UAT-ATT-01 | Attendance | Mark site worker present with in/out times | 1. Open HR → Attendance. 2. Select worker with 8hr duty, daily wage 800. 3. Enter 6h worked. 4. Save. | Day pay = Rs 600 (pro-rata). No OT. | Site Engineer |
| UAT-ATT-02 | Attendance | Full 8hr day | 1. Same worker, 8h worked. 2. Save. | Day pay = Rs 800. | Site Engineer |
| UAT-ATT-03 | Attendance | OT on 8hr worker | 1. OT eligible Yes. 2. Enter 10h. 3. Save. | Base Rs 800 + OT 2h × Rs 100 = Rs 1000. | Site Engineer |
| UAT-ATT-04 | Attendance | 10hr duty partial | 1. Worker 10hr, wage 1000. 2. Enter 8h. | Pay Rs 800. | Site Engineer |
| UAT-ATT-05 | Attendance | 10hr duty with OT | 1. 12h worked. 2. Save. | Base Rs 1000 + OT Rs 200 = Rs 1200. | Site Engineer |
| UAT-PAY-01 | Worker Payroll | Generate advance cycle | 1. Worker Payroll → Attendance → Salary. 2. Period 1–15. 3. Generate salary. | Run created Draft/Prepared with gross and deductions. | HR & Payroll |
| UAT-PAY-02 | Worker Payroll | Workflow to Paid | 1. Review → Submit/Prepare → Check → Approve. 2. Payment tab → Release + Mark Paid with reference. | Status Paid; payment_reference stored; audit log entries. | HR, Accounts Manager |
| UAT-PAY-03 | Worker Payroll | Deductions | 1. Add Advance, Food, Fine deductions. 2. Recalculate net. | Net = gross − sum(deductions). | HR & Payroll |
| UAT-PAY-04 | Worker Payroll | Salary slip PDF | 1. Reports → Salary Slip. 2. Select paid run. 3. Download PDF. | PDF shows worker, period, gross, deductions, net. | HR & Payroll |
| UAT-SUB-01 | Subcontractor Billing | Measurement (BOQ) bill | 1. Billing → Subcontractor → Measurement mode. 2. Add BOQ entries for month. 3. Generate bill. | Bill type Quantity; BOQ amount only; preview/PDF match. | Accounts Manager |
| UAT-SUB-02 | Subcontractor Billing | Payroll (attendance) bill | 1. Attendance for sub workers in month. 2. Payroll mode. 3. Generate. | Bill type Manpower; labour + OT; no BOQ line. | Accounts Manager |
| UAT-SUB-03 | Subcontractor Billing | Workflow | 1. Register → select bill. 2. Prepare → Check → Approve → Release → Paid. | Status transitions; email stub/log if SMTP off. | PM, Accounts |
| UAT-PUR-01 | Purchase | Create PO | 1. Purchase → Purchase Order. 2. Create draft PO with vendor and amount. | PO in Draft with document number. | Store Keeper |
| UAT-PUR-02 | Purchase | PO approval chain | 1. Select PO. 2. Submit → Check → Approve → Release Payment → Mark Paid. | Status updates; prepared_by/checked_by fields set. | Store, Accounts |
| UAT-INV-01 | Inventory | Material request | 1. Site engineer submits material request. 2. PM approves via workflow. | Status moves Prepared → Checked → Approved. | Site Engineer, PM |
| UAT-INV-02 | Inventory | GRN against PO | 1. Record GRN with PO reference. | GRN saved; stock movement per existing rules. | Store Keeper |
| UAT-PC-01 | Petty Cash | Request to release | 1. Petty cash request. 2. Verify → Approve → Release. | Balance updated on release; workflow audit. | Site, Accounts |
| UAT-PC-02 | Petty Cash | Site expense petty | 1. Expense entry petty source. 2. Submit → verify → approve. 3. Post. | Petty balance deducts on final approval only. | Site, Accounts, PM |
| UAT-FIN-01 | Site Expense | Standard workflow buttons | 1. Finance → Expense verification. 2. Use Submit/Check/Approve/Release/Mark Paid panel. | Canonical workflow applied; legacy statuses mapped. | Accounts |
| UAT-FIN-02 | Vendor Bill | Purchase invoice workflow | 1. Finance register → Expense invoices. 2. Workflow on vendor bill. | vendor_bill entity transitions; payment ref on paid. | Accounts |
| UAT-FIN-03 | Client Bill | Client bill approval | 1. Billing → Client bill. 2. Register workflow panel. | client_bill workflow through Paid. | Accounts, MD |
| UAT-NOT-01 | Notifications | SMTP configured | 1. Set SMTP_* env vars. 2. Trigger Prepared transition. | Email sent to role users with email in users table. | Admin |
| UAT-NOT-02 | Notifications | SMTP not configured | 1. Unset SMTP. 2. Trigger Approved. | In-app notification; log line "would send email". | Admin |

## Sign-off

| Tester | Date | Pass / Fail | Notes |
|--------|------|-------------|-------|
| | | | |
