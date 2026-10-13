# LoanPulse — Business and Technical Requirements

Requirements are derived from the selected needs in `docs/03_needs.md`. The application is a Python full-stack system using rule-based and analytical logic only; it does not use AI/ML.

| BR ID | Need ID | Business requirement | TR ID | Technical requirement |
|---|---|---|---|---|
| BR-01 | N-01 | **System shall allow a customer to save required loan application information for later review.** | TR-01 | **The Python backend shall store required loan application fields in a relational database and retrieve them by application ID.** |
| BR-02 | N-02 | **System shall display the current status of a customer's loan application.** | TR-02 | **The backend shall store one current status value for each loan application and expose it through an authenticated API endpoint.** |
| BR-03 | N-03 | **System shall assess a loan application using predefined assessment criteria.** | TR-03 | **The Python backend shall calculate an assessment result from configured rule thresholds without using an AI/ML model.** |
| BR-04 | N-04 | **System shall provide loan officers with the relevant information for an application review.** | TR-04 | **The backend shall return the applicant and loan fields associated with a specified application ID through an authenticated API endpoint.** |
| BR-05 | N-05 | **System shall identify loan applications that require a manager decision.** | TR-05 | **The backend shall provide an API query that returns applications whose status is `PENDING_MANAGER_REVIEW`.** |
| BR-06 | N-06 | **System shall record the disbursement status of an approved loan.** | TR-06 | **The backend shall store a disbursement status and disbursement date for each approved loan.** |
| BR-07 | N-07 | **System shall provide customers and relevant loan staff with important loan-status updates.** | TR-07 | **The backend shall create a notification record when a loan application's status changes.** |
| BR-08 | Standing — Data quality | **System shall reject a loan application when a required field is missing or invalid.** | TR-08 | **The backend shall validate required fields and field formats before inserting a loan application record.** |
| BR-09 | Standing — Security/privacy | **System shall restrict loan records to authorized application roles.** | TR-09 | **The backend shall enforce role-based authorization on protected loan APIs.** |
| BR-10 | Standing — Documentation/reproducibility | **System shall provide documentation sufficient to reproduce the application setup and execution.** | TR-10 | **The project repository shall contain setup instructions, dependency definitions, database setup instructions, and test execution instructions.** |
| BR-11 | Phase 7 — Product Catalog | **System shall support configurable loan products managed by the Loan Manager.** | TR-11 | **The backend shall store loan product catalog records with financial limits and interest rates in `loan_products`, providing manager CRUD APIs and active toggle.** |
| BR-12 | Phase 7 — Financial Calculation | **System shall calculate monthly reducing-balance EMI and repayment figures.** | TR-12 | **The backend shall compute monthly EMI using Decimal reducing-balance arithmetic ($EMI = P \cdot r \cdot \frac{(1+r)^n}{(1+r)^n - 1}$), with zero-interest edge handling and JSON API.** |
| BR-13 | Phase 7 — Advanced Policy Rules | **System shall evaluate loan applications using a deterministic 6-rule policy engine.** | TR-13 | **The backend shall evaluate Minimum Income, Loan Amount, Tenure, Loan-to-Income, Affordability (<=50% income), and Employment, producing a transparent PASS/FAIL breakdown.** |
| BR-14 | Phase 7 — Historical Invariance | **System shall preserve historical financial terms of submitted loan applications.** | TR-14 | **The backend shall snapshot `applied_interest_rate` and `estimated_monthly_emi` onto the `loan_applications` record upon submission.** |
| BR-15 | Phase 8 — Lifecycle State Machine | **System shall enforce an end-to-end loan application state machine with role-authorized transitions.** | TR-15 | **The backend shall enforce allowed status transitions across `DRAFT`, `PENDING_REVIEW`, `UNDER_REVIEW`, `DOCUMENTS_REQUIRED`, `PENDING_MANAGER_REVIEW`, `APPROVED`, `REJECTED`, and `DISBURSED`, blocking unauthorized or out-of-order jumps.** |
| BR-16 | Phase 8 — Immutable Audit Logging | **System shall record an immutable audit trail for all significant application events.** | TR-16 | **The backend shall persist `ApplicationAuditLog` entries recording `application_id`, `actor_id`, `actor_name`, `actor_role`, `from_status`, `to_status`, `action`, `notes`, and timestamp.** |
| BR-17 | Phase 8 — Role Governance & Officer Workspace | **System shall restrict final lending approval exclusively to Loan Managers while providing Officers with review and triage tools.** | TR-17 | **The backend shall forbid Officer approval attempts (HTTP 403 / WorkflowError) while enabling queue search/filtering, review notes, document requests, and reasoned operational rejections.** |

## Requirement Notes

- Each BR has one primary pass/fail behaviour.
- Each TR has one primary implementation condition that can be checked independently.
- Requirements avoid subjective terms such as “fast” or “user-friendly”.
- Rule-based assessment is explicitly required; AI/ML is excluded.
- Security/privacy requirement uses **synthetic data only** for development and demonstration.
- No real financial transactions or external financial-institution verification are required by these requirements.

## Verification Considerations

The standing security/privacy requirement assumes that all project demonstration data is synthetic. Before implementation, the exact role names and assessment thresholds should be finalized as project decisions rather than assumed business facts.
