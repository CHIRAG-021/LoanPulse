# Changelog

All notable changes to the LoanPulse project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---


## [Manager Workspace In-Page Approval Modal] - 2026-10-22

### Changed
- **Replaced Native Browser `confirm()` with In-Page Accessible Modal**:
  - Eliminated browser-native popups (`confirm("Are you sure?...")`) on the Loan Manager review page in favor of a modern, accessible in-page confirmation dialog matching the LoanPulse design system.
  - Implemented centered modal dialog over a darkened backdrop (`.modal-backdrop`, `.modal-dialog`) in `src/templates/manager/review.html` with complete WAI-ARIA dialog semantics (`role="dialog"`, `aria-modal="true"`, `aria-labelledby="approveModalTitle"`, `aria-describedby="approveModalDesc"`).
  - Included an approval shield checkmark icon badge, exact title **"Approve This Loan?"**, descriptive advisory copy (**"Are you sure you want to approve this loan application? Please review the application details before confirming."**), and an application summary card displaying Applicant Name, Requested Principal, Loan Facility, and Deterministic Rule Assessment badge.
  - Provided a secondary "Cancel" button and a primary green "Approve Loan" action with button spinner and active loading text ("Approving...").
  - Robust focus management: moves initial focus to the Cancel button for safety, traps keyboard Tab cycles inside open dialog, dismisses on Escape key, restores focus to the trigger button upon dismissal, and locks body scrolling while active (`overflow: hidden`).
  - Seamless form integration: transfers executive decision notes into the underlying approval form prior to submission and enforces double-submission locking.
  - Fully responsive on mobile viewports (375px) with edge padding and touch-friendly controls.

---

## [Customer Support Chatbot Widget] - 2026-10-22

### Added
- **Google Gemini AI Integration (`gemini-2.5-flash`)**:
  - Activated Google Gemini generateContent API integration on the Flask server side with verified stable model `gemini-2.5-flash`.
  - Secure server-side header authentication via `x-goog-api-key`, strictly excluding keys from URLs, query strings, logs, and templates.
  - FAQ-First architecture: High-confidence FAQ matches (score >= 2) are answered immediately by the local verified engine, conserving quota and minimizing latency.
  - Strict grounding system instruction: Prohibits invented interest rates or credit limits, rejects fixed calendar-day SLAs, strictly details 6-rule underwriting checks and KYC requirements (PDF, PNG, JPG/JPEG max 5 MB).
  - Clarification & Escalation handling: Prompts for targeted clarifications on ambiguous queries; escalates disputes and manual overrides to `support@loanpulse.local`.
  - Data minimization & prompt injection defense: Authenticated customer records are queried locally and never passed to external AI; untrusted prompt injection attempts are safely refused.
  - Graceful fallback: Network timeouts, invalid keys, or HTTP 429 quota exhaustion fall back to honest support executive messaging without false claims.
- **Natural 2–3 Second Typing & Loading State**:
  - Sequential 3-dot animated assistant message bubble (`.lp-chatbot-typing`, `.lp-typing-dot:nth-of-type(1..3)` with staggered animation delays `-0.32s`, `-0.16s`, `0s`).
  - Dynamic positioning: Appended directly to `#lpChatbotMessages` after the user's latest message to preserve accurate conversational chronology.
  - Concurrency synchronization: Uses `Promise.all([fetchPromise, delayPromise])` to ensure answers wait for the minimum natural typing duration (~2.2s, bounded between 2.0s and 2.7s) without adding extra latency to slow responses (> 3s).
  - User interaction safeguards: Disables input field (`input.disabled = true`), marks Send button as busy (`.is-busy`, `aria-busy="true"`), and blocks rapid clicks on suggestion chips via CSS `pointer-events: none` and JS state checks.
  - Accessibility & Motion: Added `role="status"`, `aria-live="polite"`, and screen-reader status text (`.sr-only`), with `@media (prefers-reduced-motion: reduce)` overrides disabling pulsing animations and easing scroll behavior.
  - Error and rate-limit recovery: Automatically clears typing indicator and renders helpful guidance upon network failure or HTTP 429 rate limit.
