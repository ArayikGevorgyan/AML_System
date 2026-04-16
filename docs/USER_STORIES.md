# User Stories

## Roles

| Role | Description |
|------|-------------|
| **Admin** | System administrator with full access to all modules, user management, and configuration |
| **Analyst** | Compliance analyst who investigates transactions, reviews alerts, and manages cases |
| **Supervisor** | Senior compliance officer who oversees investigations, escalates cases, and files SARs |

---

## Epic 1: Authentication & Registration

### US-001 — User Login
**As a** compliance user (Admin, Analyst, or Supervisor),
**I want to** log in with my username and password,
**So that** I can securely access the AML monitoring system.

**Acceptance Criteria:**
- Given valid credentials, the user receives a JWT token and is redirected to the Dashboard.
- Given invalid credentials, the user sees a clear error message.
- The session expires after 8 hours of inactivity.

---

### US-002 — User Registration with Email Verification
**As a** new compliance team member,
**I want to** register my own account by providing my details and verifying my email,
**So that** I can access the system without needing an admin to create my account manually.

**Acceptance Criteria:**
- The user fills in full name, username, email, password, and role.
- A 6-digit code is sent to the provided email address.
- If the email domain is invalid, the system displays: "Email domain does not exist or cannot receive emails."
- The code expires in 10 minutes.
- On successful verification, the account is created and the user is redirected to login.

---

### US-003 — User Logout
**As a** logged-in user,
**I want to** log out of the system,
**So that** my session is ended and unauthorized access is prevented.

**Acceptance Criteria:**
- Clicking logout clears the JWT token and redirects to the login page.
- After logout, accessing any protected page redirects back to login.

---

### US-004 — Dark / Light Mode Toggle
**As a** user,
**I want to** switch between dark and light mode,
**So that** I can use the interface comfortably in different lighting conditions.

**Acceptance Criteria:**
- A toggle button in the top bar switches between dark and light mode.
- The preference is saved and persists after page refresh or app restart.

---

## Epic 2: Customer Management

### US-005 — View Customer List
**As an** Analyst or Admin,
**I want to** view a list of all customers with their risk levels and PEP status,
**So that** I can quickly identify high-risk individuals.

**Acceptance Criteria:**
- The customer table shows name, customer number, nationality, risk level, PEP flag, and sanctions flag.
- The list is searchable by name.
- Risk levels are color-coded (green = LOW, yellow = MEDIUM, red = HIGH).

---

### US-006 — Create Customer Profile
**As an** Admin or Analyst,
**I want to** create a new customer profile with all relevant details,
**So that** the customer can be monitored in the system.

**Acceptance Criteria:**
- The form includes full name, email, phone, nationality, date of birth, address, risk level, PEP status, sanctions flag, annual income, and source of funds.
- A unique customer number is auto-generated (e.g., CUS-000021).
- The new customer appears immediately in the list.

---

### US-007 — Identify PEP Customers
**As an** Analyst,
**I want to** see which customers are Politically Exposed Persons (PEPs),
**So that** I can apply Enhanced Due Diligence as required by FATF Recommendation 12.

**Acceptance Criteria:**
- PEP customers are visually marked with a badge in the customer list.
- Transactions involving PEP customers trigger the PEP Transaction AML rule.

---

## Epic 3: Transaction Monitoring

### US-008 — Submit a Transaction
**As an** Analyst or Admin,
**I want to** record a financial transaction between two accounts,
**So that** it is stored and automatically monitored for suspicious activity.

**Acceptance Criteria:**
- The form accepts amount, currency, transaction type, originating country, destination country, and optional description.
- On submission, the AML rules engine evaluates the transaction automatically.
- The transaction's risk score and flagged status are immediately visible.

---

### US-009 — View Flagged Transactions
**As an** Analyst,
**I want to** filter transactions to show only flagged ones,
**So that** I can focus my investigation on suspicious activity.

**Acceptance Criteria:**
- A filter toggle shows only flagged transactions.
- Flagged transactions display their risk score highlighted in red.
- Clicking a transaction shows which AML rules were triggered.

---

### US-010 — Monitor Transaction Risk Score
**As an** Analyst,
**I want to** see a numerical risk score for each transaction,
**So that** I can prioritize which transactions to investigate first.

**Acceptance Criteria:**
- Risk scores are displayed on a 0–100 scale.
- Scores are color-coded: 0–39 (green), 40–69 (yellow), 70–100 (red).

---

## Epic 4: AML Rules Engine

### US-011 — View Active AML Rules
**As an** Admin,
**I want to** view all configured AML detection rules,
**So that** I understand what patterns the system is monitoring.

**Acceptance Criteria:**
- Each rule card shows its name, category, threshold, time window, and enabled/disabled status.
- Rules are grouped by category.

---

### US-012 — Enable / Disable a Rule
**As an** Admin,
**I want to** enable or disable individual AML rules,
**So that** I can tune the system based on current compliance requirements.

**Acceptance Criteria:**
- A toggle switch on each rule card enables or disables the rule.
- Disabled rules are grayed out and not evaluated during transaction processing.
- Only Admin users can toggle rules.

---

### US-013 — Create a New AML Rule
**As an** Admin,
**I want to** create a new AML detection rule with custom thresholds,
**So that** the system can detect additional suspicious patterns specific to our risk appetite.

**Acceptance Criteria:**
- The form includes rule name, category (including Micro-Transaction), threshold amount, transaction count, time window, and high-risk countries.
- The new rule is immediately active and applied to future transactions.

---

## Epic 5: Alert Management

