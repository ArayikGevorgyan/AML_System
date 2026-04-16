# System Architecture — AML Transaction Monitoring System

## 1. High-Level Architecture

The system follows a three-tier architecture: React frontend, FastAPI backend, and SQLite database.

The React frontend communicates with the FastAPI backend via HTTP REST APIs using JWT authentication. The backend contains 12 routers, a services layer, and an ORM layer connecting to SQLite.

External data: OFAC SDN Advanced XML is imported once via a streaming parser into the SQLite database.

## 2. Backend Routers

| Router | Endpoints | Auth Required |
|--------|-----------|---------------|
| auth | login, register, send-verification, me, logout, users | Partial |
| customers | CRUD for customers and accounts | Yes |
| transactions | Create and list transactions | Yes |
| rules | CRUD and toggle for AML rules | Yes |
| alerts | List, get, update alerts | Yes |
| cases | CRUD cases, notes, SAR filing | Yes |
| sanctions | Search OFAC SDN, stats | Yes |
| dashboard | KPIs and charts | Yes |
| audit | Audit log viewer | Admin only |
| blacklist | Internal blacklist management | Yes |
| reporting | Compliance reports | Yes |
| escalation | Run escalation engine | Admin/Supervisor |

## 3. Services Layer

| Service | Responsibility |
|---------|---------------|
| rules_engine.py | Evaluate 8 AML detection rules per transaction |
| sanctions_screener.py | Fuzzy name matching against OFAC SDN database |
| risk_scoring_service.py | Compute composite risk score (0-100) per customer |
| alert_service.py | Create alerts from rule matches |
| escalation_service.py | Auto-escalate stale and repeated alerts |
| case_service.py | Case CRUD with SAR filing support |
| reporting_service.py | Generate compliance reports |
| audit_service.py | Log all system actions with before/after snapshots |
| email_service.py | Send verification codes via SMTP |

## 4. Security Architecture

| Layer | Mechanism |
|-------|-----------|
| Password Storage | bcrypt hashing (cost factor 12) |
| Authentication | JWT tokens signed with HS256, 24h expiry |
| Authorization | Role-based: require_roles() dependency factory |
| Email Validation | DNS MX record lookup via dnspython |

## 5. Data Flow: Transaction Monitoring

Step 1: User submits transaction via POST /api/v1/transactions

Step 2: Transaction saved to SQLite database

Step 3: BackgroundTask triggers RulesEngine.evaluate()

Step 4: For each enabled rule — if match found, create RuleMatch object

Step 5: AlertService.create_alerts_from_matches() saves alerts to database

Step 6: Alerts become visible in the Alerts page

## 6. Sanctions Screening Algorithm

Query normalization removes noise words and applies unicode normalization.
Soundex phonetic pre-filter reduces the candidate pool from thousands to hundreds.
Composite score formula: Jaro-Winkler times 0.70 plus Token Overlap times 0.20 plus Prefix Bonus times 0.10.
Results are ranked: STRONG (0.85+), POSSIBLE (0.70+), WEAK (below 0.70).