- **Customer Support Robot Chat Widget (`src/templates/components/chatbot.html`)**:
  - Floating action button fixed to bottom-right with friendly fintech robot SVG icon (`#lpChatbotTrigger`).
  - Motion-safe entrance animation (`@keyframes lpBotEntrance`) respecting `prefers-reduced-motion`.
  - Unobtrusive welcome teaser tooltip ("Need help with your loan?") with dismissal memory in session storage.
  - Accessible conversation panel (`#lpChatbotPanel`) featuring minimize and close controls, status pulse indicator, and responsive mobile full-screen overlay.
  - Starter clickable quick question chips for KYC requirements, processing timelines, 6-rule eligibility, EMI calculation, status tracking, and disbursement.
  - Safe message streaming with typed loading indicator dots and character count indicator (max 500 characters).
  - Conditionally rendered exclusively on customer-facing pages and public landing/calculator views; strictly excluded from staff workspaces (`/officer/*`, `/manager/*`).
- **Chatbot Client Module (`src/static/js/chatbot.js`)**:
  - Safe text node rendering (`document.createTextNode()`) for XSS prevention.
  - CSRF token extraction and `X-CSRFToken` request header attachment.
  - Multi-tab window session propagation via `X-Window-ID` header.
  - Keyboard navigation (Esc to close open panel, Enter to submit query).
  - Dynamic loading state toggle and error recovery with fallback chips.
- **Chatbot Backend Service (`src/services/chatbot_service.py`)**:
  - Deterministic verified knowledge base covering 10+ core operational domains (KYC documents, 6-rule underwriting, lifecycle states, EMI calculations, product limits, registration, and status tracking).
  - Strict processing-time policy: details the 5 authentic stages while rejecting false SLA/calendar-day guarantees.
  - Safe personalized query answering for authenticated customers (`current_user.role == 'CUSTOMER'`), returning real-time application and KYC statuses without trusting IDs in messages.
  - Configurable support desk fallback (`LOANPULSE_SUPPORT_CONTACT`) defaulting to `support@loanpulse.local`.
  - Optional server-side AI integration support (OpenAI / Gemini) via environment variables with zero code changes or new runtime dependencies required.
- **Chatbot Route Endpoints (`src/routes/chatbot.py`)**:
  - `GET /chatbot/config`: Returns assistant metadata, active mode (`faq` or `ai`), and starter suggested questions.
  - `POST /chatbot/message`: Validates request payload, enforces 500-character limits, applies sliding-window session rate limiting (25 requests/minute), and returns grounded assistant responses.
- **Automated Test Suite (`tests/test_chatbot.py`)**:
  - 14 automated tests verifying widget rendering, staff workspace exclusion, knowledge accuracy, careful processing time response, personalized customer queries, input validation, rate limiting, and SQL injection safety.
- **Documentation (`docs/CUSTOMER_SUPPORT_CHATBOT.md`)**:
  - Comprehensive architectural guide, verified knowledge catalog, AI configuration guide, and security design details.

---

## [Phase 6] - 2026-10-21

### Added
- **Loan Manager Workspace & Executive Dashboard Modernization (Stripe & Linear Inspired)**:
  - **Manager Decision Queue (`src/templates/manager/queue.html`)**:
    - High-density executive queue with purple role accents (`.badge.purple`).
    - 4-card metric display tracking `Pending Manager Decisions` (`id="pendingCount"`), `Approved Portfolio`, `Rejected Applications`, and `Disbursed Portfolio`.
    - Modern queue table (`id="pending-applications-table"`, `id="managerRows"`) displaying applicant initials avatars, monospaced application IDs, tabular amounts, term durations, assessment result badges (`ELIGIBLE` / `NOT_ELIGIBLE`), lifecycle status pills, and inline review/approve/reject controls.
    - Standardized empty state card (`id="empty-state-message" class="placeholder"`) displaying `All Decisions Complete`.
  - **Executive Decision Review (`src/templates/manager/review.html`)**:
    - Modern breadcrumb navigation and header: `Executive Decision Review: {{ app.application_id }}`.
    - Metadata ribbon (`.manager-meta-bar`) summarizing application ID, applicant avatar, loan facility, KYC status badge, and disbursement status.
    - Two-column card grid detailing `Applicant Information` and `Loan Request` with verified monthly income, requested amounts, tenures, applicable interest rates, estimated EMIs, and existing debt obligations.
    - Deterministic 6-Rule Assessment card detailing Pass/Fail checks for `Income Requirement`, `Loan-to-Income Ratio`, `Term Requirement`, Loan Amount, Affordability, and Employment.
    - Immutable audit trail history card displaying all operational lifecycle events.
    - Executive decision card with rationale input (`#managerDecisionNotes`), confirmation safeguards, anti-double-submission prevention, and distinct `Approve Application` and `Reject Application` controls.
  - **Loan Products Policy Management (`src/templates/manager/products.html`)**:
    - Executive policy catalog header with refresh action and "Create New Product" CTA.
    - 3-card metric display: `Total Loan Products`, `Active Products`, and `Inactive Products`.
    - Facilities table displaying product codes, principal ranges, tenures, annual interest rates, income thresholds, max LTI ratios, active status badges, and inline Edit/Toggle controls.
  - **Loan Product Creation & Editing Form (`src/templates/manager/product_form.html`)**:
    - Polished card with `.executive-accent` border styling for creating and editing lending products.
    - Grouped fields for Product Identity (name, uppercase monospace code, description) and Facility Boundaries (min/max amounts, tenures, interest rate, min income, max LTI ratio).
    - Validation error banner and active product toggle checkbox.
