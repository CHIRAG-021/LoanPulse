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

## `loan_applications`

| Column | Type | Required | Key | Allowed/example values | Description |
|---|---|---|---|---|---|
| application_id | VARCHAR(20) | Yes | PK | `APP-0001` | Public application reference |
| customer_id | INTEGER | Yes | FK | `1` | References `users.user_id` |
| applicant_name | VARCHAR(100) | Yes | | `Test Borrower 01` | Synthetic applicant name |
| monthly_income | DECIMAL(12,2) | Yes | | `60000.00` | Synthetic monthly income |
| requested_amount | DECIMAL(12,2) | Yes | | `200000.00` | Synthetic requested loan amount |
| term_months | INTEGER | Yes | | `12`, `24`, `36`, `60` | Requested term in months |
| status | VARCHAR(30) | Yes | | `DRAFT`, `PENDING_REVIEW`, `PENDING_MANAGER_REVIEW`, `APPROVED`, `REJECTED` | Current lifecycle status |
| approved_amount | DECIMAL(12,2) | Conditional | | `200000.00` or NULL | Approved loan amount; populated for approved loans |
| disbursement_status | VARCHAR(30) | Yes | | `NOT_APPLICABLE`, `NOT_DISBURSED`, `DISBURSED` | Current disbursement state |
| disbursement_date | DATE | Conditional | | `2026-10-10` or NULL | Date the approved loan was disbursed |
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

## Core relationships

- `loan_applications.customer_id` → `users.user_id`
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
