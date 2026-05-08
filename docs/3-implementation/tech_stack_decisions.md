# Technology Stack Decisions

This document records the rationale behind each major technology choice in the AML Transaction Monitoring System.

---

## Backend

### Python 3.13 + FastAPI
FastAPI was chosen over Flask and Django for three reasons: automatic OpenAPI/Swagger documentation generation (critical for a compliance system where API contracts matter), native async support via ASGI, and Pydantic v2 integration for strict request/response validation. Python 3.13 was used as the latest stable release with improved performance characteristics.

### SQLAlchemy ORM
SQLAlchemy's declarative ORM was chosen to keep database models readable and maintainable without writing raw SQL. The ORM layer also makes the codebase database-agnostic — switching from SQLite to PostgreSQL in a production deployment requires changing only the connection string.

### SQLite (WAL mode)
SQLite was chosen for the prototype to eliminate infrastructure dependencies — no separate database server needs to be running. WAL (Write-Ahead Logging) mode was enabled to allow concurrent reads alongside writes, which matters for a system that queries and inserts data simultaneously during transaction processing. Foreign keys were explicitly enabled (`PRAGMA foreign_keys = ON`) since SQLite disables them by default.

### Pydantic v2
Pydantic v2 is used for all API request and response schemas. It provides automatic type coercion, field-level validation, and clear error messages. v2 was chosen over v1 for its significantly improved performance and stricter validation behaviour.

### python-jose + passlib[bcrypt]
python-jose handles JWT encoding and decoding using the HS256 algorithm. passlib with the bcrypt backend handles password hashing. bcrypt was chosen over SHA-256 or MD5 because it is specifically designed for password hashing — it is slow by design, making brute-force attacks computationally expensive.

### jellyfish
jellyfish was chosen for fuzzy string matching in the sanctions screener because it provides both Jaro-Winkler distance and Soundex in a single lightweight library with no heavy dependencies. It outperforms simpler edit-distance libraries (such as python-Levenshtein) for name-matching tasks where transpositions and prefix agreement are more meaningful than raw edit cost.

### lxml (iterparse)
lxml's iterparse was chosen for parsing the OFAC SDN Advanced XML file (~2.6 million lines) because it streams elements one at a time without loading the entire document into memory. The standard library `xml.etree.ElementTree` was ruled out due to performance limitations on large files.

### APScheduler
APScheduler's BackgroundScheduler was used to run the daily transaction seed job at 08:00. It was chosen for its simplicity — no external broker (Redis, Celery) is required for a single-job schedule.

### dnspython
Used exclusively for MX record validation during user registration. Before sending a verification code, the system resolves the email domain's MX record to confirm the domain can receive email, reducing wasted SMTP calls on invalid addresses.

---

## Frontend

### React 18 (Create React App)
React 18 was chosen for its component model, which maps naturally to the modular nature of a compliance dashboard. Create React App was used instead of Vite for simplicity and stability in a capstone context. React 18's concurrent features are not used directly, but the upgrade path is open.

### React Router v6
React Router v6 provides declarative client-side routing with nested route support. The `<Navigate>` component is used to enforce authentication guards without custom logic.

### Axios
Axios was chosen over the native `fetch` API for its interceptor system — a single request interceptor automatically attaches the JWT `Authorization` header to every outgoing request, and a response interceptor handles 401 redirects globally. This eliminates repetitive auth logic in every page component.

### Recharts
Recharts was chosen for charting because it is built on top of D3 but exposes a React-native component API, eliminating the need to manage D3's imperative DOM manipulation. The library covers all required chart types: line, bar, pie, and area charts.

### Custom CSS (no UI framework)
Tailwind CSS, Material UI, and Ant Design were considered and rejected. A compliance dashboard requires precise visual control over colour-coding (severity badges, risk level colours, status chips) and a custom dark/light theme with brand-specific amber accents. CSS variables (`--text-primary`, `--gradient-main`, etc.) defined in `index.css` provide a consistent design token system without the overhead of a third-party component library.

---

## Infrastructure

### No Docker / No CI Pipeline
Docker and GitHub Actions were not included in the prototype. The decision was deliberate — the capstone scope focused on implementing correct AML domain logic rather than DevOps tooling. All dependencies are managed via `pip` and `npm`, and the system starts with two commands.

### No Alembic (Database Migrations)
Alembic was excluded because the schema is stable and the database is recreated by running `seed_data.py` during development. For a production deployment, Alembic would be introduced to manage schema evolution without data loss.

### SMTP (Brevo-compatible)
Email delivery uses Python's standard `smtplib` with configurable SMTP credentials in `.env`. The default configuration points to `smtp.gmail.com` but is provider-agnostic — Brevo, SendGrid, or any other SMTP relay can be used by updating the `.env` file. If no credentials are configured, the system falls back to printing verification codes to the server console.
