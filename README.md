# LoanPulse: LoanMaster Loan Management

Individual Python full-stack student project.

## Scope

LoanPulse manages a simplified loan lifecycle from application through rule-based assessment, status tracking, manager decision visibility, disbursement tracking, and notifications.

The product uses **no AI/ML features** and all development/demo data must be synthetic.

## Stack

- Python
- Flask
- Jinja2
- HTML/CSS/Vanilla JavaScript
- SQLAlchemy
- SQLite
- pytest

See `docs/tech_stack.md` for architecture decisions.

## Repository

- `src/` — application code
- `tests/` — automated tests
- `data/` — synthetic datasets and fixtures
- `docs/` — requirements, design, wireframe, and project guidance

## Existing dataset generator

The current synthetic CSV dataset can be regenerated with:

```bash
python3 src/generate_data.py
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Initialize and Seed Database

```bash
flask --app src.app:create_app init-db
```

### Start the Application

```bash
flask --app src.app:create_app run
```

Then open `http://127.0.0.1:5000` in your web browser.

## Tests

```bash
pytest
```

## Data policy

Use synthetic demonstration data only. Do not add real customer, banking, government-ID, contact, or financial records.

## Documentation

Start with:

1. `docs/03_needs.md`
2. `docs/04_requirements.md`
3. `docs/05_traceability.md`
4. `docs/06_user_stories.md`
5. `docs/07_test_cases.md`
6. `docs/09_data_design.md`
7. `docs/tech_stack.md`
8. `docs/wireframe.html`
9. `CLAUDE.md`
