# LoanPulse — Test Cases

Project: **LoanPulse: LoanMaster Loan Management**

The test cases trace each user story to its business requirement. The four proposed MVP stories (US-01, US-02, US-03, US-05) each have at least one happy-path and one invalid-input test. Standing tests cover data quality, synthetic-only data, and clean-machine reproducibility.

## Test Cases

| TC ID | US ID | BR ID | Scenario | Test data | Steps | Expected result (exact) | Type |
|---|---|---|---|---|---|---|---|
| TC-01 | US-01 | BR-01 | Save a complete loan application | Name=Test Borrower; income=60000; amount=200000; term=24 months | 1. Open application form. 2. Enter all required values. 3. Select Save. | A new application reference is displayed and the entered application values are stored. | happy path |
| TC-02 | US-01 | BR-01 | Submit application with a required field missing | Income is blank; other required fields are valid | 1. Open application form. 2. Enter all required values except income. 3. Select Submit. | The application is not submitted and the income field is identified as required. | invalid input |
| TC-03 | US-02 | BR-02 | View an existing application's status | Application APP-001 with status `PENDING_REVIEW` | 1. Sign in as the application owner. 2. Open APP-001. | `PENDING_REVIEW` is displayed as the current application status. | happy path |
| TC-04 | US-02 | BR-02 | Request status for a nonexistent application | Application ID `APP-9999` that does not exist | 1. Open the application-status view. 2. Request APP-9999. | The system displays an application-not-found message and does not display a loan status. | invalid input |
| TC-05 | US-03 | BR-03 | Assess an application that satisfies configured rules | Income=60000; requested amount=200000; configured rule permits this combination | 1. Open the eligible application as a loan officer. 2. Start assessment. | The system produces the configured positive assessment result for the supplied inputs. | happy path |
| TC-06 | US-03 | BR-03 | Assess an application with invalid assessment input | Income=-5000; requested amount=200000 | 1. Open the application as a loan officer. 2. Start assessment. | The system rejects the invalid income value and does not produce a loan assessment result from that value. | invalid input |
| TC-07 | US-03 | BR-03 | Same inputs produce the same rule result | Two applications with identical configured assessment inputs | 1. Assess application A. 2. Assess application B using the same inputs. | Both applications receive the same assessment result. | edge |
| TC-08 | US-04 | BR-04 | View relevant information for an existing application | APP-001 with applicant and loan fields populated | 1. Sign in as a loan officer. 2. Open APP-001. | The applicant details and loan details stored for APP-001 are displayed. | happy path |
| TC-09 | US-04 | BR-04 | Open an application that does not exist | Application ID `APP-9999` | 1. Sign in as a loan officer. 2. Open APP-9999. | The system displays an application-not-found message and no applicant or loan details. | invalid input |
| TC-10 | US-05 | BR-05 | View applications requiring manager decision | APP-002 status=`PENDING_MANAGER_REVIEW`; APP-003 status=`APPROVED` | 1. Sign in as a loan manager. 2. Open the pending-decision view. | APP-002 is listed and APP-003 is not listed. | happy path |
| TC-11 | US-05 | BR-05 | Pending-decision view has no matching applications | No application has status `PENDING_MANAGER_REVIEW` | 1. Sign in as a loan manager. 2. Open the pending-decision view. | The view displays an empty-state message and no application rows. | invalid input |
| TC-12 | US-06 | BR-06 | Record disbursement for an approved loan | APP-0015 status=`APPROVED`; approved amount populated; disbursement date=2026-10-10 | 1. Sign in as a loan officer. 2. Open APP-0015. 3. Record the disbursement. | APP-0015 shows `DISBURSED` and a stored disbursement date. | happy path |
| TC-13 | US-06 | BR-06 | Attempt disbursement for an approved loan with no disbursement record | APP-EDGE-NO-DISBURSEMENT status=`APPROVED`; disbursement status=`NOT_DISBURSED` | 1. Sign in as a loan officer. 2. Open the edge-case application. 3. Attempt to complete disbursement. | The system accepts the approved application for disbursement and records `DISBURSED` with a disbursement date. | edge |
| TC-14 | US-07 | BR-07 | Create a status update after a status change | APP-006 changes from `PENDING_REVIEW` to `APPROVED` | 1. Change APP-006 status to `APPROVED`. 2. Process the status change. | An update record for APP-006 is created and identifies the new status as `APPROVED`. | happy path |
| TC-15 | US-07 | BR-07 | Do not create a status update when no status change occurs | APP-007 remains `PENDING_REVIEW` | 1. Process APP-007 without changing its status. 2. Open the customer's updates. | No new status-change update is created for APP-007. | edge |
| TC-16 | US-08 | BR-08 | Reject an application with missing required information | Required field `loan_amount` is blank | 1. Enter the remaining required values. 2. Submit the application. | Submission is rejected and `loan_amount` is identified as missing. | invalid input |
| TC-17 | US-08 | BR-08 | Reject an application with an invalid field format | Loan amount=`abc` | 1. Enter `abc` in the loan amount field. 2. Submit the application. | Submission is rejected and the loan amount field is identified as invalid. | invalid input |
| TC-18 | US-09 | BR-09 | Authorized role accesses a permitted loan record | User role=`Loan Officer`; APP-001 is permitted for the role | 1. Sign in as the loan officer. 2. Open APP-001. | APP-001 is displayed to the authorized loan officer. | happy path |
| TC-19 | US-09 | BR-09 | Unauthorized role accesses a protected loan record | User role=`Customer`; protected staff record APP-001 | 1. Sign in as the customer. 2. Request the protected staff record. | Access is denied and the protected record data is not displayed. | invalid input |
| TC-20 | US-10 | BR-10 | Reproduce the application from documented setup steps | Clean Python environment; repository; documented dependencies | 1. Clone/copy the repository. 2. Follow README prerequisites and setup steps. 3. Run the documented start command. | The application starts using the commands documented in README without requiring undocumented setup steps. | happy path |
| TC-21 | US-10 | BR-10 | Run documented tests after documented setup | Clean Python environment; repository; documented test command | 1. Complete documented setup. 2. Run the test command from README. | The documented test command executes the project's defined test suite. | happy path |

