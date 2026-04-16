# API Specification — AML Transaction Monitoring System

Base URL: http://localhost:8000/api/v1
Authentication: Bearer JWT token in Authorization header
Interactive docs: http://localhost:8000/docs (Swagger UI)

## Authentication Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | /auth/send-verification | Send verification code to email | No |
| POST | /auth/register | Register new user | No |
| POST | /auth/login | Login, returns JWT token | No |
| POST | /auth/logout | Logout current session | Yes |
| GET | /auth/me | Get current user info | Yes |
| GET | /auth/users | List all users | Admin only |

## Customer Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /customers | List customers with search and filter | Yes |
| POST | /customers | Create customer | Analyst, Admin |
| GET | /customers/{id} | Get customer detail | Yes |
| PUT | /customers/{id} | Update customer | Analyst, Admin |
| GET | /customers/{id}/accounts | Get customer accounts | Yes |
| POST | /customers/accounts | Create account | Analyst, Admin |

## Transaction Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /transactions | List transactions with filters | Yes |
| POST | /transactions | Create transaction, triggers rules engine | Analyst, Admin |
| GET | /transactions/{id} | Get transaction detail | Yes |

## AML Rules Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /rules | List all rules | Yes |
| POST | /rules | Create new rule | Admin, Supervisor |
| PUT | /rules/{id} | Update rule configuration | Admin, Supervisor |
| PATCH | /rules/{id}/toggle | Enable or disable rule | Admin, Supervisor |

## Alert Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /alerts | List alerts with severity and status filters | Yes |
| GET | /alerts/{id} | Get alert detail with rule context | Yes |
| PUT | /alerts/{id} | Update alert status | Analyst, Admin, Supervisor |
| GET | /alerts/stats | Alert statistics summary | Yes |

## Case Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /cases | List cases with status filter | Yes |
| POST | /cases | Create case from alert | Analyst, Admin |
| GET | /cases/{id} | Get case detail | Yes |
| PUT | /cases/{id} | Update case status or file SAR | Analyst, Admin, Supervisor |
| GET | /cases/{id}/notes | Get case notes | Yes |
| POST | /cases/{id}/notes | Add note to case | Yes |

## Sanctions Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | /sanctions/search | Search OFAC SDN list by name | Yes |
| GET | /sanctions/stats | SDN database statistics | Yes |
| GET | /sanctions/entries | List entries with pagination | Yes |

## Dashboard Endpoint

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /dashboard | Full dashboard data: KPIs and charts | Yes |

## Risk Scoring Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /risk-scoring/customers | All customer risk scores | Yes |
| GET | /risk-scoring/customers/{id} | Single customer risk score | Yes |

## Blacklist Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /blacklist | List blacklist entries | Yes |
| POST | /blacklist | Add blacklist entry | Admin, Supervisor |
| DELETE | /blacklist/{id} | Remove entry | Admin |

## Reporting Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /reports/monthly | Monthly transaction summary | Yes |
| GET | /reports/alerts | Alert statistics report | Yes |
| GET | /reports/sar | SAR filing summary | Yes |
| GET | /reports/customers | Customer risk distribution | Yes |
| GET | /reports/rules | Rule performance report | Yes |
| GET | /reports/export/full | Full compliance report JSON | Admin, Supervisor |

## Escalation Endpoint

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | /escalation/run | Run escalation engine manually | Admin, Supervisor |

## Audit Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | /audit | List audit logs with filters | Admin only |
| GET | /audit/actions | List available action types | Admin only |
