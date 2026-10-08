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

## Requirement Notes

- Each BR has one primary pass/fail behaviour.
- Each TR has one primary implementation condition that can be checked independently.
- Requirements avoid subjective terms such as “fast” or “user-friendly”.
- Rule-based assessment is explicitly required; AI/ML is excluded.
- Security/privacy requirement uses **synthetic data only** for development and demonstration.
- No real financial transactions or external financial-institution verification are required by these requirements.

## Verification Considerations

The standing security/privacy requirement assumes that all project demonstration data is synthetic. Before implementation, the exact role names and assessment thresholds should be finalized as project decisions rather than assumed business facts.
