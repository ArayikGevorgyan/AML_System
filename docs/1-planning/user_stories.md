# User Stories — AML Transaction Monitoring System

## Epic 1: Authentication and User Management

**US-01** — As a new user, I want to register with my email so that I can access the system with my own credentials.
Acceptance: Email verification code sent; invalid domains rejected; account created on success.

**US-02** — As a user, I want to log in with my username and password so that I can securely access the system.
Acceptance: JWT token issued; redirected to dashboard; invalid credentials show error.

**US-03** — As an admin, I want to see all registered users so that I can manage team access.
Acceptance: User list visible in admin panel with roles and status.

## Epic 2: Customer Management

**US-04** — As an analyst, I want to create a customer profile so that I can track their financial activity.
Acceptance: Customer saved with auto-generated number; risk level, PEP status, sanctions flag set.

**US-05** — As an analyst, I want to search for customers by name so that I can quickly find the right profile.
Acceptance: Real-time search filters the customer table.

**US-06** — As an analyst, I want to see if a customer is a PEP or on the sanctions list so that I can apply enhanced due diligence.
Acceptance: PEP and Sanctioned badges visible on customer row and detail.

## Epic 3: Transaction Monitoring

**US-07** — As an analyst, I want to record a new transaction so that it is monitored for suspicious activity.
Acceptance: Transaction saved; rules engine runs in background; alerts generated if rules match.

**US-08** — As an analyst, I want to see all transactions with their risk scores so that I can identify high-risk activity.
Acceptance: Risk score color-coded; flagged transactions highlighted.

**US-09** — As an analyst, I want to filter transactions by date, amount, and type so that I can investigate specific patterns.
Acceptance: Filter controls on transactions page; table updates in real time.

## Epic 4: AML Rules Engine

**US-10** — As an admin, I want to enable or disable AML detection rules so that I can tune the system.
Acceptance: Toggle on rule card; status changes immediately; audit log records change.

**US-11** — As an admin, I want to create a new AML rule with custom thresholds so that I can add detection for new patterns.
Acceptance: Rule form with all parameters; new rule appears in list and is evaluated on new transactions.

**US-12** — As a supervisor, I want to see which rules are triggering the most alerts so that I can assess rule performance.
Acceptance: Top rules chart on dashboard; rule performance in reports.

## Epic 5: Alert Management

**US-13** — As an analyst, I want to see all open alerts so that I can prioritize my review queue.
Acceptance: Alerts table with severity filter and status filter; sorted by date.

**US-14** — As an analyst, I want to update the status of an alert so that I can track my investigation progress.
Acceptance: Status dropdown in alert detail; update saved; audit log entry created.

**US-15** — As an analyst, I want to create a case from an alert so that I can formally investigate suspicious activity.
Acceptance: Create Case button in alert detail; case created and linked to alert.

**US-16** — As a supervisor, I want critical alerts to be automatically escalated if not reviewed within 48 hours so that nothing is missed.
Acceptance: Escalation engine runs and updates alert status to escalated.

## Epic 6: Case Management

**US-17** — As an analyst, I want to add notes to a case so that I can document my investigation findings.
Acceptance: Notes thread in case detail; timestamp and author shown.

**US-18** — As a supervisor, I want to file a SAR for a confirmed suspicious case so that I can meet regulatory reporting obligations.
Acceptance: SAR filed flag, reference number, and date recorded on case.

**US-19** — As a supervisor, I want to see cases by status so that I can manage the investigation pipeline.
Acceptance: Status filter cards on cases page; click to filter table.

## Epic 7: Sanctions Screening

**US-20** — As an analyst, I want to search a customer name against the OFAC SDN list so that I can check for sanctions exposure.
Acceptance: Search returns results with match score and match strength badge (STRONG/POSSIBLE/WEAK).

**US-21** — As an analyst, I want to filter sanctions results by country and entity type so that I can narrow my search.
Acceptance: Country and type filters on sanctions search form.

## Epic 8: Dashboard and Reporting

**US-22** — As any user, I want to see a dashboard with key compliance metrics so that I can understand the current risk status.
Acceptance: 6 KPI cards, charts for trends and distributions, recent alerts table.

**US-23** — As an admin, I want to export a compliance report so that I can share it with management.
Acceptance: Reporting API returns JSON report with monthly stats, alert breakdown, SAR count.

## Epic 9: Audit and Compliance

**US-24** — As an admin, I want to view the full audit log so that I can review all system activity.
Acceptance: Audit log shows all actions with user, timestamp, and before/after values.

**US-25** — As any user, I want the system to remember my dark/light mode preference so that I do not have to set it every time.
Acceptance: Theme preference saved to localStorage; persists on refresh and restart.
