# LoanPulse UI Modernization — Phase 4: Customer Dashboard & Experience Redesign

## 1. Executive Summary

Phase 4 delivers a complete visual and experiential modernization of the customer-facing views in LoanPulse, inspired by the clean, typography-driven, and intuitive fintech design patterns of **Stripe** and **Linear**. All enhancements build directly on the Phase 1 design foundation and Phase 2–3 shared components, strictly preserving the existing Flask and Jinja2 architecture, SQLAlchemy models, SQLite schema, route signatures, business calculations, CSRF protection, and multi-tab session management.

The modernized customer experience encompasses nine primary views:
1. **Customer Dashboard** (`src/templates/customer/dashboard.html`)
2. **Loan Applications History** (`src/templates/customer/applications.html`)
3. **New Loan Application Form** (`src/templates/customer/apply.html`)
4. **Application Summary Confirmation** (`src/templates/customer/apply_summary.html`)
5. **Application Details & Operational Lifecycle Tracker** (`src/templates/customer/status.html`)
6. **KYC Verification & Document Vault** (`src/templates/customer/kyc.html`)
7. **Customer Profile & Completeness Workspace** (`src/templates/customer/profile.html`)
8. **Notifications & Activity History** (`src/templates/notifications/index.html`)
9. **Interactive Loan EMI Calculator** (`src/templates/calculator.html`)

---

## 2. Scope & Safety Invariants

| Safety Invariant | Status | Verification Detail |
| :--- | :--- | :--- |
| **Local-Only Policy** | Confirmed | Zero Git pushes, zero Render deployments, zero remote configuration modifications. |
| **No Premature Commits** | Confirmed | No Git commits created without explicit user instruction. |
| **Backend & Architecture Preservation** | Confirmed | Flask routes, SQLAlchemy models, SQLite schema, migrations, loan calculations, and multi-tab window sessions (`lp_wid`) remain intact. |
| **Role-Based Access Control (RBAC)** | Confirmed | Strict customer isolation maintained; customers cannot access `/officer/queue`, `/officer/disbursements`, or `/manager/queue` (HTTP 403). |
| **Privacy & Security Masking** | Confirmed | Staff personal names are masked with role labels (`Loan Officer`, `Loan Manager`) on customer views. Internal underwriting notes are never exposed. |
| **Preserved Test Hooks & DOM IDs** | Confirmed | All required DOM elements (`statusAppId`, `statusValue`, `statusDate`, `statusAmount`, `timeline`, `unreadCount`, `notificationRows`) and text strings preserved verbatim. |
| **Strict Scope Boundary** | Confirmed | Loan Officer (Phase 5) and Loan Manager (Phase 6) workspaces were not modified. |

---

## 3. Detailed View Enhancements

### A. Customer Dashboard (`src/templates/customer/dashboard.html`)
- **Customer Welcome Header**: Clean greeting lockup displaying `Welcome back, {{ current_user.full_name }}`, avatar badge, cache-busting refresh button with animated SVG spin, and a high-priority "Apply for a Loan" CTA.
- **Dynamic KYC Verification Hero Banner (`.kyc-banner`)**:
  - Dynamically renders border-left accents and semantic pill badges for `VERIFIED`, `PENDING REVIEW`, `REJECTED`, and `NOT STARTED`.
  - Integrates the profile completeness progress meter with live percentage readout.
  - Contextual action buttons: "View Documents", "Check KYC Status", "Fix & Resubmit KYC", or "Complete KYC".
- **Fintech Metric Cards (`.grid4`)**:
  - 4 responsive KPI tiles displaying database-backed metrics: Total Applications, Pending Applications, Approved Applications, and Disbursed Applications.
  - Tabular typography (`font-variant-numeric: tabular-nums`) with high contrast in both light and dark themes.
- **Available Loan Products Catalog (`.loan-product-grid`, `.loan-product-card`)**:
  - Linear-inspired product cards featuring product code, annual interest rate pill, description, permitted principal range, tenure limits, and direct "Apply Now" button.
- **Recent Applications Table & Notifications**:
  - Polished table container with monospaced IDs, status pills, and empty states utilizing the standardized `.empty-state` component from Phase 3.

### B. Loan Applications History (`src/templates/customer/applications.html`)
- Structured application history table with tabular currency figures, term length, purpose categories, status indicators, and view actions.
- Graceful empty state when no applications are present.

### C. Loan Application Form (`src/templates/customer/apply.html`)
- **Linear-Style Progress Stepper (`.steps`, `.step`)**:
  - 4-step workflow indicator showing active state on `1. Product & Terms`.
