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

### User Flow & Navigation (Production Authentication Architecture)

LoanPulse features an enterprise fintech operational entry and workspace flow:
1. **Landing / Home (`/`)**: Public product landing page showcasing capabilities, visual operational lifecycle pipeline, and interactive platform previews.
2. **Authentication Portal Selection (`/login`)**: Production sign-in selector with distinct gateways:
   - **User**: "For customers who want to apply for and track loans." -> Continues to `/login/user`.
   - **Administration**: "For authorized Loan Officers and Loan Managers." -> Continues to `/login/admin`.
3. **User Login (`/login/user`)**: Dedicated customer portal with email/password authentication, link to `/signup`, and strict rejection of staff credentials.
4. **Administration Login (`/login/admin`)**: Dedicated staff portal for Loan Officers and Loan Managers with staff email authentication, strict rejection of customer credentials, and omission of public signup.
5. **Customer Sign Up (`/signup`)**: Public customer registration flow. Server-side role assignment strictly enforces `role = CUSTOMER` (no privilege escalation possible). Validates name, email uniqueness, password complexity, and confirmation match.
6. **Cross-Portal Credential Handling**:
   - Staff credentials entered on `/login/user` are rejected with: *"These credentials belong to an Administration account. Please use Administration Login."*
   - Customer credentials entered on `/login/admin` are rejected with: *"These credentials belong to a User account. Please use User Login."*
7. **Dynamic Logo Navigation**:
   - When logged out: Clicking the LoanPulse brand logo navigates to `/` (public landing page).
   - When logged in: Clicking the LoanPulse brand logo navigates directly to the authenticated role's dashboard (`/customer/dashboard`, `/officer/queue`, or `/manager/queue`), preserving multi-tab session scoping.
8. **Role Dashboards & Workspaces (Phases 6 & 7)**:
   - **Customer Portal**:
     - **Dashboard (`/customer/dashboard`)**: Application history, real-time KPI metrics, active loan products carousel/links, dynamic KYC Status Card (`NOT_STARTED`, `PENDING`, `VERIFIED`, `REJECTED`), and profile completion tracking.
     - **Profile (`/customer/profile`)**: Manage personal details (phone, DOB, residential address, city, state, employment type, employer name, monthly income) with real-time percentage completion calculation.
     - **KYC & Documents (`/customer/kyc`)**: Upload and manage verification files (Identity Proof, Address Proof, Income Proof) with strict extension (`.pdf`, `.png`, `.jpg`, `.jpeg`) and size (<= 5 MB) validation, plus one-click KYC submission.
     - **Enhanced Application (`/applications/new`)**: Interactive loan product selector with dynamic parameter preview, live Vanilla JS EMI preview, server-side validation against product boundaries, and immutable rate/EMI snapshotting.
     - **Interactive EMI Calculator (`/calculator`, `/customer/calculator`)**: High-precision reducing-balance amortization calculator ($EMI = P \cdot r \cdot \frac{(1+r)^n}{(1+r)^n - 1}$), zero-interest edge handling, live slider adjustments, product quick presets, and visual principal vs interest breakdown.
     - **My Applications (`/customer/applications`)**: Comprehensive historical list of customer loan facilities.
   - **Loan Officer Workspace**:
     - **Loan Queue (`/officer/queue`)**: Application backlog, credit assessment execution, and manager escalation.
     - **Policy Assessment Review (`/officer/applications/<id>`)**: Comprehensive review screen presenting selected loan product terms, applicant KYC status, and deterministic 6-rule policy breakdown (Income, Amount, Tenure, LTI Ratio, Affordability with obligations + EMI, Employment).
     - **Loan Products Reference (`/officer/loan-products`)**: Read-only catalog of active credit facilities and limits.
     - **KYC Review Workspace (`/officer/kyc`, `/officer/kyc/<id>`)**: Dedicated queue to inspect customer verification files, evaluate credentials, and record decisions (`VERIFY` or `REJECT` with mandatory feedback reason).
     - **Disbursements (`/officer/disbursements`)**: Fund release tracking for approved loan facilities.
   - **Loan Manager Console**:
     - **Manager Queue (`/manager/queue`)**: Underwriting decision console with executive approval/rejection controls, 6-rule policy compliance breakdown, and applicant KYC standing.
     - **Loan Products Management (`/manager/loan-products`)**: Full product lifecycle management console to view, create (`/manager/loan-products/new`), edit (`/manager/loan-products/<id>/edit`), and toggle active/inactive status (`/manager/loan-products/<id>/toggle-status`).
   - **Activity Feed (`/notifications`)**: Real-time event log with unread badge counter and mark-as-read controls.

### Seeded Credentials (Evaluation & Testing)

For local evaluation and automated testing, default seeded user credentials in SQLite:
| Persona | Email | Password | Allowed Portal | Default Destination |
| :--- | :--- | :--- | :--- | :--- |
| **Customer** | `borrower01@example.test` | `demo123` | User (`/login/user`) | `/customer/dashboard` |
| **Loan Officer** | `officer01@example.test` | `demo123` | Administration (`/login/admin`) | `/officer/queue` |
| **Loan Manager** | `manager01@example.test` | `demo123` | Administration (`/login/admin`) | `/manager/queue` |

### Multi-Tab Concurrent Sessions

