# Test Cases — AML Transaction Monitoring System

## Authentication Test Cases

| TC-ID | Test Case | Steps | Expected Result | Status |
|-------|-----------|-------|-----------------|--------|
| TC-01 | Valid login | Enter admin/Admin@123, click Login | JWT issued, redirect to Dashboard | Pass |
| TC-02 | Invalid password | Enter admin/WrongPass, click Login | Invalid credentials error shown | Pass |
| TC-03 | Register with valid email | Enter valid email, receive code, complete form | Account created, redirect to Login | Pass |
| TC-04 | Register with fake email domain | Enter user@fakedomain12345.xyz | Email domain does not exist error | Pass |
| TC-05 | Register with wrong verification code | Enter wrong 6-digit code | Invalid verification code error | Pass |
| TC-06 | Access protected route without token | Navigate to /dashboard without login | Redirect to /login | Pass |

## AML Rules Engine Test Cases

| TC-ID | Test Case | Steps | Expected Result | Status |
|-------|-----------|-------|-----------------|--------|
| TC-07 | Large transaction alert | Create transaction over $10,000 | Alert generated with rule large_transaction | Pass |
| TC-08 | Structuring detection | Create 3 transactions just below $10,000 in 24h | Structuring alert generated | Pass |
| TC-09 | Round amount detection | Create transaction of $5,000.00 | Round amount alert generated | Pass |
| TC-10 | High-risk country alert | Create transaction with originating_country=IR | High-risk country alert generated | Pass |
| TC-11 | PEP transaction alert | Create transaction for PEP customer | PEP alert generated | Pass |
| TC-12 | Disabled rule no alert | Disable large_transaction rule, create $15,000 transaction | No alert generated | Pass |

## Sanctions Screening Test Cases

| TC-ID | Test Case | Steps | Expected Result | Status |
|-------|-----------|-------|-----------------|--------|
| TC-13 | Exact name match | Search Al-Qaida | STRONG match result shown | Pass |
| TC-14 | Fuzzy name match | Search Kadafi (variant of Gaddafi) | POSSIBLE match with score shown | Pass |
| TC-15 | Non-existent name | Search John Normal Citizen | No results or WEAK matches only | Pass |
| TC-16 | Filter by country | Search with country=IR | Only Iranian entities returned | Pass |
| TC-17 | Empty search | Submit empty search | Validation error shown | Pass |

## Alert Management Test Cases

| TC-ID | Test Case | Steps | Expected Result | Status |
|-------|-----------|-------|-----------------|--------|
| TC-18 | View alert detail | Click any alert row | Alert detail modal opens with rule context | Pass |
| TC-19 | Update alert status | Change status to investigating, click Update | Status updated; audit log entry created | Pass |
| TC-20 | Create case from alert | Click Create Case in alert detail | Case created; appears in Cases page | Pass |
| TC-21 | Analyst cannot view audit logs | Log in as ArayikAnalyst, go to /audit | 403 Forbidden error shown | Pass |

## Case Management Test Cases

| TC-ID | Test Case | Steps | Expected Result | Status |
|-------|-----------|-------|-----------------|--------|
| TC-22 | Add note to case | Open case, type note, click Add | Note appears in notes thread with timestamp | Pass |
| TC-23 | File SAR | Open case as supervisor, click File SAR, enter reference | SAR filed flag set; reference saved | Pass |
| TC-24 | Filter cases by status | Click Open status card | Table filters to open cases only | Pass |

## Dashboard Test Cases

| TC-ID | Test Case | Steps | Expected Result | Status |
|-------|-----------|-------|-----------------|--------|
| TC-25 | KPI cards load | Navigate to Dashboard | All 6 KPI cards show numeric values | Pass |
| TC-26 | Charts render | Navigate to Dashboard | Line chart, bar chart, pie charts all visible | Pass |
| TC-27 | Bell notification dropdown | Click bell icon in topbar | Dropdown shows 5 most recent open alerts | Pass |
| TC-28 | Light mode toggle | Click sun/moon icon in topbar | Theme switches; preference saved to localStorage | Pass |