- **Manager Styling Tokens & Components (`src/static/css/style.css`)**:
  - Added `.manager-avatar-icon`, `.manager-meta-bar`, `.manager-decision-card`, `.executive-accent`, and `.manager-action-group`.
- **Documentation**:
  - Created `docs/PHASE_6_MANAGER_WORKSPACE.md`.

---

## [Phase 5] - 2026-10-21

### Added
- **Loan Officer Workspace & Underwriting Modernization (Stripe & Linear Inspired)**:
  - **Officer Queue Workspace (`src/templates/officer/queue.html`)**:
    - High-visibility 4-card metric display tracking `Total Queue Volume`, `Pending Review`, `Pending Manager Review`, and `Approved / Disbursed`.
    - Live search input (`Search by Application ID or Applicant...`) with query persistence.
    - Button-based status filter pills (`All`, `Pending Review`, `Under Review`, `Docs Required`, `Manager Review`, `Approved`, `Disbursed`, `Rejected`) ensuring strict test compatibility without `<select>` elements.
    - Product filtering pills and responsive queue table featuring customer initials avatars, monospace application IDs, tabular amounts, and lifecycle status pills.
  - **Application Underwriting Review (`src/templates/officer/review.html`)**:
    - High-density metadata ribbon (`.officer-review-meta-bar`) summarizing applicant details, contact info, requested finances, and product terms.
    - Deterministic 6-Rule Assessment card with Pass/Fail visual chips for `Income Requirement`, `Loan-to-Income Ratio`, and `Term Requirement`, backed by a one-click "Run Rule Assessment" trigger.
    - Customer verification document chip list (`.kyc-doc-chip`) with file metadata and download inspection controls.
    - Underwriting notes log and timestamped rule assessment history.
    - Immutable visual audit trail log.
    - Consequential action cards for document requests (`.warning-action`) and application rejections (`.danger-action`) with validated reason fields.
  - **Disbursement Workspace (`src/templates/officer/disbursements.html`)**:
    - Portfolio metrics ribbon for `Approved Applications`, `Disbursed Loans`, and `Awaiting Disbursement`.
    - Reactive fund release execution card with application selector, live approved amount calculation, disbursement date input, and CSRF protection.
    - Approved loans tracking table (`id="disbRows"`) with inline "Disburse Now" execution forms and "Completed" badges.
  - **KYC Verification Queue (`src/templates/officer/kyc_queue.html`)**:
    - Compliance metrics tracking `Total Customers`, `Pending Review`, `Verified Customers`, and `Rejected KYCs`.
    - Verification queue table with borrower avatar, profile completion progress bar, document count chip, and KYC status tags.
  - **Individual KYC Review Workspace (`src/templates/officer/kyc_review.html`)**:
    - Comprehensive borrower profile card with profile completion meter and previous rejection reason alert banner.
    - Verification documents inspection table with download actions.
    - Officer decision form with validated rejection reason and verification approval actions.
  - **Loan Product Directory Reference (`src/templates/officer/products.html`)**:
    - Read-only catalog grid detailing active borrowing facilities, amount limits, tenures, annual interest rates, and minimum monthly income thresholds.
- **Officer Styling Tokens & Components (`src/static/css/style.css`)**:
  - Added `.officer-avatar-icon`, `.officer-review-meta-bar`, `.officer-meta-group`, `.officer-meta-item`, `.officer-meta-divider`, `.kyc-doc-chip`, `.officer-action-card`, `.warning-action`, and `.danger-action`.
