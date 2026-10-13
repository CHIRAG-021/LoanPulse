# LoanPulse — Data Dictionary

Project: **LoanPulse: LoanMaster Loan Management**

All values in this dictionary are synthetic examples. No real personal data may be used.

## `users`

| Column | Type | Required | Key | Allowed/example values | Description |
|---|---|---|---|---|---|
| user_id | INTEGER | Yes | PK | 1, 2, 3 | Unique user identifier |
| full_name | VARCHAR(100) | Yes | | `Test Borrower 01` | Synthetic display name |
| email | VARCHAR(150) | Yes | UNIQUE | `borrower01@example.test` | Synthetic login email |
| role | VARCHAR(30) | Yes | | `CUSTOMER`, `LOAN_OFFICER`, `LOAN_MANAGER` | Application role |
| is_active | BOOLEAN | Yes | | `true`, `false` | Whether the account can access the application |
| phone_number | VARCHAR(20) | No | | `+91 9876543210` | Customer contact telephone number |
| date_of_birth | DATE | No | | `1992-05-15` | Customer birth date |
| address | VARCHAR(255) | No | | `42 Tech Boulevard` | Residential street address |
| city | VARCHAR(100) | No | | `Bengaluru` | Residential city |
| state | VARCHAR(100) | No | | `Karnataka` | Residential state / province |
| employment_type | VARCHAR(50) | No | | `SALARIED`, `SELF_EMPLOYED`, `BUSINESS_OWNER`, `OTHER` | Employment category |
| employer_name | VARCHAR(150) | No | | `Antigravity Systems` | Employer / business organization |
| monthly_income | DECIMAL(12,2) | No | | `85000.00` | Stored customer monthly gross income |
| kyc_status | VARCHAR(30) | Yes | | `NOT_STARTED`, `PENDING`, `VERIFIED`, `REJECTED` | Current KYC state (default `NOT_STARTED`) |
| kyc_rejection_reason | VARCHAR(255) | No | | `Document illegible` | Officer rejection explanation |
| kyc_submitted_at | DATE | No | | `2026-10-08` | Date KYC submitted |
| kyc_reviewed_at | DATE | No | | `2026-10-08` | Date KYC decision recorded |

## `loan_applications`

| Column | Type | Required | Key | Allowed/example values | Description |
|---|---|---|---|---|---|
| application_id | VARCHAR(20) | Yes | PK | `APP-0001` | Public application reference |
| customer_id | INTEGER | Yes | FK | `1` | References `users.user_id` |
| applicant_name | VARCHAR(100) | Yes | | `Test Borrower 01` | Synthetic applicant name |
| monthly_income | DECIMAL(12,2) | Yes | | `60000.00` | Synthetic monthly income |
| requested_amount | DECIMAL(12,2) | Yes | | `200000.00` | Synthetic requested loan amount |
| term_months | INTEGER | Yes | | `12`, `24`, `36`, `60` | Requested term in months |
| status | VARCHAR(30) | Yes | | `DRAFT`, `PENDING_REVIEW`, `UNDER_REVIEW`, `DOCUMENTS_REQUIRED`, `PENDING_MANAGER_REVIEW`, `APPROVED`, `REJECTED`, `DISBURSED` | Current lifecycle status |
| approved_amount | DECIMAL(12,2) | Conditional | | `200000.00` or NULL | Approved loan amount; populated for approved loans |
| disbursement_status | VARCHAR(30) | Yes | | `NOT_APPLICABLE`, `NOT_DISBURSED`, `DISBURSED` | Current disbursement state |
| disbursement_date | DATE | Conditional | | `2026-10-10` or NULL | Date the approved loan was disbursed |
| loan_purpose | VARCHAR(50) | Yes | | `PERSONAL`, `EDUCATION`, `MEDICAL`, `HOME_IMPROVEMENT`, `BUSINESS`, `OTHER` | Controlled purpose category |
| loan_purpose_other | VARCHAR(255) | No | | `Retail inventory purchase` | Free-text if purpose is `OTHER` |
| employment_type | VARCHAR(50) | No | | `SALARIED` | Employment classification |
| employer_name | VARCHAR(150) | No | | `Global Tech Corp` | Employer or business name |
| existing_obligations | DECIMAL(12,2) | Yes | | `12000.00` | Existing monthly debt/rent obligations (default 0.0) |
| preferred_repayment_date | INTEGER | No | | `5`, `10`, `15` | Preferred monthly repayment day (1-31) |
| product_id | INTEGER | No | FK | `1`, `2` | References `loan_products.product_id` (Phase 7) |
| applied_interest_rate | DECIMAL(5,2) | No | | `11.50` | Immutable annual interest rate snapshot at application time (Phase 7) |
| estimated_monthly_emi | DECIMAL(12,2) | No | | `9350.25` | Immutable reducing-balance monthly EMI snapshot (Phase 7) |
| review_notes | TEXT | No | | `Credit verified...` | Officer review notes or document request instructions (Phase 8) |
| rejection_reason | VARCHAR(255) | No | | `High debt-to-income...` | Documented reason when application is rejected (Phase 8) |
| created_at | DATE | Yes | | `2026-10-08` | Synthetic creation date |
| updated_at | DATE | Yes | | `2026-10-08` | Synthetic last-update date |

