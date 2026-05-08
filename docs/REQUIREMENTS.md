# System Requirements

## Table of Contents
1. [Functional Requirements](#1-functional-requirements)
2. [Non-Functional Requirements](#2-non-functional-requirements)
3. [System Requirements](#3-system-requirements)

---

## 1. Functional Requirements

### FR-01: User Authentication
- **FR-01.1** The system shall allow users to log in using a username and password.
- **FR-01.2** The system shall issue a JWT (JSON Web Token) upon successful login.
- **FR-01.3** The system shall invalidate expired tokens and redirect unauthenticated users to the login page.
- **FR-01.4** The system shall support user logout, which clears the active session token.

### FR-02: User Registration
- **FR-02.1** The system shall allow new users to self-register by providing their full name, username, email, password, and role.
- **FR-02.2** The system shall send a 6-digit verification code to the provided email address (via Brevo SMTP) before completing registration.
- **FR-02.3** The system shall validate that the email domain exists (MX record check) and reject invalid email addresses.
- **FR-02.4** Verification codes shall be single-use and expire after 10 minutes.
- **FR-02.5** The system shall reject duplicate usernames and email addresses.

### FR-03: Role-Based Access Control (RBAC)
- **FR-03.1** The system shall support three user roles: Admin, Analyst, and Supervisor.
- **FR-03.2** Admin users shall have full access to all modules including user management, rule configuration, and audit logs.
- **FR-03.3** Analyst users shall be able to view and investigate customers, transactions, alerts, and cases.
- **FR-03.4** Supervisor users shall be able to approve/escalate cases and file SARs.
- **FR-03.5** Role-based access shall be enforced server-side on every request; the system shall return HTTP 403 Forbidden for unauthorized access attempts.

### FR-04: Customer Management
- **FR-04.1** The system shall allow creation of customer profiles with full name, email, phone, nationality, date of birth, address, risk level, PEP status, and source of funds.
- **FR-04.2** The system shall auto-generate unique customer numbers in the format `CUS-XXXXXX`.
- **FR-04.3** The system shall allow searching and filtering customers by name, risk level, and PEP status.
- **FR-04.4** The system shall support marking customers as sanctions-flagged.

### FR-05: Account Management
- **FR-05.1** The system shall allow creation of bank accounts linked to a customer.
- **FR-05.2** Each account shall have a unique auto-generated account number, type (CHECKING, SAVINGS, BUSINESS), currency, and balance.
- **FR-05.3** Account balances shall be updated automatically upon transaction creation.

### FR-06: Transaction Monitoring
- **FR-06.1** The system shall allow creation of financial transactions between accounts with amount, currency, type, and country fields.
- **FR-06.2** Every transaction shall automatically trigger the AML Rules Engine upon submission.
- **FR-06.3** The system shall calculate and store a risk score (0–100) for each transaction.
- **FR-06.4** The system shall compute and maintain a composite risk band (LOW / MEDIUM / HIGH / CRITICAL) for each customer, updated automatically after each transaction or alert.
- **FR-06.5** Transactions exceeding risk thresholds shall be automatically flagged.
- **FR-06.6** The system shall support filtering transactions by date range, flagged status, and amount.

### FR-07: AML Rules Engine
- **FR-07.1** The system shall implement the following nine detection rules:
  - Large Transaction (single amount > $10,000)
  - Structuring / Smurfing (multiple amounts just below threshold)
  - High Frequency (excessive transactions within 24 hours)
  - High Velocity (large cumulative volume within time window)
  - High-Risk Country (transaction involving FATF/OFAC-listed country)
  - Rapid Movement (funds received and sent within hours)
  - Round Amount (suspiciously round transaction values)
  - PEP Transaction (involves a Politically Exposed Person)
  - Micro-Transaction (repeated small amounts at high frequency)
- **FR-07.2** Each rule shall have configurable thresholds, transaction counts, and time windows.
- **FR-07.3** Admin users shall be able to enable or disable individual rules.
- **FR-07.4** Each triggered rule shall produce a weighted risk score contribution.

### FR-08: Alert Management
- **FR-08.1** The system shall automatically generate alerts whenever a rule is triggered, a customer risk threshold is exceeded, or a sanctions hit is detected.
- **FR-08.2** Each alert shall be assigned a unique alert number, severity (LOW / MEDIUM / HIGH / CRITICAL), status (OPEN / INVESTIGATING / ESCALATED / FALSE_POSITIVE / CLOSED), and rule context.
- **FR-08.3** Analysts shall be able to update alert status and add investigation notes.
- **FR-08.4** Alerts shall be filterable by severity, status, and date.
- **FR-08.5** Analysts shall be able to create a case directly from an alert.

### FR-09: Case Management
- **FR-09.1** The system shall support creation of investigation cases linked to customers and alerts.
- **FR-09.2** Cases shall have a status workflow: OPEN → UNDER_REVIEW → ESCALATED → CLOSED.
- **FR-09.3** Users shall be able to add timestamped notes to cases.
- **FR-09.4** Supervisors shall be able to mark a case as SAR (Suspicious Activity Report) filed, with a SAR reference number.
- **FR-09.5** Cases shall be filterable by status, priority, and assigned user.

### FR-10: Sanctions Screening
- **FR-10.1** The system shall import and store the OFAC SDN Advanced XML list and the UN Consolidated Sanctions List into a local database.
- **FR-10.2** The system shall provide a fuzzy name search against both lists with tolerance for name variations and transliterations.
- **FR-10.3** The composite scoring formula per alias shall be:
  `Token Recall (per-token best Jaro-Winkler) × 0.60 + Full-string Jaro-Winkler × 0.25 + Token Jaccard Overlap × 0.15`
- **FR-10.4** The system shall support filtering results by entity type, country, and SDN program.
- **FR-10.5** Results shall be classified as EXACT (100), STRONG (≥85), POSSIBLE (≥70), or WEAK (<70).
- **FR-10.6** Users shall be able to adjust the minimum score threshold and maximum result count.

### FR-11: Dashboard & Analytics
- **FR-11.1** The system shall display KPI cards for: total transactions, flagged transactions, open alerts, and active cases.
- **FR-11.2** The system shall display a 30-day transaction volume trend (line chart).
- **FR-11.3** The system shall display a 30-day alert count trend (bar chart).
- **FR-11.4** The system shall display alert distribution by severity (pie chart).
- **FR-11.5** The system shall display case distribution by status (pie chart).
- **FR-11.6** The system shall display the top AML rules by number of triggered alerts.

### FR-12: ML Anomaly Detection
- **FR-12.1** The system shall provide an unsupervised anomaly detector based on the Isolation Forest algorithm to identify unusual transaction patterns not covered by predefined rules.
- **FR-12.2** The anomaly detector shall maintain a separate model per customer, trained on that customer's own transaction history.
- **FR-12.3** The detector shall evaluate each transaction on seven features: log(amount), hour of day, day of week, is_international, is_round_amount, transaction type, and channel.
- **FR-12.4** Each transaction shall receive an anomaly score (0–100) and an is_anomaly flag.
- **FR-12.5** Anomalous transactions shall be flagged independently of rule-based alerts.

### FR-13: Audit Logging
- **FR-13.1** The system shall maintain an immutable audit log recording all create, update, and delete operations across all modules.
- **FR-13.2** Each audit entry shall record the user identity, action type, affected entity, timestamp, IP address, and before/after JSON snapshots.
- **FR-13.3** Admin users shall be able to view and filter the full audit log.

---

## 2. Non-Functional Requirements

### NFR-01: Performance
- **NFR-01.1** API endpoints shall respond within 500 ms for all main operations under normal load.
- **NFR-01.2** The sanctions screening search shall return results within 3 seconds for any query against the full OFAC SDN list.

### NFR-02: Security
- **NFR-02.1** All passwords shall be hashed using bcrypt with a cost factor of 12.
- **NFR-02.2** JWT tokens shall expire after 8 hours.
- **NFR-02.3** The system shall comply with OWASP Top 10 mitigations: all database queries shall use parameterised statements (no SQL injection), internal stack traces shall never be exposed in API responses, and role-based access shall be enforced server-side on every route.

### NFR-03: Maintainability
- **NFR-03.1** The backend shall maintain a strict separation of layers: routers, services, models, and schemas shall reside in independent modules with no cross-layer imports.

### NFR-04: Testability
- **NFR-04.1** Unit test coverage shall reach at least 70% on domain logic, covering the services layer and the AML rules engine.

### NFR-05: Portability
- **NFR-05.1** The system shall run without code changes on Windows, macOS, and Linux.
- **NFR-05.2** The backend shall require Python 3.13+ and the frontend shall require Node.js 18+.

### NFR-06: Usability
- **NFR-06.1** The interface shall support both dark mode and light mode, with the preference persisted across sessions.
- **NFR-06.2** All error messages shall be human-readable and displayed inline in the UI.

### NFR-07: Reliability
- **NFR-07.1** The system shall not lose data on application restart (SQLite file persistence).
- **NFR-07.2** If SMTP email delivery fails, the system shall fall back to printing the verification code to the server console without crashing.
- **NFR-07.3** A failed AML rule evaluation shall not block transaction creation.

---

## 3. System Requirements

### SR-01: Hardware Requirements (Minimum)

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8 GB |
| Disk | 2 GB free | 5 GB free |
| Network | Internet access (for email) | Broadband |

> Note: The OFAC SDN database import requires approximately 500 MB of RAM during processing and ~300 MB of disk space for the resulting SQLite database.

### SR-02: Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.13+ | Backend runtime |
| Node.js | 18+ | Frontend build and dev server |
| npm | 9+ | Frontend package manager |
| pip | 24+ | Python package manager |
| Git | 2.x+ | Version control |

### SR-03: Python Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.115.5 | REST API framework |
| uvicorn[standard] | 0.32.1 | ASGI server |
| sqlalchemy | 2.0.36 | ORM and database abstraction |
| pydantic | 2.10.3 | Data validation |
| pydantic-settings | 2.6.1 | Environment config |
| python-jose[cryptography] | 3.3.0 | JWT encoding/decoding |
| passlib[bcrypt] | 1.7.4 | Password hashing |
| jellyfish | 1.1.0 | Jaro-Winkler fuzzy matching |
| lxml | 5.3.0 | XML streaming parser |
| dnspython | 2.7.0 | Email domain MX validation |
| python-dateutil | 2.9.0 | Date parsing utilities |
| bcrypt | 4.2.1 | bcrypt backend |
| scikit-learn | latest | Isolation Forest, Gradient Boosting |
| numpy | latest | Numerical feature processing |

### SR-04: Frontend Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| react | 18.x | UI framework |
| react-router-dom | 6.x | Client-side routing |
| axios | 1.x | HTTP client |
| recharts | 2.x | Chart components |
| react-icons | 5.x | Icon library |
| date-fns | 2.x | Date formatting |

### SR-05: External Services

| Service | Required | Purpose |
|---------|----------|---------|
| Brevo (or any SMTP provider) | Optional | Sending email verification codes (falls back to console if not configured) |
| OFAC SDN Advanced XML | Required for sanctions | Local file, obtained from `sanctionslistservice.ofac.treas.gov` |
| UN Consolidated List XML | Optional | Additional sanctions coverage |

### SR-06: Network Requirements

- Port **8000** must be available for the FastAPI backend
- Port **3000** must be available for the React development server
- Internet access required only for email delivery (SMTP); all other functionality is local