- **Documentation**:
  - Created `docs/PHASE_5_OFFICER_WORKSPACE.md`.

---

## [Phase 4] - 2026-10-21

### Added
- **Customer Experience & Dashboard Modernization (Stripe & Linear Inspired)**:
  - **Customer Dashboard (`src/templates/customer/dashboard.html`)**:
    - Modern welcome header with user avatar, borrower greeting, and prominent "Apply for a Loan" CTA.
    - Dynamic KYC Verification hero card (`.kyc-banner`) with state-driven border-left accents, verification badge, profile completion progress meter, and direct action triggers.
    - 4-card KPI metric display backed by live database records (`total_count`, `pending_count`, `approved_count`, `disbursed_count`).
    - Available Loan Products catalog grid (`.loan-product-grid`, `.loan-product-card`) featuring interest rate pills, min/max borrowing limits, tenure parameters, and instant "Apply Now" buttons.
    - Structured applications history and recent notification transition tables with empty state handling.
  - **Loan Applications History (`src/templates/customer/applications.html`)**:
    - Clean tabular application records with monospaced IDs, tabular-numeric amounts, and standardized empty state fallback.
  - **Loan Application Form (`src/templates/customer/apply.html`)**:
    - Linear-style 4-step progress stepper (`.steps`, `.step`).
    - Dynamic loan product facility selector with live reactive parameter updates.
    - Live reducing-balance EMI preview box (`.emi-preview-box`) calculating real-time monthly EMI, total interest, and total payable as users type.
    - Two-column responsive form layout with inline validation feedback and multi-action controls ("Save as Draft", "Review Summary", "Submit Application").
  - **Application Summary Confirmation (`src/templates/customer/apply_summary.html`)**:
    - Step 2 final review summary card with loan specifications and applicant financial profile.
    - Color-coded Loan-to-Income (LTI) ratio indicator pill with risk thresholds.
    - Edit and final submit actions.
  - **Application Status & Operational Lifecycle (`src/templates/customer/status.html`)**:
    - Top reference bar with required IDs (`statusAppId`, `statusValue`, `statusDate`, `statusAmount`).
    - 5-stage visual operational lifecycle tracker (`1. Submitted`, `2. Officer Review`, `3. Manager Review`, `4. Final Decision`, `5. Disbursement`).
    - Deterministic rule assessment card with PASS/FAIL check badges.
    - Connected application status timeline (`id="timeline"`).
    - Immutable application audit trail with staff role masking for applicant privacy.
    - Status-dependent action banners (`DOCUMENTS_REQUIRED` with resubmit form, `REJECTED` with reason, `DRAFT` with resume CTA).
  - **KYC Verification & Document Vault (`src/templates/customer/kyc.html`)**:
    - Verification hero banner, 3-card upload grid with format/size guidelines, and encrypted documents vault table with download and delete controls.
  - **Customer Profile Workspace (`src/templates/customer/profile.html`)**:
    - Profile completeness meter, grouped identity/contact/employment forms, and validation alerts.
  - **Notifications & Updates (`src/templates/notifications/index.html`)**:
    - Unread KPI counter (`id="unreadCount"`), status updates history table (`id="notificationRows"`), and bulk mark-read action.
  - **Loan EMI Calculator (`src/templates/calculator.html`)**:
    - Synchronized dual numeric/slider controls, product presets, and proportional principal/interest split visualization.
- **Customer Styling Tokens & Components (`src/static/css/style.css`)**:
  - Added `.customer-hero-head`, `.kyc-banner`, `.loan-product-grid`, `.loan-product-card`, `.emi-preview-box`, `.emi-preview-grid`, `.document-upload-grid`, `.document-upload-card`, `.rule-check-grid`, `.rule-check-item`, and `.profile-completion-card`.
- **Documentation**:
  - Authored `docs/PHASE_4_CUSTOMER_EXPERIENCE.md`.

---

## [Phase 3] - 2026-10-21

### Added
- **Standardized System Alerts (`.alert`)**:
  - Accessible container (`.alerts-container`, `role="region"`, `aria-label="System notifications"`) in `src/templates/base.html`.
  - Semantic SVG category icons for `success`, `danger`/`error`, `warning`, and `info`.
  - Alert message content wrapper (`.alert-content`).
  - Native dismiss button (`.alert-close`, `aria-label="Dismiss alert"`) with smooth transition and focus ring.
  - 4px semantic accent left borders in both light and dark themes.
