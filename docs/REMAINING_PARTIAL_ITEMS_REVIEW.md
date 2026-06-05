# MAXEK ERP — Remaining Partial Items Review

**Generated:** June 4, 2026  
**Checklist baseline:** [UAT_ACCEPTANCE_CRITERIA.md](./UAT_ACCEPTANCE_CRITERIA.md) · [UAT_READINESS_REPORT.md](./UAT_READINESS_REPORT.md)  
**Counts:** **38 Pass / 10 Partial / 0 Fail** (48 items, ~79% implementation readiness)

Use this document for business review of open gaps, go-live blockers, and operational sign-off (admin password, SMTP, backup).

---

## Partial items (10)

### 1. Advance Deduction (auto-apply on payroll generate)

| Field | Detail |
|--------|--------|
| **Module** | Payroll |
| **Description** | `Advance Recovery` exists in `DEDUCTION_TYPES` and supports manual `add_deduction`; advance recovery report is available. Open advances are **not** auto-applied when payroll is generated or saved—accounts must enter deductions manually. |
| **Business Impact** | Risk of missed advance recovery, overstated net pay, and reconciliation delays at month-end if HR/accounts forget manual steps. |
| **Severity** | Medium |
| **Estimated Fix Time** | 1–2 days (wire `advance_recovery_report_df` / open balances into `build_period_payroll` / save path, UAT on partial recovery rules) |
| **Go-Live Blocker?** | **No** — manual deduction path works today; defer or accept with written process if payroll volume is low and accounts sign off. |

---

### 2. Food Deduction (auto-post to payroll)

| Field | Detail |
|--------|--------|
| **Module** | Payroll |
| **Description** | Food allowance logic appears in attendance **preview** (`food_allowance/26` in `modules/pages.py`); `Food Recovery` deduction type exists but is **not** auto-posted to `worker_payroll_runs` on generate. |
| **Business Impact** | Inconsistent food recovery vs attendance; possible under-recovery of food advances or extra manual payroll adjustments. |
| **Severity** | Medium |
| **Estimated Fix Time** | 1 day (derive monthly food recovery from attendance/settings and post as deduction on generate) |
| **Go-Live Blocker?** | **No** — same as advance: manual `Food Recovery` deduction supported; blocker only if business requires zero-touch payroll. |

---

### 3. Fine Deduction (auto-deduction on payroll save)

| Field | Detail |
|--------|--------|
| **Module** | Payroll |
| **Description** | `Fine Deduction` type and manual entry exist; attendance UI references fines. No fine master or automatic fine aggregation on payroll save. |
| **Business Impact** | Fines may be applied late or omitted unless tracked outside the system. |
| **Severity** | Medium |
| **Estimated Fix Time** | 1–2 days (fine register or attendance-linked fines → auto deduction line; depends on whether fines are per-day or lump-sum) |
| **Go-Live Blocker?** | **No** — manual fine deductions available; accept with process if fines are infrequent. |

---

### 4. Project Wise Stock (project-level ledger)

| Field | Detail |
|--------|--------|
| **Module** | Inventory |
| **Description** | `load_site_wise_stock` sums **issued** quantity by project; there is no reconciled project-level stock ledger separate from the central `stock_register`. |
| **Business Impact** | Site managers cannot trust project-level on-hand balances for planning; may rely on central register + issues list instead of true project stock. |
| **Severity** | Medium |
| **Estimated Fix Time** | 3–5 days (project ledger table or derived balances: opening + issues − returns per project/material, UI and tests) |
| **Go-Live Blocker?** | **No** for go-live if operations accept **central register + GRN/issue/return** as source of truth (gate tests already pass auto-deduction). Blocker only if contracts require live project stock balances. |

---

### 5. Approval workflow — all financial modules (unified six-step)

| Field | Detail |
|--------|--------|
| **Module** | Approval Workflow |
| **Description** | Six statuses (`Draft` → `Paid`) and `transition()` are implemented. Site expenses, client/vendor bills, POs, subcontractor bills, and worker payroll use the standard workflow UI. **Not all** financial surfaces use the same six-step panel and audit pattern end-to-end. |
| **Business Impact** | Approvers may see different UX and audit depth by module; training burden and inconsistent compliance evidence. |
| **Severity** | Enhancement (process risk **Medium** if petty cash volume is high) |
| **Estimated Fix Time** | 2–3 days (audit remaining finance tabs, align labels and `render_workflow_action_panel` usage) |
| **Go-Live Blocker?** | **No** — core billing and payroll workflows are wired; gate and UAT scope exclude uniform petty UI until accepted. |

---

### 6. Petty cash — standard workflow UI

| Field | Detail |
|--------|--------|
| **Module** | Approval Workflow / Finance |
| **Description** | Petty cash uses a **custom** status path and `log_finance_audit` in `modules/finance_workflow.py` rather than the full six-step workflow panel on all petty tabs. |
| **Business Impact** | Petty cash approvals may not trigger the same email/audit trail as other finance documents unless staff follow the custom path. |
| **Severity** | Medium |
| **Estimated Fix Time** | 1–2 days (mount `render_workflow_action_panel` on petty entities or document equivalent states) |
| **Go-Live Blocker?** | **No** — petty cash report export exists; blocker only if policy mandates identical workflow UI for petty cash day one. |

---

### 7. Role Permissions (FINAL spec role names)

