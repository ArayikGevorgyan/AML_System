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
- **FR-02.2** The system shall send a 6-digit verification code to the provided email address before completing registration.
- **FR-02.3** The system shall validate that the email domain exists (MX record check) and reject invalid email addresses with the message "Email domain does not exist or cannot receive emails."
- **FR-02.4** Verification codes shall expire after 10 minutes.
- **FR-02.5** The system shall reject duplicate usernames and email addresses.

### FR-03: Role-Based Access Control (RBAC)
- **FR-03.1** The system shall support three user roles: Admin, Analyst, and Supervisor.
- **FR-03.2** Admin users shall have full access to all modules including user management, rule configuration, and audit logs.
- **FR-03.3** Analyst users shall be able to view and investigate customers, transactions, alerts, and cases.
- **FR-03.4** Supervisor users shall be able to approve/escalate cases and file SARs.
- **FR-03.5** The system shall return HTTP 403 Forbidden for unauthorized role access attempts.

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
- **FR-06.4** Transactions exceeding risk thresholds shall be automatically flagged.
- **FR-06.5** The system shall support filtering transactions by date range, flagged status, and amount.

### FR-07: AML Rules Engine
- **FR-07.1** The system shall implement the following detection rules:
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
- **FR-08.1** The system shall automatically generate alerts when AML rules are triggered.
- **FR-08.2** Each alert shall be assigned a unique alert number, severity (LOW/MEDIUM/HIGH/CRITICAL), status (OPEN/INVESTIGATING/FALSE_POSITIVE/ESCALATED/CLOSED), and rule context.
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
- **FR-10.1** The system shall import and store the official OFAC SDN Advanced XML list into a local database.
- **FR-10.2** The system shall provide a fuzzy name search against the SDN list using a composite scoring algorithm.
- **FR-10.3** The scoring formula shall be: `Jaro-Winkler × 0.70 + Token Overlap × 0.20 + Prefix Bonus × 0.10`.
- **FR-10.4** The system shall support filtering by entity type, country, and SDN program.
- **FR-10.5** Results shall be classified as STRONG (≥0.85), POSSIBLE (≥0.70), or WEAK (≥0.60).
- **FR-10.6** Users shall be able to adjust the minimum score threshold and maximum result count.

### FR-11: Dashboard & Analytics
- **FR-11.1** The system shall display KPI cards for: total transactions, flagged transactions, open alerts, and active cases.
- **FR-11.2** The system shall display a 30-day transaction volume trend (line chart).
- **FR-11.3** The system shall display a 30-day alert count trend (bar chart).
- **FR-11.4** The system shall display alert distribution by severity (pie chart).
- **FR-11.5** The system shall display case distribution by status (pie chart).
- **FR-11.6** The system shall display the top AML rules by number of triggered alerts.

### FR-12: Audit Logging
- **FR-12.1** The system shall log all create, update, and delete operations across all modules.
- **FR-12.2** Each audit entry shall record the user, action type, affected entity, timestamp, IP address, and before/after JSON snapshots.
- **FR-12.3** Admin users shall be able to view and filter the full audit log.

---

## 2. Non-Functional Requirements

### NFR-01: Performance
- **NFR-01.1** API endpoints shall respond within 500ms for standard CRUD operations under normal load.
- **NFR-01.2** The sanctions screening search shall return results within 3 seconds for any query against the full SDN list.
- **NFR-01.3** The OFAC SDN XML import shall process the 2.6-million-line file using streaming (iterparse) to avoid memory exhaustion.
- **NFR-01.4** The database shall use WAL (Write-Ahead Logging) mode to support concurrent reads and writes without locking.

### NFR-02: Security
- **NFR-02.1** All passwords shall be hashed using bcrypt with a cost factor of 12.
- **NFR-02.2** JWT tokens shall expire after 8 hours.
- **NFR-02.3** All protected API routes shall require a valid JWT in the Authorization header.
- **NFR-02.4** Role-based access shall be enforced server-side on every request.
- **NFR-02.5** The system shall not expose password hashes or internal stack traces in API responses.
- **NFR-02.6** Email verification codes shall be single-use and expire after 10 minutes.

### NFR-03: Usability
- **NFR-03.1** The UI shall support both dark mode and light mode, with the preference persisted across sessions.
- **NFR-03.2** All data tables shall support search and filter operations without page reloads.
- **NFR-03.3** The dashboard shall load all KPIs and charts in a single API call.
- **NFR-03.4** Error messages shall be human-readable and displayed inline in the UI.

### NFR-04: Reliability
- **NFR-04.1** The system shall not lose data on application restart (SQLite persistence).
- **NFR-04.2** If SMTP email delivery fails, the system shall fall back to printing the verification code to the server console without crashing.
- **NFR-04.3** Failed AML rule evaluation shall not block transaction creation.

### NFR-05: Maintainability
- **NFR-05.1** AML rule thresholds shall be configurable via the UI without code changes.
- **NFR-05.2** Each module shall be separated into its own router and service layer.
- **NFR-05.3** All database models shall use SQLAlchemy ORM with typed columns.
- **NFR-05.4** API request/response schemas shall be validated using Pydantic v2.

### NFR-06: Scalability
- **NFR-06.1** The backend architecture shall be stateless to allow horizontal scaling.
- **NFR-06.2** The sanctions screener shall use phonetic pre-filtering (Soundex) to limit the candidate pool before applying expensive string metrics.
- **NFR-06.3** The SDN import shall batch-insert records in groups of 500 to avoid memory spikes.

### NFR-07: Compatibility
- **NFR-07.1** The backend shall support Python 3.13+.
- **NFR-07.2** The frontend shall support modern browsers (Chrome, Firefox, Safari, Edge).
- **NFR-07.3** The system shall run on macOS, Linux, and Windows.

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
| jellyfish | 1.1.0 | Jaro-Winkler and Soundex |
| lxml | 5.3.0 | XML streaming parser |
| dnspython | 2.7.0 | Email domain MX validation |
| python-dateutil | 2.9.0 | Date parsing utilities |
| bcrypt | 4.2.1 | bcrypt backend |

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
| Brevo (or any SMTP) | Optional | Sending email verification codes |
| OFAC SDN XML file | Required for sanctions | Local file, obtained from `sanctionslistservice.ofac.treas.gov` |

### SR-06: Network Requirements

- Port **8000** must be available for the FastAPI backend
- Port **3000** must be available for the React development server
- Internet access required only for email delivery (SMTP); all other functionality is local
