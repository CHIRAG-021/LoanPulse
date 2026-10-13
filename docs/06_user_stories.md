# LoanPulse — User Stories and Acceptance Criteria

Project: **LoanPulse: LoanMaster Loan Management**

Each business requirement has one user story. Effort is estimated in build days and kept within the requested 1–3 day range. Acceptance criteria use Given/When/Then format and describe observable user behaviour rather than technical implementation.

| US ID | BR ID | User story | Effort |
|---|---|---|---:|
| US-01 | BR-01 | **As a customer, I want to save my required loan application information so that I can submit and review my application information without unnecessary repetition.** | 2 days |
| US-02 | BR-02 | **As a customer, I want to view the current status of my loan application so that I know what stage my application is in.** | 1 day |
| US-03 | BR-03 | **As a loan officer, I want the system to assess a loan application using predefined criteria so that I can review applications using consistent rules.** | 2 days |
| US-04 | BR-04 | **As a loan officer, I want to view the relevant applicant and loan information for an application so that I can review the application.** | 1 day |
| US-05 | BR-05 | **As a loan manager, I want to view applications requiring my decision so that I can identify pending loan decisions.** | 1 day |
| US-06 | BR-06 | **As a loan officer, I want to record the disbursement status of an approved loan so that the post-approval status remains clear.** | 1 day |
| US-07 | BR-07 | **As a customer, I want to receive important loan-status updates so that I can respond to changes or required actions.** | 2 days |
| US-08 | BR-08 | **As a customer, I want the system to identify missing or invalid application information so that I can correct my application before submission.** | 1 day |
| US-09 | BR-09 | **As a loan staff member, I want to access loan records according to my authorized role so that I only access information relevant to my responsibilities.** | 2 days |
| US-10 | BR-10 | **As a project maintainer, I want clear setup and execution instructions so that another person can reproduce and run the application.** | 1 day |
| US-11 | BR-11 | **As a loan manager, I want to configure and manage loan products so that the institution can offer tailored lending products with distinct financial terms.** | 2 days |
| US-12 | BR-12 | **As a customer or staff user, I want an interactive reducing-balance EMI calculator so that I can accurately estimate monthly installments and total repayment obligations.** | 1 day |
| US-13 | BR-13 | **As a loan officer or manager, I want the system to assess applications against a deterministic 6-rule policy engine so that underwriting decisions are transparent and consistent.** | 2 days |
| US-14 | BR-14 | **As an applicant or auditor, I want submitted application terms snapshotted at submission time so that subsequent product catalog modifications never alter historic contracts.** | 1 day |

## Acceptance Criteria

### US-01 — BR-01: Save loan application information

**AC-01**  
Given a customer has entered all required application information, when the customer saves the application, then the application is stored with an identifiable application reference.

**AC-02**  
Given a saved application exists, when the customer opens that application again, then the previously saved application information is displayed.

### US-02 — BR-02: View application status

**AC-01**  
Given a customer has an existing loan application, when the customer opens the application, then the current application status is displayed.

**AC-02**  
Given an application's status has changed, when the customer views the application after the change, then the updated status is displayed.

### US-03 — BR-03: Rule-based loan assessment

**AC-01**  
Given a loan application contains the information required by the configured assessment criteria, when a loan officer starts the assessment, then the system produces an assessment result based on those criteria.

**AC-02**  
Given two applications contain the same assessment inputs, when both applications are assessed, then both produce the same assessment result under the same configured rules.

### US-04 — BR-04: Review application information

**AC-01**  
Given a loan officer selects an application, when the officer opens the application, then the relevant applicant and loan information is displayed.

**AC-02**  
Given an application does not exist, when a loan officer attempts to open it, then the system indicates that the application cannot be found.

### US-05 — BR-05: View applications requiring manager decision

**AC-01**  
Given applications are awaiting manager decisions, when the loan manager opens the pending-decision view, then those applications are listed.

**AC-02**  
Given an application does not require a manager decision, when the loan manager opens the pending-decision view, then that application is not listed.

### US-06 — BR-06: Record disbursement status

**AC-01**  
Given a loan has been approved, when a loan officer records its disbursement, then the loan shows the recorded disbursement status.

**AC-02**  
Given a disbursement has been recorded, when the loan officer views the loan details, then the disbursement date is displayed.

### US-07 — BR-07: Receive loan-status updates

**AC-01**  
Given a customer's loan application status changes, when the status change is processed, then an update is available for the customer.

**AC-02**  
Given a relevant loan-status update exists, when the customer views their updates, then the update identifies the related loan application and its status change.

### US-08 — BR-08: Identify invalid application information

**AC-01**  
Given a required application field is missing, when the customer attempts to submit the application, then the system identifies the missing field.

**AC-02**  
Given an application field contains an invalid value, when the customer attempts to submit the application, then the system identifies the invalid field.

### US-09 — BR-09: Role-based access to loan records

**AC-01**  
Given a user has an authorized loan-management role, when the user accesses a permitted loan record, then the record is available to that user.

**AC-02**  
Given a user does not have permission for a protected loan record, when the user attempts to access it, then access is denied.

### US-10 — BR-10: Reproduce project setup

**AC-01**  
Given a person has access to the project repository and its documented prerequisites, when they follow the setup instructions, then the application can be started successfully.

**AC-02**  
Given the application has been set up using the documented process, when the documented test command is executed, then the project's defined tests can be run.

### US-11 — BR-11: Configurable loan products management

**AC-01**  
Given a loan manager accesses the loan products management console, when they view, create, or edit a product with valid parameters, then the product catalog is updated with validated boundaries.

**AC-02**  
Given a loan product exists, when a loan manager toggles its status, then the product switches between active and inactive states and inactive products cannot be selected for new loans.

### US-12 — BR-12: Reducing-balance EMI calculator

**AC-01**  
Given valid principal, annual interest rate, and tenure values, when the user calculates EMI, then the system returns the monthly installment computed using the standard reducing-balance formula rounded to 2 decimal places.

**AC-02**  
Given a zero percent annual interest rate, when the user calculates EMI, then the system computes $EMI = P / n$ without division by zero errors.

### US-13 — BR-13: Deterministic 6-rule policy assessment

**AC-01**  
Given an application is evaluated against product criteria, when underwriting assessment executes, then all 6 deterministic rules (Minimum Income, Loan Amount, Tenure, LTI Ratio, Affordability, Employment) are evaluated and a detailed PASS/FAIL breakdown is generated.

**AC-02**  
Given an application fails one or more criteria, when assessment completes, then the overall result is NOT_ELIGIBLE and human-readable failure explanations are recorded.

### US-14 — BR-14: Historic terms snapshotting

**AC-01**  
Given a customer submits an application linked to an active loan product, when the application is saved, then the applied interest rate and estimated monthly EMI are snapshotted onto the application record.

**AC-02**  
Given an application was previously submitted, when a loan manager modifies the product's interest rate in the catalog, then the existing application's applied rate and EMI remain unaltered.

## Effort Notes

- All stories are intentionally scoped to **1–3 build days**.
- No story prescribes a database, API, framework, programming language, or other implementation detail.
- BR-01 through BR-05 align most closely with the proposed MVP flow; BR-06 through BR-10 can be treated as final/stretch or supporting work according to the approved project scope.
- The acceptance criteria are intended to be directly convertible into pass/fail checks during testing.
