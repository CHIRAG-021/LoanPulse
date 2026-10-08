# LoanPulse — Traceability Matrix

Project: **LoanPulse: LoanMaster Loan Management**

This matrix traces the selected pain areas through needs to business requirements. It is based on the current versions of the project documents. The three standing requirements in `docs/04_requirements.md` are reviewed separately because they are project-wide requirements rather than direct responses to a single pain area.

## Traceability Matrix

| PA ID | Pain | Stakeholder | Need ID | Need | BR ID | Business requirement |
|---|---|---|---|---|---|---|
| PA-01 | Loan application information can be difficult to keep organized across the application process. | Customer / Borrower | N-01 | Customers need to keep their loan application information organized and accessible so that they can provide and review the required information without unnecessary repetition. | BR-01 | System shall allow a customer to save required loan application information for later review. |
| PA-02 | Customers may have limited visibility into the current status of their loan application. | Customer / Borrower | N-02 | Customers need to know the current status of their loan application so that they can understand what stage their application is in. | BR-02 | System shall display the current status of a customer's loan application. |
| PA-03 | Reviewing applications manually can make it harder for loan staff to apply assessment rules consistently. | Loan Officer | N-03 | Loan officers need to assess loan applications using clear and consistent criteria so that applications can be reviewed fairly and systematically. | BR-03 | System shall assess a loan application using predefined assessment criteria. |
| PA-04 | Loan officers may spend time locating application information before making a review or approval recommendation. | Loan Officer | N-04 | Loan officers need to find the relevant applicant and loan information efficiently so that they can review applications without unnecessary effort. | BR-04 | System shall provide loan officers with the relevant information for an application review. |
| PA-05 | Loan managers may lack a single view of applications requiring decisions and their current status. | Loan Manager | N-05 | Loan managers need to understand which applications require decisions and their current status so that they can manage pending loan decisions effectively. | BR-05 | System shall identify loan applications that require a manager decision. |
| PA-06 | Disbursement information can become difficult to track separately from the original loan application. | Loan Officer / Finance Staff | N-06 | Loan officers and finance staff need to know whether approved loans have been disbursed and when so that the post-approval status remains clear. | BR-06 | System shall record the disbursement status of an approved loan. |
| PA-08 | Important loan-status and repayment updates may not reach the relevant user at the right time. | Customer / Loan Staff | N-07 | Customers and relevant loan staff need to receive important loan-status and repayment updates in a timely manner so that they can respond to changes or required actions. | BR-07 | System shall provide customers and relevant loan staff with important loan-status updates. |

## Traceability Gaps

### Pain with no need

**None among the selected pain areas.** PA-01, PA-02, PA-03, PA-04, PA-05, PA-06, and PA-08 each trace to exactly one need.

**Suggested fix:** No change required.

### Need with no requirement

**None.** N-01 through N-07 each trace to one business requirement: BR-01 through BR-07 respectively.

**Suggested fix:** No change required.

### Requirement with no trace back to a pain

The following business requirements do not trace directly to a selected pain:

| BR ID | Requirement | Why it does not directly trace to a pain | Suggested fix |
|---|---|---|---|
| BR-08 | System shall reject a loan application when a required field is missing or invalid. | Standing data-quality requirement. | Keep as a standing requirement; optionally document it as a cross-cutting safeguard rather than forcing a pain link. |
| BR-09 | System shall restrict loan records to authorized application roles. | Standing security/privacy requirement. | Keep as a standing requirement; do not invent a pain solely to create traceability. |
| BR-10 | System shall provide documentation sufficient to reproduce the application setup and execution. | Standing documentation/reproducibility requirement. | Keep as a standing requirement; it supports project quality rather than a specific user pain. |

## Summary

- **7 selected pains → 7 needs → 7 business requirements** have complete direct traceability.
- **0 pains** are missing a need.
- **0 needs** are missing a business requirement.
- **3 standing business requirements** do not trace directly to a pain by design.
- No files were changed other than creating this traceability document.

## Decision Note

The standing requirements are intentionally retained without artificial pain mappings. If the project documentation later requires every requirement to trace to a pain, the recommended approach is to add an explicit project-wide requirement category or traceability type rather than inventing unsupported user problems. This is a suggestion only and does not change the source requirements.