## `assessment_rules`

| Column | Type | Required | Key | Allowed/example values | Description |
|---|---|---|---|---|---|
| rule_id | INTEGER | Yes | PK | `1` | Rule identifier |
| rule_name | VARCHAR(100) | Yes | | `Basic Eligibility Rule` | Rule description |
| min_monthly_income | DECIMAL(12,2) | Yes | | `30000.00` | Minimum income threshold |
| max_loan_to_income_ratio | DECIMAL(6,2) | Yes | | `0.50` | Maximum requested amount / annual income |
| min_term_months | INTEGER | Yes | | `12` | Minimum term |
| max_term_months | INTEGER | Yes | | `60` | Maximum term |
| result_if_pass | VARCHAR(30) | Yes | | `ELIGIBLE` | Result if all configured conditions pass |
| active | BOOLEAN | Yes | | `true`, `false` | Whether the rule is active |

## `assessments`

| Column | Type | Required | Key | Allowed/example values | Description |
|---|---|---|---|---|---|
| assessment_id | INTEGER | Yes | PK | `1` | Assessment identifier |
| application_id | VARCHAR(20) | Yes | FK | `APP-0003` | Application being assessed |
| rule_id | INTEGER | Yes | FK | `1` | Rule configuration used |
| assessment_result | VARCHAR(30) | Yes | | `ELIGIBLE`, `NOT_ELIGIBLE` | Deterministic rule result |
| calculated_ratio | DECIMAL(8,2) | Yes | | `0.28` | Requested amount divided by annual income |
| rules_breakdown_json | TEXT | No | | `[{"rule_key": "income", "passed": true...}]` | Serialized JSON array of 6-rule breakdown (Phase 7) |
| failure_reasons_json | TEXT | No | | `["Affordability cap exceeded..."]` | Serialized JSON array of failure explanations (Phase 7) |
| estimated_emi | DECIMAL(12,2) | No | | `8884.88` | Calculated reducing-balance monthly EMI (Phase 7) |
| affordability_ratio | DECIMAL(6,2) | No | | `0.42` | Debt burden ratio: (obligations + EMI) / income (Phase 7) |
| assessed_at | DATE | Yes | | `2026-10-08` | Synthetic assessment date |

## `notifications`

| Column | Type | Required | Key | Allowed/example values | Description |
|---|---|---|---|---|---|
| notification_id | INTEGER | Yes | PK | `1` | Notification identifier |
| application_id | VARCHAR(20) | Yes | FK | `APP-0016` | Related application |
| recipient_user_id | INTEGER | Yes | FK | `1` | User receiving the update |
| old_status | VARCHAR(30) | No | | `PENDING_MANAGER_REVIEW` or NULL | Previous status |
| new_status | VARCHAR(30) | Yes | | `APPROVED` | New status |
| message | VARCHAR(255) | Yes | | `Application APP-0016 status changed to APPROVED.` | Synthetic update message |
| created_at | DATE | Yes | | `2026-10-08` | Synthetic notification date |
| is_read | BOOLEAN | Yes | | `true`, `false` | Whether the update was viewed |

## `role_permissions`

| Column | Type | Required | Key | Allowed/example values | Description |
|---|---|---|---|---|---|
| role | VARCHAR(30) | Yes | PK | `CUSTOMER`, `LOAN_OFFICER`, `LOAN_MANAGER` | Role name |
| resource | VARCHAR(50) | Yes | PK | `CUSTOMER_APPLICATION`, `STAFF_APPLICATION`, `MANAGER_QUEUE` | Protected resource |
| can_view | BOOLEAN | Yes | | `true`, `false` | Whether the role can view that resource |

## `customer_documents`

| Column | Type | Required | Key | Allowed/example values | Description |
|---|---|---|---|---|---|
| document_id | INTEGER | Yes | PK | `1` | Unique document identifier |
| customer_id | INTEGER | Yes | FK | `1` | References `users.user_id` |
| document_type | VARCHAR(50) | Yes | | `IDENTITY_PROOF`, `ADDRESS_PROOF`, `INCOME_PROOF` | Category of document |
| original_filename | VARCHAR(255) | Yes | | `passport.pdf`, `utility_bill.png` | User-provided file name |
| stored_filename | VARCHAR(255) | Yes | | `cust_1_identity_proof_a1b2c3d4.pdf` | Sanitized unique local filename |
| file_path | VARCHAR(255) | Yes | | `uploads/documents/cust_1_...` | Relative or absolute path on disk |
| file_size | INTEGER | Yes | | `204850` | File size in bytes (max 5MB) |
| mime_type | VARCHAR(100) | Yes | | `application/pdf`, `image/png`, `image/jpeg` | File MIME format |
| verification_status | VARCHAR(30) | Yes | | `PENDING`, `VERIFIED`, `REJECTED` | Document verification state |
| rejection_reason | VARCHAR(255) | No | | `Document expired` | Specific feedback if rejected |
| uploaded_at | DATE | Yes | | `2026-10-08` | Upload date |
| reviewed_at | DATE | No | | `2026-10-08` | Officer review date |

