# Software Requirements Specification (SRS)
## AML Transaction Monitoring System — v1.0

## 1. Introduction

### 1.1 Purpose
This document describes the functional and non-functional requirements for the AML Transaction Monitoring System.

### 1.2 Definitions
- AML: Anti-Money Laundering
- SAR: Suspicious Activity Report
- PEP: Politically Exposed Person
- OFAC: Office of Foreign Assets Control
- SDN: Specially Designated Nationals list

## 2. Functional Requirements

### 2.1 Authentication and Authorization

| ID | Requirement |
|----|-------------|
| FR-01 | Users shall register with email verification (6-digit code) |
| FR-02 | System shall validate email domain using DNS MX record lookup |
| FR-03 | Users shall log in with username and password |
| FR-04 | System shall issue JWT tokens valid for 24 hours |
| FR-05 | Three roles: Admin, Analyst, Supervisor with different permissions |
| FR-06 | Admins can view all users and create new accounts |

### 2.2 Customer Management

| ID | Requirement |
|----|-------------|
| FR-07 | System shall store customer profile with name, nationality, DOB, occupation, income |
| FR-08 | Each customer shall have a unique auto-generated customer number (CUS-XXXXXX) |
| FR-09 | Customer risk level shall be: LOW, MEDIUM, HIGH, CRITICAL |
| FR-10 | System shall flag customers as PEP (Politically Exposed Person) |
| FR-11 | System shall flag customers on internal sanctions list |
| FR-12 | Customers shall have one or more linked accounts |

### 2.3 Transaction Monitoring

| ID | Requirement |
|----|-------------|
| FR-13 | System shall record transactions with amount, type, countries, customer, account |
| FR-14 | Each transaction shall be evaluated by the rules engine upon creation |
| FR-15 | Rules engine shall run asynchronously in background tasks |
| FR-16 | Transactions shall have a risk_score (0-100) and flagged boolean |

### 2.4 AML Rules Engine

| ID | Requirement |
|----|-------------|
| FR-17 | System shall implement 8 AML detection rules |
| FR-18 | Rules shall be configurable with threshold amounts, time windows, countries |
| FR-19 | Rules shall be enabled/disabled by Admin/Supervisor |
| FR-20 | Each rule match shall produce an Alert with severity and risk score |

### Detection Rules

| Rule | Threshold | Basis |
|------|-----------|-------|
| Large Transaction | Over $10,000 | U.S. BSA |
| Structuring | Multiple transactions just below $10,000 | 31 U.S.C. Section 5324 |
| High Frequency | More than 5 transactions per 24h | FATF Rec. 20 |
| High Velocity | Over $50,000 per 24h | FinCEN |
| Round Amount | Ends in .00, over $1,000 | FATF |
| High-Risk Country | FATF/OFAC country list | OFAC |
| Rapid Movement | In and out within 2h | FinCEN |
| PEP Transaction | Customer flagged as PEP | FATF Rec. 12 |

### 2.5 Alert Management

| ID | Requirement |
|----|-------------|
| FR-21 | Alerts shall have: alert_number, severity, status, reason, risk_score |
| FR-22 | Alert statuses: open, investigating, false_positive, escalated, closed |
| FR-23 | Analysts can update alert status |
| FR-24 | Analysts can create a Case from an Alert |
| FR-25 | Alert escalation engine shall auto-escalate stale or repeated alerts |

### 2.6 Case Management

| ID | Requirement |
|----|-------------|
| FR-26 | Cases shall have: case number, status, assigned analyst, linked alerts |
| FR-27 | Case statuses: open, under_review, escalated, closed |
| FR-28 | Users can add notes to cases |
| FR-29 | Supervisors can file a SAR (Suspicious Activity Report) |
| FR-30 | SAR filing records SAR reference number and filing date |

### 2.7 Sanctions Screening

| ID | Requirement |
|----|-------------|
| FR-31 | System shall import OFAC SDN Advanced XML list into SQLite database |
| FR-32 | Search shall use Jaro-Winkler similarity scoring |
| FR-33 | Search shall use Soundex phonetic pre-filter for performance |
| FR-34 | Results shall show match score, aliases, programs, and addresses |
| FR-35 | Users can filter by entity type, country, program, and minimum score |

## 3. Non-Functional Requirements

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-01 | Performance | Rules engine evaluation shall complete within 2 seconds per transaction |
| NFR-02 | Performance | Sanctions search shall return results within 3 seconds |
| NFR-03 | Security | Passwords shall be hashed using bcrypt |
| NFR-04 | Security | All API endpoints shall require JWT authentication |
| NFR-05 | Security | Role-based access shall be enforced server-side |
| NFR-06 | Reliability | SQLite WAL mode for concurrent read/write |
| NFR-07 | Usability | UI shall support dark and light modes |
| NFR-08 | Maintainability | Backend code shall follow modular service/router/model pattern |
| NFR-09 | Scalability | XML import shall use streaming parser for 2.6M-line files |
| NFR-10 | Compliance | System shall align with BSA, FATF, FinCEN, and OFAC requirements |