- **Unified Empty States (`.empty-state`)**:
  - Reusable empty state components with `.empty-state-icon`, `.empty-state-title`, `.empty-state-description`, and `.empty-state-actions` in `src/static/css/style.css`.
  - High-contrast light mode overrides preventing white-on-white text washout on light cards.
  - Maintained complete backward compatibility with existing `.placeholder` and `.table-empty` classes.
- **Expanded Status Badge Dictionary (`.status`)**:
  - Geometric dot indicator badge styling for all application lifecycle states:
    - `.status-SUBMITTED`, `.status-DOCUMENT_VERIFICATION` (Blue / Info).
    - `.status-UNDER_REVIEW`, `.status-IN_REVIEW`, `.status-PENDING` (Amber / Warning).
    - `.status-MANAGER_APPROVED`, `.status-VERIFIED` (Emerald / Success).
    - `.status-OFFICER_REJECTED`, `.status-MANAGER_REJECTED` (Rose / Danger).
    - `.status-NOT_APPLICABLE` (Slate / Muted).
  - High-contrast Light Mode overrides with strict WCAG AA color tokens.
- **Modal & Overlay Component Primitives**:
  - `.modal-backdrop`, `.modal-dialog`, `.modal-header`, `.modal-title`, `.modal-body`, and `.modal-footer` primitives added for subsequent phases.
- **Responsive Footer Layout**:
  - Enhanced `src/templates/base.html` and `src/static/css/style.css` with `.app-footer-inner`, brand lockup, deterministic operations descriptor, and copyright notice.
- **Documentation**:
  - Created `docs/PHASE_3_SHARED_COMPONENTS.md` detailing component inventory, contrast verification, and scope boundaries.

### Fixed
- Ensured table empty states and placeholder cards have high contrast across both light and dark themes.

---

## [Phase 2] - 2026-10-20

### Added
- **Public Landing Page Redesign (`src/templates/landing.html`)**:
  - Stripe/Linear inspired hero section with gradient typography, trust badging, and role quick-access tabs.
  - Live interactive client-side loan calculator preview widget.
  - Verified capabilities grid highlighting deterministic rule-based evaluation, automated KYC, and multi-tier RBAC.
  - Enterprise security architecture showcase displaying zero-telemetry, window-scoped session isolation, and audit trail guarantees.
  - Responsive conversion banner and clean CTA footer.
- **Landing Page Styling (`src/static/css/style.css`)**:
  - Scoped landing layout classes, subtle radial glow effects, and interactive demo tabs.
  - Strict WCAG AA contrast compliance in both light and dark modes.

---

## [Phase 1] - 2026-10-19

### Added
- **Design Token System (`src/static/css/style.css`)**:
  - 4px baseline spacing scale (`--space-0` through `--space-20`).
  - Comprehensive typographic scale and line heights (`--font-sans`, `--font-mono`, `--text-xs` to `--text-4xl`).
  - Multi-layered elevation shadows (`--shadow-xs` to `--shadow-xl`, `--shadow-card`, `--shadow-glow`).
  - Accessible focus tokens (`--focus-ring`, `--focus-ring-shadow`) and `prefers-reduced-motion` animation suppression.
- **Standardized Component Foundation**:
  - Modern button primitives (`.btn.primary`, `.btn.secondary`, `.btn.outline`, `.btn.ghost`, `.btn.danger`, `.btn.success`, `.btn-sm`, `.btn-lg`, `.is-loading`, `.is-disabled`).
  - Form control layouts (`.form-group`, `.form-row`, `.form-col`, `.form-label`, `.required-star`).
  - Accessible custom checkboxes, radios, and file inputs.
  - Card primitives (`.card`, `.card-header`, `.card-title`, `.card-subtitle`, `.card-body`, `.card-footer`).
  - Status badge foundation (`.status-DRAFT`, `.status-PENDING_REVIEW`, `.status-DOCUMENTS_REQUIRED`, `.status-PENDING_MANAGER_REVIEW`, `.status-APPROVED`, `.status-REJECTED`, `.status-DISBURSED`, `.status-NOT_DISBURSED`).
- **Documentation**:
  - Created Phase 1 Design Foundation report.