For multi-role operational evaluation in modern browsers:
- LoanPulse supports concurrent sessions using tab-scoped role routing (`demo_role` parameter).
- Each tab maintains its isolated authenticated role and session context without overwriting the authenticated user of other open tabs.
- Full server-side authentication, password checks, and RBAC authorization remain strictly enforced across all tabs.

## Automated Test Suite

LoanPulse features a comprehensive 155-test automated test suite across 17 test modules with a 100% pass rate:

```bash
pytest
```
Covers authentication, RBAC authorization, profile & KYC lifecycle, multi-tab sessions, configurable loan products, financial reducing-balance calculations, 6-rule policy engine, application workflows, disbursements, production error handling, WSGI entrypoints, and proxy integration.

## Production Deployment Guide (Phase 10)

### 1. Architecture Overview
In production, LoanPulse runs with:
- **WSGI Application Server**: Gunicorn (`wsgi.py`, configured via `gunicorn.conf.py`). Flask development server debug mode is strictly forbidden.
- **Relational Database**: PostgreSQL (production recommendation) or SQLite on a persistent volume.
- **Reverse Proxy**: TLS termination via Render, Cloudflare, Nginx, or AWS ALB with `ProxyFix` handling `X-Forwarded-Proto` and `X-Forwarded-For`.
- **Security Guardrails**:
  - `SECRET_KEY` fail-safe: Application startup aborts with a critical error if `SECRET_KEY` is missing or set to the local development placeholder.
  - Cookie security: `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"`, `SESSION_COOKIE_SECURE=True`.

### 2. Hosting Recommendations & Cost Analysis

| Platform | Recommended Tier | Estimated Cost | Strengths & Trade-offs |
| :--- | :--- | :--- | :--- |
| **Render (Recommended PaaS)** | Web: Starter ($7/mo)<br>DB: Starter ($7/mo) | **$14 / month** (or free for 30-day staging) | Turnkey Git deploys, zero server maintenance, automated HTTPS certificates, automated backups. Free tier available with 50s cold starts. |
| **Railway** | Hobby / Pro Usage | **$5 – $10 / month** | Fast builds, instant PostgreSQL provisioning, low latency. Usage-based billing. |
| **Docker VPS (DigitalOcean / Hetzner)** | 1–2 vCPU, 2–4 GB RAM | **$4 – $6 / month** | Lowest cost for 24/7 uptime; includes Postgres in Docker Compose. Requires OS patching and server administration. |

### 3. Environment Variables Configuration

Copy `.env.production.example` and set production environment variables in your deployment platform:

```bash
cp .env.production.example .env.production
```

| Variable | Description | Production Example |
| :--- | :--- | :--- |
| `FLASK_APP` | Application entrypoint | `wsgi.py` |
| `FLASK_ENV` | Application environment | `production` |
| `SECRET_KEY` | 32+ byte cryptographic key (**Required**) | `$(python3 -c 'import secrets; print(secrets.token_hex(32))')` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/loanpulse_prod` |
| `SESSION_COOKIE_SECURE` | HTTPS cookie flag | `True` |
| `BEHIND_PROXY` | Enables `ProxyFix` reverse proxy headers | `True` |
| `PORT` | Listening network port | `8000` |
| `WEB_CONCURRENCY` | Gunicorn worker processes | `2` |
| `PYTHON_THREADS` | Gunicorn threads per worker | `2` |

### 4. Database Setup & Migrations

For a new production PostgreSQL database:
```bash
# 1. Initialize schema and load seed products and test personas:
flask --app wsgi:app init-db --seed

# 2. Or initialize schema without demo records:
flask --app wsgi:app init-db --no-seed

# 3. For schema upgrades with Flask-Migrate / Alembic:
flask --app wsgi:app db upgrade
```

### 5. Production Startup Commands

**Gunicorn WSGI Server:**
```bash
gunicorn --config gunicorn.conf.py wsgi:app
```

**Docker / Multi-Container Deployment:**
```bash
# Build and run web service and PostgreSQL container:
docker compose up -d

# Check service logs:
docker compose logs -f web
```

**Health Check Endpoint:**
```bash
curl -f http://localhost:8000/health
# {"app": "LoanPulse", "status": "ok"}
```

### 6. Production Troubleshooting

1. **`CRITICAL SECURITY CONFIGURATION ERROR: Production mode requires a secure, non-default SECRET_KEY`**:
   - Cause: `SECRET_KEY` is unset or equals `"change-this-for-local-development"`.
   - Resolution: Set `SECRET_KEY` in environment variables using `python3 -c "import secrets; print(secrets.token_hex(32))"`.
2. **`sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgres`**:
   - Cause: Provider provided `postgres://` connection URI instead of `postgresql://`.
   - Resolution: LoanPulse automatically normalizes `postgres://` to `postgresql://` in `src/config.py`. Ensure `DATABASE_URL` is well-formed.
3. **Session expires immediately or redirects fail under HTTPS**:
   - Cause: Reverse proxy is not forwarding `X-Forwarded-Proto: https` or `BEHIND_PROXY` is not enabled.
   - Resolution: Set `BEHIND_PROXY=True` in environment variables so `ProxyFix` middleware accurately interprets client protocol.
4. **Static CSS not applying or 404 on assets**:
   - Cause: Reverse proxy not routing `/static` or wrong permissions.
   - Resolution: Ensure `/app/src/static` is readable by the web service user, or configure Nginx/CDN to serve `/static` directly.

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
