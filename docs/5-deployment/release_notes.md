# Release Notes — AML Transaction Monitoring System

## Version 1.0.0 — March 2026

### New Features

| Feature | Description |
|---------|-------------|
| User Registration | Email verification with DNS MX validation and 6-digit code |
| JWT Authentication | Role-based access control for Admin, Analyst, Supervisor |
| Customer Management | Full CRUD with PEP and sanctions flagging |
| Transaction Monitoring | Background rules engine evaluation on every transaction |
| AML Rules Engine | 8 detection rules: large transaction, structuring, frequency, velocity, round amount, high-risk country, rapid movement, PEP transaction |
| Alert Generation | Automatic alerts with severity levels LOW, MEDIUM, HIGH, CRITICAL |
| Alert Escalation | Auto-escalates stale alerts after 48 hours and repeated alerts |
| Case Management | Notes thread and SAR filing support |
| Sanctions Screening | OFAC SDN fuzzy matching with Jaro-Winkler and Soundex |
| Risk Scoring | Composite 0-100 score per customer |
| Blacklist Management | Internal blacklist for IPs, countries, entities, emails |
| Compliance Reporting | API with 5 report types |
| Audit Logging | Full trail of all system actions |
| Dashboard | KPI cards, line chart, bar chart, two pie charts, top rules, recent alerts |
| Notification Bell | Dropdown showing 5 most recent open alerts |
| Dark and Light Mode | Theme toggle with localStorage persistence |
| Daily Data Generation | Cron job for automatic synthetic data creation |

### Known Issues
- SQLite not recommended for more than 100,000 concurrent transactions — upgrade to PostgreSQL for production
- OFAC XML must be manually re-imported when OFAC publishes updates (approximately weekly)
- Email delivery requires valid SMTP configuration; falls back to terminal output in dev mode

### Resolved Issues
- Fixed lxml 5.2.1 Python 3.13 build failure — upgraded to 5.3.0
- Fixed pydantic-core Python 3.13 incompatibility — upgraded to pydantic 2.10.3
- Fixed KPI card number overflow for large monetary values
- Fixed dashboard chart tooltip text invisible in dark mode
