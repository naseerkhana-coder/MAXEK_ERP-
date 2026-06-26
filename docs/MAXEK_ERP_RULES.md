# MAXEK Construction ERP Rules

Development constraints for all Cursor work on MAXEK Construction ERP. Follow these rules on every task.

## Rules

### 1. Do NOT redesign any UI.

The existing UI reflects approved workflows and user training. Redesigns introduce regression risk and delay backend fixes that unblock daily site and office operations.

### 2. Do NOT rename modules.

Module names map to navigation, permissions, URLs, and documentation across construction, finance, and HR teams. Renaming breaks bookmarks, integrations, and user muscle memory.

### 3. Do NOT remove existing features.

Features may appear unused but often support edge cases (retention, variations, multi-site payroll). Removal without audit can break compliance and reporting.

### 4. Fix backend before frontend.

Broken APIs and data models cause misleading UI states. Stabilize routes, queries, and business logic first so the frontend reflects truth.

### 5. Reuse existing templates.

Templates encode layout, branding, and module chrome. New pages should extend the same base templates for consistency and faster delivery.

### 6. Reuse common CRUD components.

List, form, filter, and pagination patterns already exist. Reusing them avoids duplicate bugs and keeps behavior uniform across BOQ, DPR, payroll, and petty cash modules.

### 7. Reuse common toolbar.

Toolbar actions (save, export, print, back) are wired to shared handlers. A custom toolbar per screen fragments UX and duplicates permission checks.

### 8. Every button must have a working backend route.

Orphan buttons erode trust on site and in accounts. Wire each action to a real endpoint before marking work complete.

### 9. Every route must return valid data.

Empty, malformed, or error responses break grids and reports. Validate shape, status codes, and edge cases (no rows, partial BOQ, closed project).

### 10. Every fix must be tested before commit.

Construction ERP mistakes affect cost, payroll, and compliance. Exercise the changed flow manually or with tests before committing.

### 11. Commit after every completed task.

Small, focused commits preserve rollback points and make audits traceable to a single fix or feature slice.

### 12. Never modify unrelated modules.

Scope creep across modules increases merge conflict and regression risk. Change only files required for the stated task.
