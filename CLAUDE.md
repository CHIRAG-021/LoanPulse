# CLAUDE.md — LoanPulse Development Context

## Project identity

**Project:** LoanPulse: LoanMaster Loan Management

**Type:** Individual student Python full-stack project.

**Deadline:** 25 October 2026.

**Code freeze:** 24 October 2026.

**Development constraint:** Keep the implementation simple enough for one student to build, test, explain, and demonstrate within the available time.

## Product purpose

LoanPulse manages a simplified loan lifecycle:

1. Customer provides loan application information.
2. The system stores and validates the application.
3. The system assesses the application using predefined rules.
4. The customer can view the current application status.
5. Loan staff can review relevant application information.
6. A manager can see applications requiring a decision.
7. Approved-loan disbursement status can be recorded in final scope.
8. Status changes can create notification records in final scope.

## Explicit exclusions

Do **not** add:

- AI/ML credit scoring
- AI/ML recommendation systems
- real credit-bureau integrations
- real banking integrations
- real-money transfers
- payment gateway processing
- real KYC/document verification
- production lending decisions
- fraud-detection systems
- unnecessary microservices
- complex event streaming
- mobile-app scope unless explicitly requested

AI tools may assist development, but AI is not a product feature.

## Source-of-truth documentation

Before changing behaviour, consult the relevant documents:

- `docs/01_stakeholders.md` — stakeholders
- `docs/03_needs.md` — needs
- `docs/04_requirements.md` — BR/TR requirements
- `docs/05_traceability.md` — PA → Need → BR mapping
- `docs/06_user_stories.md` — user stories and acceptance criteria
- `docs/07_test_cases.md` — expected tests
- `docs/09_data_design.md` — tables and data design
- `docs/data_dictionary.md` — field definitions
- `docs/tech_stack.md` — architecture
- `docs/wireframe.html` — page/screen intent

Do not invent business requirements when a requirement is already documented.

## Stack

- Python 3.11+
- Flask
- Jinja2
- HTML/CSS/Vanilla JavaScript
- Flask-SQLAlchemy / SQLAlchemy
- SQLite
- Flask-Login
- python-dotenv
- pytest

## Folder structure

```text
LoanPulse/
├── data/
│   ├── fixtures/
│   └── *.csv
├── docs/
├── src/
│   ├── app.py
│   ├── config.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── templates/
│   └── static/
├── tests/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
└── CLAUDE.md
```

## Coding conventions

### Python

- Use `snake_case` for variables, functions, files, and module names.
- Use `PascalCase` for classes.
- Use clear type hints where they improve readability.
- Keep route functions thin.
- Put assessment/workflow rules in `services/`.
- Keep database models in `models/`.
- Avoid unnecessary design patterns and abstractions.

### Database

- Use singular, descriptive model class names and the documented table names.
- Primary keys and foreign keys must follow `docs/09_data_design.md`.
- Do not silently rename documented columns.
- Use synthetic data only.

### HTML/JavaScript

- Use semantic HTML where practical.
- Keep JavaScript small and page-focused.
- Use clear IDs/classes such as `application-form`, `status-table`, and `assessment-result`.
- Do not introduce a frontend framework.

### IDs

Preserve project IDs exactly:

- Pain areas: `PA-xx`
- Needs: `N-xx`
- Business requirements: `BR-xx`
- Technical requirements: `TR-xx`
- User stories: `US-xx`
- Test cases: `TC-xx`

## Requirements priority

The MVP functional flow is:

```text
Customer application
       ↓
Rule-based assessment
       ↓
Customer status
       ↓
Manager pending-decision report
```

Primary MVP business requirements:

- BR-01 — save required application information
- BR-02 — display current application status
- BR-03 — assess using predefined criteria
- BR-05 — identify applications requiring manager decision

Supporting/final-scope requirements:

- BR-04 — application review information
- BR-06 — disbursement status
- BR-07 — status updates/notifications
- BR-08 — validation
- BR-09 — role-based authorization
- BR-10 — reproducibility/documentation

## Assessment rules

Assessment must remain deterministic and rule-based.

Current documented rule structure includes:

- minimum monthly income
- maximum loan-to-income ratio
- minimum term
- maximum term
- active/inactive rule

Do not replace this with an ML model or external credit score.

## Testing

Run all tests from the repository root:

```bash
pytest
```

Before considering a feature done:

1. Add or update a test.
2. Run the relevant test.
3. Run the full suite.
4. Confirm expected browser flow manually for UI changes.

## Definition of Done

A change is done when:

- It maps to a documented US/BR where applicable.
- Required database fields exist.
- Backend behaviour is implemented.
- UI behaviour matches the wireframe intent.
- Validation and authorization are handled where required.
- Relevant happy-path and invalid-input tests pass.
- Existing tests still pass.
- Synthetic data only is used.
- No AI/ML product functionality is introduced.
- Documentation is updated when behaviour/schema changes.
- The feature can be explained simply during a project demonstration.

## Working style

Prefer the smallest implementation that satisfies the documented requirement.

Do not over-engineer the project. Avoid adding libraries unless they solve a documented need and save meaningful implementation time.

When a requirement conflicts with the existing data design, stop and identify the mismatch rather than silently inventing a schema.

## Current known schema issue

BR-06 requires disbursement status and date, but the current `loan_applications` design does not yet contain those fields. Resolve this deliberately before implementing BR-06. A simple extension of `loan_applications` is acceptable if chosen explicitly.

Similarly, authentication credentials are not currently represented in the data design. Do not store plaintext passwords.