- **Dynamic Facility Selector**:
  - Dropdown populated with active loan products, dynamically updating interest rate badge, permitted principal range, tenure limits, minimum income, and maximum LTI cap via client-side event binding.
- **Grouped Form Fields**:
  - 2-column responsive layout for applicant identity, loan amount, term, monthly income, existing obligations, loan purpose (with dynamic other-purpose reveal), employment classification, and preferred repayment day.
- **Live Reducing-Balance EMI Preview (`.emi-preview-box`)**:
  - Real-time client-side calculation showing Monthly EMI, Total Interest, and Gross Repayment Obligation as the user types.
- **Action Toolbar**:
  - "Save as Draft", "Review Application Summary →", and "Submit Application" buttons with full CSRF protection.

### D. Application Summary Confirmation (`src/templates/customer/apply_summary.html`)
- Step 2 confirmation card with full financial breakdown.
- Two-column specifications grid comparing loan specifications with the applicant's financial and employment profile.
- Live Loan-to-Income (LTI) risk indicator pill with color-coded safety thresholds (`<= 0.50x` safe, `0.51x - 0.70x` moderate, `> 0.70x` elevated).
- Edit back button and final submission CTA.

### E. Application Status & Operational Lifecycle (`src/templates/customer/status.html`)
- Top reference bar with application ID (`id="statusAppId"`), status badge (`id="statusValue"`), last updated timestamp (`id="statusDate"`), and requested amount (`id="statusAmount"`).
- Status-specific action banners:
  - `DOCUMENTS_REQUIRED`: Loan officer instructions, link to document vault, and inline resubmission form.
  - `REJECTED`: Formal decision notice with recorded credit policy rejection reason.
  - `DRAFT`: Saved draft notice with direct link to resume application.
- **Operational Lifecycle Progress Tracker**:
  - 5-stage visual tracker: `1. Submitted`, `2. Officer Review`, `3. Manager Review`, `4. Final Decision`, `5. Disbursement`.
- **Deterministic Rule Assessment Card**:
  - Income requirement, LTI ratio cap, and repayment tenure requirement with PASS/FAIL indicator badges.
- **Status Timeline (`id="timeline"`)**:
  - Connected vertical timeline tracking state transitions from draft to disbursement.
- **Application Audit Trail**:
  - Displays operational event history with strict actor privacy masking (staff personal names masked with role titles `Loan Officer` and `Loan Manager`).

### F. KYC Verification & Document Vault (`src/templates/customer/kyc.html`)
- Hero status card with verification state indicators.
- 3-card upload grid for Identity Proof, Address Proof, and Income Proof with clear size (<= 5MB) and format (.pdf, .png, .jpg, .jpeg) guidelines.
- Vault table listing uploaded files with secure download endpoints and delete buttons for unverified documents.

### G. Customer Profile (`src/templates/customer/profile.html`)
- Profile completeness card with animated progress bar.
- Grouped sections for account credentials, contact information, and employment details.
- Field-level validation error alerts.

### H. Notifications Log (`src/templates/notifications/index.html`)
- Metrics row with unread count (`id="unreadCount"`), total updates, and role pill.
- Status Updates History table (`id="notificationRows"`) with read/unread visual styling.
- Bulk "Mark Visible Updates as Read" action.

### I. Interactive Loan EMI Calculator (`src/templates/calculator.html`)
- Dual-control synchronized inputs (number input + range slider) for amount, interest rate, and term.
- Quick product preset buttons.
- Real-time results card with hero EMI readout, principal, interest, total payable, and proportional split bar.

---

## 4. Theme & Accessibility Audit

- **High-Contrast Theme Compatibility**:
  - All hardcoded white text on light surfaces was eliminated. Typography uses semantic CSS variables (`var(--text-primary)`, `var(--text-secondary)`, `var(--text-muted)`).
  - Backgrounds use `var(--bg-card)` and `var(--bg-surface)` to guarantee sharp contrast in both Light mode (`data-theme="light"`) and Dark mode (`data-theme="dark"`).
- **Tabular Numerics**:
  - Financial amounts and percentages employ `font-variant-numeric: tabular-nums` and `font-family: var(--font-mono)` for clean column alignment.
- **Responsive Layouts**:
  - All data tables are wrapped in `.table-responsive` containers to prevent horizontal viewport clipping on mobile viewports.
  - Form grids and metric bars wrap cleanly across tablet (768px) and mobile (480px) breakpoints.