### US-014 — View Generated Alerts
**As an** Analyst,
**I want to** see all alerts generated by the AML rules engine,
**So that** I know which transactions require investigation.

**Acceptance Criteria:**
- The alerts table shows alert number, rule name, customer, severity, status, and creation date.
- Alerts are filterable by severity and status.
- CRITICAL alerts are visually prominent.

---

### US-015 — Investigate an Alert
**As an** Analyst,
**I want to** open an alert and view its full details including the rule context,
**So that** I can understand why it was triggered and decide on next steps.

**Acceptance Criteria:**
- The alert detail modal shows the triggered rule, reason, risk score, transaction details, and raw rule context JSON.
- The analyst can update the alert status (e.g., mark as FALSE_POSITIVE or ESCALATED).

---

### US-016 — Create a Case from an Alert
**As an** Analyst,
**I want to** escalate an alert into a formal investigation case,
**So that** the suspicious activity is formally tracked and assigned.

**Acceptance Criteria:**
- A "Create Case" button is available on each alert detail.
- The case is linked to the alert and the associated customer.
- The alert status is updated to ESCALATED upon case creation.

---

## Epic 6: Case Management

### US-017 — View All Cases
**As an** Analyst or Supervisor,
**I want to** view all open investigation cases,
**So that** I can monitor the status of ongoing investigations.

**Acceptance Criteria:**
- Cases are displayed with case number, title, customer, priority, status, and assigned user.
- Summary cards at the top show counts by status (OPEN, UNDER_REVIEW, ESCALATED, CLOSED).
- Clicking a status card filters the list to that status.

---

### US-018 — Add Notes to a Case
**As an** Analyst,
**I want to** add investigation notes to a case,
**So that** I can document my findings and communicate with the team.

**Acceptance Criteria:**
- The case detail shows a chronological notes thread.
- New notes are timestamped and attributed to the user.
- Notes cannot be deleted to preserve the investigation record.

---

### US-019 — File a SAR
**As a** Supervisor,
**I want to** mark a case as having a Suspicious Activity Report filed,
**So that** the regulatory obligation is recorded in the system.

**Acceptance Criteria:**
- Supervisors can toggle "SAR Filed" on a case and enter a SAR reference number.
- The SAR reference and filing status are visible in the case detail.
- Only Supervisors and Admins can file SARs.

---

### US-020 — Close a Case
**As a** Supervisor,
**I want to** close a resolved investigation case,
**So that** the team can focus on open investigations.

**Acceptance Criteria:**
- A status update changes the case to CLOSED.
- An automatic note is added recording who closed the case and when.
- Closed cases remain visible in the case list for audit purposes.

---

## Epic 7: Sanctions Screening

### US-021 — Search the OFAC SDN List
**As an** Analyst,
**I want to** search for a person or entity name against the OFAC Specially Designated Nationals list,
**So that** I can determine if a customer or counterparty is a sanctioned individual.

**Acceptance Criteria:**
- The search form accepts a name query and optional filters for entity type, country, and SDN program.
- Results are returned within 3 seconds.
- Each result shows a match score, match strength badge (STRONG / POSSIBLE / WEAK), aliases, addresses, and programs.

---

### US-022 — Adjust Search Sensitivity
**As an** Analyst,
**I want to** adjust the minimum match score threshold,
**So that** I can control the sensitivity of the sanctions search based on the situation.

**Acceptance Criteria:**
- A slider lets the user set the minimum score (0.60 to 1.00).
- Lowering the threshold returns more (potentially weaker) matches.
- Raising the threshold returns only strong matches.

---

## Epic 8: Dashboard & Analytics

### US-023 — View Compliance KPIs
**As a** Supervisor or Admin,
**I want to** see key compliance metrics on the dashboard,
**So that** I can quickly assess the current state of the AML monitoring program.

**Acceptance Criteria:**
- The dashboard shows: total transactions, flagged transactions, open alerts, and active cases.
- Each KPI card shows a percentage change compared to the previous period.

---

### US-024 — View Transaction Trends
**As a** Supervisor,
**I want to** see a 30-day trend of transaction volumes and alert counts,
**So that** I can identify spikes or unusual patterns over time.

**Acceptance Criteria:**
- A line chart shows daily transaction counts and amounts for the last 30 days.
- A bar chart shows daily alert counts for the last 30 days.

---

### US-025 — View Alert & Case Distribution
**As a** Supervisor,
**I want to** see how alerts and cases are distributed by severity and status,
**So that** I can identify if any category is disproportionately high.

**Acceptance Criteria:**
- A pie chart shows alert distribution by severity (LOW / MEDIUM / HIGH / CRITICAL).
- A pie chart shows case distribution by status (OPEN / UNDER_REVIEW / ESCALATED / CLOSED).

---

## Epic 9: Audit & Compliance

### US-026 — View Audit Log
**As an** Admin,
**I want to** view a complete log of all actions performed in the system,
**So that** I can ensure accountability and investigate any unauthorized activity.

**Acceptance Criteria:**
- The audit log shows the user, action, affected entity, timestamp, and before/after JSON snapshots.
- Entries are color-coded by action type (CREATE = green, UPDATE = yellow, DELETE = red).
- The log is read-only and cannot be modified or deleted.

---

### US-027 — Track Who Changed What
**As an** Admin,
**I want to** see exactly what changed in each audit entry,
**So that** I can trace the history of any record in the system.

**Acceptance Criteria:**
- Each audit entry that involves an update shows the before and after values as formatted JSON.
- The IP address and user agent of the requestor are recorded.
