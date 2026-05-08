# Known Issues & Limitations

This document records known limitations, intentional simplifications, and open items in the current prototype. These are not bugs — they are deliberate trade-offs appropriate for a capstone project scope.

---

## Security

### JWT Stored in localStorage
The JWT token is stored in the browser's `localStorage`. In a production system, HttpOnly cookies would be used instead to prevent XSS-based token theft. The current approach was chosen for simplicity in a demo environment.

### Hardcoded SECRET_KEY Default
`config.py` contains a hardcoded fallback value for `SECRET_KEY`. In production, this must be replaced with a strong random secret loaded exclusively from environment variables. The `.env.example` file does not document this setting.

### Rate Limiting Not Active
A `RateLimitMiddleware` exists in `core/rate_limiter.py` but is not registered in `main.py`. Login and registration endpoints are therefore not protected against brute-force or enumeration attacks in the current build.

### No Refresh Token
The authentication system issues a single JWT with an 8-hour lifetime. There is no refresh token mechanism — users must re-authenticate after expiry.

### Audit Log Is Not Cryptographically Immutable
The audit log records all sensitive actions with before/after JSON snapshots, but rows are plain database records with no hash chain or digital signature. A determined database administrator could modify audit entries. In a production compliance system, append-only storage or an external audit sink would be required.

---

## Data & Storage

### SQLite Not Suitable for Production Load
SQLite is appropriate for a single-user or low-concurrency prototype. Under production load (multiple concurrent analysts), SQLite's file-level locking would become a bottleneck. Migration to PostgreSQL is straightforward given the SQLAlchemy ORM abstraction.

### No Schema Migration Tool
The database schema is managed by `Base.metadata.create_all()` on startup. Any schema change requires dropping and recreating the database. For production use, Alembic should be introduced to manage migrations without data loss.

### Seed Data Is Fixed
`seed_data.py` seeds 20 customers with static demo data. The daily scheduler runs `seed_today.py` to append new transactions each day. There is no mechanism to vary the seeded customer profiles.

---

## Sanctions Screening

### Local Database Only
The OFAC SDN and UN Consolidated List are imported once into the local SQLite database. There is no automated refresh — the database must be manually re-imported when the official lists are updated (OFAC updates the SDN list multiple times per week in production systems).

### No Real-Time Screening on Transaction Submission
Sanctions screening is a manual search operation via the UI. Transactions are not automatically screened against the sanctions list at submission time — only the rules engine runs automatically.

---

## Machine Learning

### Anomaly Detector Requires Transaction History
The Isolation Forest model per customer is trained lazily on first use. If a customer has fewer than 10 transactions, the model falls back to rule-based scoring. New customers have no anomaly detection coverage until sufficient history accumulates.

### Risk Predictor Is Not Trained on Real SAR Labels
The `CustomerRiskModel` (Gradient Boosting) requires labelled training data (customers who generated SARs = positive class). In the prototype, the model is not pre-trained — it requires running `ml/train.py` with real labelled data before predictions are meaningful.

---

## Infrastructure

### No Docker or CI/CD Pipeline
The system has no Docker configuration and no GitHub Actions workflow. Deployment requires manual setup of Python and Node.js environments. There are no automated checks on pull requests.

### Single Scheduled Job
The background scheduler runs only one job: a daily transaction seed at 08:00. There is no scheduled risk score refresh, no scheduled sanctions list update, and no scheduled alert escalation sweep.

### No Email Queue
Email verification codes are sent synchronously within the request/response cycle. If SMTP delivery is slow, the `/auth/send-verification` endpoint will block until the email is sent or times out.

---

## Frontend

### No Pagination on Large Tables
Customer, transaction, and audit log tables load all records in a single API call. For databases with tens of thousands of records, this will cause slow page loads. Server-side pagination is not yet implemented.

### Token Expiry Not Handled Gracefully
When the JWT expires mid-session, the user receives a generic error rather than a smooth redirect to the login page with a "session expired" message.
