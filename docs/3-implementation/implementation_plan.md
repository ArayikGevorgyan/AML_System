# Implementation Plan

## Overview

The AML Transaction Monitoring System was implemented as a full-stack monorepo with a Python/FastAPI backend and a React frontend. Implementation followed a layered architecture with strict separation between routers, services, models, and schemas.

---

## Backend Implementation

### Entry Point — `main.py`
The FastAPI application is initialised in `main.py`. All routers are registered under the `/api/v1` prefix. A background scheduler (APScheduler) runs a daily seed job at 08:00 to generate realistic transaction data. The SQLite database is created on startup via `Base.metadata.create_all()` — no migration tool (Alembic) is used.

### Layer Structure

| Layer | Location | Responsibility |
|-------|----------|---------------|
| Routers | `routers/` | HTTP request handling, input validation, response serialisation |
| Services | `services/` | Business logic, rule evaluation, scoring, screening |
| Models | `models/` | SQLAlchemy ORM table definitions |
| Schemas | `schemas/` | Pydantic v2 request/response models |
| Core | `core/` | JWT security, RBAC dependencies, enums, exceptions |
| ML | `ml/` | Anomaly detection and risk prediction models |
| Analysis | `analysis/` | Aggregation and analytics queries |
| Scripts | `scripts/` | CLI tools and data import utilities |

### Key Services

#### Rules Engine (`services/rules_engine.py`)
Implements nine detection rules: `large_transaction`, `structuring`, `frequency`, `velocity`, `high_risk_country`, `rapid_movement`, `round_amount`, `pep_transaction`, `micro_transaction`. Each rule returns a `RuleMatch` dataclass containing the rule name, severity, score contribution, and matched evidence. Rules are evaluated on every transaction submission.

#### Risk Scoring (`services/risk_scoring_service.py`)
Computes a composite customer risk score from three additive components:
- **Profile score** — up to 60 points (PEP status, nationality, sanctions flag)
- **Transaction behaviour** — up to 30 points (velocity, flagged ratio, international activity)
- **Alert history** — up to 25 points (open alerts, critical alerts, escalated cases)

Score bands: LOW (0–24), MEDIUM (25–49), HIGH (50–74), CRITICAL (75–100).

#### Sanctions Screener (`services/sanctions_screener.py`)
Multi-stage pipeline:
1. Normalise input (lowercase, Unicode → ASCII, remove honorifics)
2. SQL ILIKE substring pre-filter for candidate retrieval
3. Composite score per alias: Token Recall × 0.60 + Jaro-Winkler × 0.25 + Jaccard × 0.15
4. Exact token subset match → forced score of 100

Uses the `jellyfish` library for Jaro-Winkler distance computation.

#### Authentication (`services/auth_service.py`, `core/security.py`)
JWT tokens with an 8-hour lifetime (`ACCESS_TOKEN_EXPIRE_MINUTES = 480`). Passwords hashed with bcrypt via passlib. Three roles enforced via `require_roles()` and `require_supervisor_or_admin()` dependency functions.

#### Anomaly Detection (`ml/anomaly_detector.py`)
Isolation Forest (scikit-learn) with `n_estimators=100` and `contamination=0.05`. One model is trained per customer on demand, managed by `CustomerAnomalyDetectorRegistry`. Features: log(amount), hour of day, day of week, is_international, is_round_amount, transaction type, channel.

#### ML Risk Predictor (`ml/risk_model.py`)
`GradientBoostingClassifier` (scikit-learn) wrapped in a `StandardScaler` Pipeline. Trained on 14 features per customer to predict SAR probability in the next 90 days. Feature engineering centralised in `ml/feature_engineering.py` across 6 groups: amount statistics, velocity windows, temporal patterns, geographic risk, alert history, and customer profile.

#### Audit Service (`services/audit_service.py`)
Records every sensitive create/update/delete operation as a plain `AuditLog` row containing: user, action type, entity type, entity ID, IP address, timestamp, and before/after JSON snapshots.

---

## Frontend Implementation

### Stack
Create React App (React 18), React Router v6, Axios with JWT interceptor, Recharts for charts, custom CSS with CSS variables for dark/light theming. No component library (Tailwind, MUI, etc.) is used.

### Routing
All authenticated routes are wrapped in a layout guard that checks the JWT from `localStorage`. Unauthenticated users are redirected to `/home` (Landing page).

### State Management
- `AuthContext` — user session, login/logout, JWT storage
- `ThemeContext` — dark/light mode preference persisted to `localStorage`
- Per-page local state via `useState` + `useEffect` + Axios (no React Query or Redux)

### Pages

| Page | Description |
|------|-------------|
| Landing | Public entry point with login and register navigation |
| Login | Two-column layout: branding panel (left) + form (right) |
| Register | Email verification flow with 6-digit code input |
| Dashboard | KPI cards + 5 Recharts charts loaded in a single API call |
| Customers | Filterable table with risk badge and PEP/sanctions indicators |
| Transactions | Transaction list with flagged status and risk score display |
| Alerts | Alert management with severity classification and status workflow |
| Cases | Investigation cases with notes thread and SAR filing |
| Sanctions | Fuzzy search with Type/Program/Country dropdowns (86 programs, 196 countries) |
| Rules | Admin rule configuration with threshold editing |
| Blacklist | Custom blacklist/whitelist management |
| Audit | Full audit log with before/after JSON diff |
| Profile | User profile management |
| Sessions | Active session management |
| GeoHeatmap | Geographic transaction heatmap visualisation |

---

## Database

SQLite with WAL mode and foreign keys enabled. Schema created via `Base.metadata.create_all()` on application startup. No Alembic or migration scripts — the schema is recreated by re-running `seed_data.py`.

### Core Tables

| Table | Description |
|-------|-------------|
| `users` | System users with hashed passwords and roles |
| `customers` | Customer KYC profiles with risk band and PEP flag |
| `accounts` | Bank accounts linked to customers |
| `transactions` | Financial transactions with risk score and flagged status |
| `rules` | Configurable AML detection rules |
| `alerts` | Auto-generated alerts from rule and sanctions matches |
| `cases` | Investigation cases with SAR filing support |
| `sanctions_entries` | OFAC SDN and UN Consolidated List entries |
| `sanctions_aliases` | Per-alias rows for fuzzy name matching |
| `blacklist` | Custom entity blacklist/whitelist |
| `audit_logs` | Full audit trail with before/after JSON |
| `user_sessions` | Active JWT session tracking |

---

## CLI Scripts

| Script | Purpose |
|--------|---------|
| `seed_data.py` | Populates demo users, rules, customers, accounts, and transactions |
| `import_sanctions.py` | Streams OFAC SDN Advanced XML via lxml iterparse and inserts entries |
| `import_un_sanctions.py` | Imports UN Consolidated Sanctions List XML |
| `bulk_screen.py` | CLI tool to screen a CSV of names against the sanctions database |
| `health_check.py` | System-wide status check with exit codes for monitoring |
| `generate_report.py` | Generates text and CSV compliance reports for a given date range |

---

## Testing

363 unit tests across 17 test modules in `tests/`, all using `unittest.mock.MagicMock` for service-layer isolation. No real database is used in tests. Test runner: pytest.