| Field | Detail |
|--------|--------|
| **Module** | Security |
| **Description** | `allowed_pages_for_role` and workflow guards exist. FINAL spec roles **Purchase**, **Store** (name), **Subcontractor portal**, and **Client (View Only)** are not fully aligned in `modules/navigation.py` / `modules/roles.py`. |
| **Business Impact** | Wrong menu access or missing dedicated portals; workaround via Admin/MD roles may over-privilege users. |
| **Severity** | Medium |
| **Estimated Fix Time** | 2–3 days (role enum, page matrix, workflow actor mapping, smoke tests per role) |
| **Go-Live Blocker?** | **No** if current role set (Admin, MD, Accountant, Store Keeper, etc.) covers go-live users; **Yes** if external clients or purchase-only users must log in on day one. |

---

### 8. Inventory Report (dedicated export)

| Field | Detail |
|--------|--------|
| **Module** | Reports |
| **Description** | `page_rpt_inventory` routes to the store register screen; there is **no** dedicated inventory Excel/PDF export comparable to attendance or petty cash reports. |
| **Business Impact** | Management cannot one-click export stock position for auditors or site reviews without using register UI or manual extracts. |
| **Severity** | Enhancement |
| **Estimated Fix Time** | 4–8 hours (report tab + `load_*` + Excel export mirroring `petty_cash_report.xlsx` pattern) |
| **Go-Live Blocker?** | **No** — stock movements and register are functional; export is convenience/reporting. |

---

### 9. Email — operational SMTP verification

| Field | Detail |
|--------|--------|
| **Module** | Email Notifications (operational) |
| **Description** | All five workflow notification steps are **Pass** in code (`notify_workflow_transition`, templates, unit tests). **Ops Verified** is pending: real `SMTP_*` in target environment and successful `python scripts/test_smtp.py --to …`. |
| **Business Impact** | Password reset, approval emails, and payment-released notices will not reach users if SMTP is misconfigured at go-live. |
| **Severity** | **Critical** (operational) |
| **Estimated Fix Time** | 2–4 hours (env config, DNS/firewall, test scenarios in `DEPLOY.md`—not dev coding) |
| **Go-Live Blocker?** | **Yes** — business expects email for approvals and reset; code-ready is insufficient without a logged successful send in production/staging. |

---

### 10. Email — recipient readiness (`users.email`)

| Field | Detail |
|--------|--------|
| **Module** | Email Notifications (data) |
| **Description** | Notifications resolve recipients from `users.email`. Empty or stale emails mean silent non-delivery even when SMTP works. |
| **Business Impact** | Approvers miss workflow emails; forgot-password flow fails for users without email on file. |
| **Severity** | Medium |
| **Estimated Fix Time** | 2–4 hours (data cleanup + admin checklist; optional validation on user save) |
| **Go-Live Blocker?** | **Yes** if workflow email is required for go-live sign-off; **No** if in-app workflow only until emails are populated. |

---

## Summary table (quick reference)

| # | Module | Item | Severity | Est. fix | Go-live blocker |
|---|--------|------|----------|----------|-----------------|
| 1 | Payroll | Advance auto-deduction | Medium | 1–2 days | No |
| 2 | Payroll | Food auto-deduction | Medium | 1 day | No |
| 3 | Payroll | Fine auto-deduction | Medium | 1–2 days | No |
| 4 | Inventory | Project-wise stock ledger | Medium | 3–5 days | No* |
| 5 | Approval | Unified six-step (all finance) | Enhancement | 2–3 days | No |
| 6 | Approval | Petty cash workflow UI | Medium | 1–2 days | No |
| 7 | Security | Role name / permission gaps | Medium | 2–3 days | No† |
| 8 | Reports | Inventory Excel/PDF report | Enhancement | 4–8 hrs | No |
| 9 | Email | SMTP ops test | Critical | 2–4 hrs | **Yes** |
| 10 | Email | `users.email` populated | Medium | 2–4 hrs | **Yes**‡ |

\* Blocker if contract requires project-level stock balances.  
† Blocker if Purchase / Client portal users required at launch.  
‡ Blocker when email notifications are mandatory for approvals.

---

## ADMIN SECURITY

- **Admin Password Changed:** YES / NO
- **Date Changed:**

---

## SMTP STATUS

- **SMTP Configured:** YES / NO
- **Password Reset Email:** PASS / FAIL
- **Approval Email:** PASS / FAIL
- **Payment Released Email:** PASS / FAIL

---

## DATABASE BACKUP

- **Backup Completed:** YES / NO
- **Backup Date:**
- **Restore Test Completed:** YES / NO

---

## FINAL RECOMMENDATION

- [ ] **Not Ready**
- [x] **Conditional Go-Live** *(recommended as of June 4, 2026)*
- [ ] **Production Ready**

**Reason:** Implementation checklist is **38/10/0** (~79% ready); Phase 1 gate blockers are **4/4 PASS** at code/test level, so **internal UAT is allowed**. Ten partial items remain: seven are **code gaps** deferrable with written acceptance (payroll auto-deductions, project stock ledger, workflow UI parity, role names, inventory export); **two are operational email readiness** (SMTP live test + user emails) and should be completed before production cutover. **Admin password change**, **database backup/restore test**, and **SMTP scenario sign-off** below are still blank and must be confirmed by IT/Admin. Full payroll automation and project stock ledger are **not** blanket blockers per [UAT_READINESS_REPORT.md](./UAT_READINESS_REPORT.md) if business signs off on manual processes and known gaps.

---

## References

- [UAT_READINESS_REPORT.md](./UAT_READINESS_REPORT.md)
- [UAT_ACCEPTANCE_CRITERIA.md](./UAT_ACCEPTANCE_CRITERIA.md)
- [PRODUCTION_DEPLOYMENT_CHECKLIST.md](./PRODUCTION_DEPLOYMENT_CHECKLIST.md)
- [UAT_HANDOFF.md](./UAT_HANDOFF.md)
