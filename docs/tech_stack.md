# LoanPulse — Tech Stack and Repository Plan

## Project
**LoanPulse: LoanMaster Loan Management**

LoanPulse is an individual Python full-stack student project for managing a simplified loan lifecycle: application, rule-based assessment, status tracking, manager decision visibility, disbursement tracking, and status notifications.

The product contains **no AI/ML features**. Any AI tools may only assist development.

## Architecture decision

### Selected option: Flask + Jinja2 + Vanilla JavaScript + SQLAlchemy + SQLite + pytest

```text
Browser
  |
  v
HTML / CSS / Vanilla JavaScript
  |
  v
Flask routes
  |
  v
Service / business logic
  |
  v
SQLAlchemy models
  |
  v
SQLite
```

SQLite is the default local database because this is an individual project with a short implementation window. SQLAlchemy keeps the persistence layer portable if PostgreSQL is required later.

## Why this option

- One application is easier to build, run, debug, and demonstrate alone.
- No separate frontend build system is required.
- Jinja templates are enough for the low-complexity MVP screens.
- Vanilla JavaScript can provide small interactive behaviours without adding frontend dependency overhead.
- Flask's test client works cleanly with pytest.
- The architecture can still separate routes, services, models, templates, and static assets.

## Alternative considered

### FastAPI + React + PostgreSQL

**Advantages:** stronger API/frontend separation, richer UI architecture, production-style REST boundary.

**Trade-offs:** two applications, more configuration, CORS/authentication coordination, more dependencies, and higher integration overhead for one student working within roughly two weeks.

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Backend | Flask |
| Templates | Jinja2 |
| Frontend | HTML, CSS, Vanilla JavaScript |
| ORM | Flask-SQLAlchemy / SQLAlchemy |
| Database | SQLite |
| Authentication | Flask-Login |
| Configuration | python-dotenv |
| Validation | Server-side Python validation; WTForms only if useful |
| Testing | pytest |
| Version control | Git / GitHub |

## MVP scope

The MVP flow is:

**Customer application data → predefined rule-based assessment → customer status screen → manager pending-decision report.**

Supporting/final-scope features include application review details, disbursement, notifications, validation, authorization, and reproducibility documentation.

## Architecture rules

1. Keep business rules out of route functions where practical.
2. Use service functions for assessment and workflow transitions.
3. Use SQLAlchemy models for relational data access.
4. Use Jinja for page rendering and small JavaScript enhancements only where needed.
5. Never add AI/ML scoring or external credit-scoring integrations.
6. Use synthetic data only.
7. Do not implement real-money transfers or real KYC/financial-institution verification.
8. Keep authentication/authorization simple and role-based.
9. Prefer one clear implementation over unnecessary abstractions.

## Repository plan

```text
LoanPulse/
├── data/
│   ├── fixtures/
│   └── *.csv
├── docs/
│   ├── 01_stakeholders.md
│   ├── 03_needs.md
│   ├── 04_requirements.md
│   ├── 05_traceability.md
│   ├── 06_user_stories.md
│   ├── 07_test_cases.md
│   ├── 09_data_design.md
│   ├── data_dictionary.md
│   ├── tech_stack.md
│   ├── wireframe.html
│   └── CLAUDE.md
├── src/
│   ├── app.py
│   ├── config.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── templates/
│   └── static/
├── tests/
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## Definition of Done

A feature is done when:

- Its relevant user story and BR are identified.
- Required data fields exist in the data model.
- The Flask route/service/model implementation is complete.
- The screen is usable through the browser.
- Happy-path and invalid-input behaviour are tested where applicable.
- Role restrictions are tested for protected functions.
- No real personal/financial data is used.
- The implementation does not introduce AI/ML.
- Relevant documentation is updated.
- `pytest` passes before code freeze.
- The project can be started using the documented README commands.
