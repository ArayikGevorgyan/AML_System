# Use Cases — AML Transaction Monitoring System

## UC-01: User Registration
Actor: New User
Goal: Create a new account in the system

Main Flow:
1. User navigates to Register page
2. User enters email address
3. System validates email domain via DNS MX lookup
4. System sends 6-digit verification code to email
5. User enters verification code
6. User fills in full name, username, password, role
7. System creates account and redirects to Login

Alternative Flow:
- Step 3a: Email domain has no MX records — system shows Email domain does not exist
- Step 5a: Wrong code entered — system shows Invalid verification code

## UC-02: User Login
Actor: Registered User
Goal: Authenticate and access the system

Main Flow:
1. User enters username and password
2. System verifies credentials
3. System issues JWT token
4. User is redirected to Dashboard

Alternative Flow:
- Step 2a: Wrong credentials — Invalid username or password

## UC-03: Create Transaction
Actor: Analyst, Admin
Goal: Record a new financial transaction

Main Flow:
1. User navigates to Transactions page
2. User clicks New Transaction
3. User fills in amount, type, from/to customer, account, countries
4. System saves transaction
5. System runs AML rules engine in background
6. If rules match, alerts are generated automatically

## UC-04: Review Alert
Actor: Analyst
Goal: Triage an open alert

Main Flow:
1. Analyst navigates to Alerts page
2. Analyst clicks an alert to open detail view
3. Analyst reviews severity, rule context, risk score
4. Analyst updates status: investigating, false_positive, escalated, or closed
5. System logs the status change in audit trail

Extension: Step 4a — Analyst clicks Create Case to proceed to UC-05

## UC-05: Create Investigation Case
Actor: Analyst
Goal: Open a case to investigate a suspicious alert

Main Flow:
1. From Alert detail, Analyst clicks Create Case
2. System creates case linked to the alert
3. Analyst adds investigation notes
4. Supervisor reviews and updates case status

## UC-06: File SAR
Actor: Supervisor
Goal: File a Suspicious Activity Report for a confirmed case

Preconditions: Case status is escalated or under_review

Main Flow:
1. Supervisor opens case
2. Supervisor clicks File SAR
3. Supervisor enters SAR reference number
4. System records SAR filing date and reference
5. Case is marked as SAR filed

## UC-07: Sanctions Search
Actor: Any authenticated user
Goal: Screen a name against the OFAC SDN list

Main Flow:
1. User navigates to Sanctions Search
2. User enters name and optionally type, country, program, min score
3. System normalizes name, applies Soundex pre-filter
4. System calculates Jaro-Winkler composite score for candidates
5. System returns results sorted by match score
6. Results show score badge (STRONG/POSSIBLE/WEAK), aliases, programs, addresses

## UC-08: Manage AML Rules
Actor: Admin, Supervisor
Goal: Configure detection rules

Main Flow:
1. User navigates to AML Rules page
2. User views all rules with current status
3. User toggles a rule on or off
4. Optionally user creates a new custom rule with thresholds

## UC-09: View Dashboard
Actor: Any authenticated user
Goal: Get an overview of system compliance status

Main Flow:
1. User navigates to Dashboard
2. System displays KPI cards: open alerts, transactions, volume, cases, high-risk customers, sanctions checks
3. System displays charts: 30-day trend, alerts by severity, cases by status, top rules

## UC-10: View Audit Logs
Actor: Admin only
Goal: Review system activity for compliance

Main Flow:
1. Admin navigates to Audit Logs
2. System displays chronological log entries
3. Admin can filter by action type and date
4. Each entry shows user, action, entity, before/after values