## Standing Tests

| TC ID | US ID | BR ID | Scenario | Test data | Steps | Expected result (exact) | Type |
|---|---|---|---|---|---|---|---|
| TC-22 | ST-01 | BR-08 | Validate required fields and basic field formats | Missing name; income=`abc`; loan amount=-1000 | 1. Submit the application with the supplied values. | The submission is rejected and each invalid or missing field is identified. | invalid input |
| TC-23 | ST-02 | Project-wide | Confirm demonstration data contains no real personal data | Synthetic names, emails, phone numbers, addresses and financial values | 1. Inspect seed/demo data. 2. Search repository files for real personal identifiers. | All stored demonstration records use synthetic values and no real person's personal data is present. | edge |
| TC-24 | ST-03 | BR-10 | Run project from README on a clean machine | Fresh Python environment; repository; README | 1. Create a clean Python environment. 2. Follow README from prerequisites through database setup and application start. 3. Run the documented tests. | The application starts and the documented test command runs successfully without undocumented commands or local-machine-specific files. | happy path |

## Pytest Automation Notes

The following tests can be automated with `pytest` and should be prioritized:

- **TC-01, TC-02:** application validation and persistence tests.
- **TC-05, TC-06, TC-07:** rule-assessment unit tests; these are especially suitable for deterministic pytest cases.
- **TC-09, TC-11, TC-13:** API/service validation tests.
- **TC-14, TC-15:** notification/status-change service tests.
- **TC-16, TC-17:** field-validation tests.
- **TC-18, TC-19:** authorization tests.
- **TC-22:** data-quality validation test.

UI-only checks such as whether a particular status is visibly rendered may be kept as manual tests unless the project adds a browser automation framework.

## MVP Coverage Check

The proposed four functional MVP stories are **US-01, US-02, US-03, and US-05**. Each has both required test types:

| MVP story | Happy-path test | Invalid-input test |
|---|---|---|
| US-01 | TC-01 | TC-02 |
| US-02 | TC-03 | TC-04 |
| US-03 | TC-05 | TC-06 |
| US-05 | TC-10 | TC-11 |

These four stories therefore cover the intended MVP flow: **application data → rule-based assessment → customer status screen → manager decision report**.

## Test Data Note

All names, application IDs, contact details, income values, loan amounts, and other personal or financial values in these test cases are synthetic examples only. No real customer data should be used for development or demonstration.
