# Technical Design Document — AML Transaction Monitoring System

## 1. Technology Stack

| Layer | Technology | Version | Reason |
|-------|-----------|---------|--------|
| Backend Framework | FastAPI | 0.115.5 | Async, auto Swagger docs, Pydantic integration |
| ORM | SQLAlchemy | 2.0.36 | Type-safe queries, migration support |
| Database | SQLite | Built-in | Simple, serverless, WAL mode for concurrency |
| Auth | python-jose | 3.3.0 | JWT token creation and validation |
| Password Hashing | passlib + bcrypt | 1.7.4 / 4.2.1 | Industry standard bcrypt |
| Fuzzy Matching | jellyfish | 1.1.0 | Jaro-Winkler and Soundex |
| XML Parsing | lxml | 5.3.0 | Streaming iterparse for large files |
| Email Validation | dnspython | 2.7.0 | MX record lookup |
| Frontend | React | 18 | Component-based SPA |
| Charts | Recharts | Latest | React-native chart library |
| HTTP Client | Axios | Latest | Interceptors for JWT injection |
| Routing | React Router | v6 | Declarative routing |

## 2. Key Design Decisions

### SQLite over PostgreSQL
SQLite chosen for simplicity — no server setup required, single file database. WAL mode enables concurrent reads. For production scale, PostgreSQL is recommended.

### Background Task for Rules Engine
Rules engine runs in FastAPI BackgroundTasks (not inline) so the transaction creation API returns immediately without waiting for rule evaluation. This keeps response time under 100ms.

### Three-Pass OFAC XML Import
The 2.6M-line OFAC XML is parsed in three passes using lxml.iterparse (streaming, not loading into memory). Pass 1 builds reference value maps. Pass 2 builds location index. Pass 3 extracts entities and batch inserts 500 at a time.

### Sanctions Screening Algorithm
Score = (Jaro-Winkler x 0.70) + (Token Overlap x 0.20) + (Prefix Bonus x 0.10)
STRONG: 0.85 or above. POSSIBLE: 0.70 or above. WEAK: below 0.70.

### Risk Score Formula

| Factor | Weight | Details |
|--------|--------|---------|
| Profile | 40% | PEP status (+25), sanctions flag (+35), high-risk country (+20), HIGH risk level (+40) |
| Transaction Behavior | 35% | Flagged ratio x50, high volume (+20), high frequency (+15) |
| Alert History | 25% | CRITICAL x30, HIGH x15, MEDIUM x8 |

Final score = minimum of 100 and sum of all factors.

## 3. Module Structure

Backend modules:
- core: security.py (bcrypt + JWT), dependencies.py (FastAPI DI), enums.py
- models: SQLAlchemy ORM models for all 14 tables
- schemas: Pydantic request and response schemas
- routers: FastAPI route handlers (thin layer, delegates to services)
- services: Business logic (thick layer with all computation)
- scripts: seed_data.py, import_sanctions.py, seed_today.py

## 4. API Authentication Flow

1. Client sends POST /auth/login with username and password
2. Server verifies password using bcrypt
3. Server creates JWT token signed with HS256
4. Client stores token in localStorage
5. Every subsequent request includes: Authorization: Bearer token
6. Server decodes JWT, gets user, checks role, executes handler

## 5. Frontend State Management
- AuthContext: Stores user object and JWT token; persists to localStorage
- ThemeContext: Stores dark/light preference; applies data-theme attribute to body element
- Local state: Each page manages its own data via useState and useEffect with API calls
- No Redux or global state management needed at this scale