## `loan_products`

| Column | Type | Required | Key | Allowed/example values | Description |
|---|---|---|---|---|---|
| product_id | INTEGER | Yes | PK | `1` | Unique loan product identifier |
| product_name | VARCHAR(100) | Yes | | `Personal Loan` | Display name of the credit facility |
| product_code | VARCHAR(50) | Yes | UNIQUE | `PERSONAL`, `EDUCATION`, `MEDICAL`, `BUSINESS`, `HOME_IMPROVEMENT` | Unique alphanumeric product code |
| description | TEXT | No | | `Unsecured credit facility...` | Facility description |
| min_amount | DECIMAL(12,2) | Yes | | `10000.00` | Minimum allowable loan amount |
| max_amount | DECIMAL(12,2) | Yes | | `500000.00` | Maximum allowable loan amount |
| min_term_months | INTEGER | Yes | | `12` | Minimum permitted tenure |
| max_term_months | INTEGER | Yes | | `60` | Maximum permitted tenure |
| annual_interest_rate | DECIMAL(5,2) | Yes | | `11.50` | Base interest rate per annum (percentage) |
| min_monthly_income | DECIMAL(12,2) | Yes | | `25000.00` | Minimum monthly income requirement |
| max_loan_to_income_ratio | DECIMAL(6,2) | Yes | | `0.50` | Maximum allowable loan-to-annual-income ratio |
| active | BOOLEAN | Yes | | `true`, `false` | Active status (only active products can be selected) |
| created_at | DATE | Yes | | `2026-10-08` | Creation date |
| updated_at | DATE | Yes | | `2026-10-08` | Last modification date |

## `application_audit_logs`

| Column | Type | Required | Key | Allowed/example values | Description |
|---|---|---|---|---|---|
| log_id | INTEGER | Yes | PK | `1` | Unique audit event identifier |
| application_id | VARCHAR(20) | Yes | FK | `APP-0001` | Associated loan application ID |
| actor_id | INTEGER | No | FK | `2` | User ID of actor who triggered event |
| actor_name | VARCHAR(100) | Yes | | `Test Officer 01` | Name of actor at event time |
| actor_role | VARCHAR(30) | Yes | | `CUSTOMER`, `LOAN_OFFICER`, `LOAN_MANAGER`, `SYSTEM` | Role of actor at event time |
| from_status | VARCHAR(30) | No | | `PENDING_REVIEW` | Application status before event |
| to_status | VARCHAR(30) | Yes | | `UNDER_REVIEW` | Application status after event |
| action | VARCHAR(50) | Yes | | `SUBMITTED`, `ASSESSED`, `NOTE_ADDED`, `DOCUMENTS_REQUESTED`, `FORWARDED_TO_MANAGER`, `MANAGER_APPROVED` | Event action type |
| notes | TEXT | No | | `Applicant verified...` | Notes, reasons, or remarks associated with event |
| created_at | DATETIME | Yes | | `2026-10-09 11:30:00` | UTC timestamp of event |

## Core relationships

- `loan_applications.customer_id` → `users.user_id`
- `loan_applications.product_id` → `loan_products.product_id`
- `application_audit_logs.application_id` → `loan_applications.application_id`
- `application_audit_logs.actor_id` → `users.user_id`
- `customer_documents.customer_id` → `users.user_id`
- `assessments.application_id` → `loan_applications.application_id`
- `assessments.rule_id` → `assessment_rules.rule_id`
- `notifications.application_id` → `loan_applications.application_id`
- `notifications.recipient_user_id` → `users.user_id`

## Data constraints

1. `application_id` must be unique.
2. `email` must be unique within the synthetic user dataset.
3. Required application fields must not be null in valid records.
4. `monthly_income` must be greater than zero for a valid submitted application.
5. `requested_amount` must be greater than zero for a valid submitted application.
6. `term_months` must be within the configured permitted range for a valid submitted application.
7. `status` must use one of the defined lifecycle values.
8. Approved applications must have `approved_amount`, `disbursement_status`, and `disbursement_date` in the clean demonstration dataset.
9. Non-approved applications must not have `approved_amount` or `disbursement_date`; their `disbursement_status` is `NOT_APPLICABLE`.
10. Assessment results must be produced only from the configured rule inputs.
11. Demonstration records must use synthetic names and contact details.
12. No Aadhaar, PAN, bank-account, card, real customer, or other real-person identifiers may appear in the dataset.
