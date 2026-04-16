# User Manual — AML Transaction Monitoring System

## 1. Getting Started

### Login
Open http://localhost:3000 in your browser.
Enter your username and password and click Login.

### Register (New Users)
Click "Don't have an account? Register" on the login page.
Enter your email — a 6-digit verification code will be sent to it.
Enter the code, fill in your details, choose a role, and click Register.

## 2. Dashboard
The dashboard gives a real-time overview of system compliance status.

| Card | Description |
|------|-------------|
| Open Alerts | Total unresolved alerts with high/critical count |
| Transactions Today | Number of transactions processed today |
| Volume Today | Total transaction amount today |
| Open Cases | Active investigation cases |
| High-Risk Customers | Customers with HIGH or CRITICAL risk level |
| Sanctions Checks | Number of sanctions searches performed today |

Charts available: 30-day transaction volume trend, alerts by severity, cases by status, top triggered rules.

## 3. Customers
View customers by navigating to Customers in the sidebar.
Use the search box to filter by name.
Click Add Customer to add a new profile.
PEP badge means the customer is a Politically Exposed Person.
Sanctioned badge means the customer is on the internal sanctions list.

## 4. Transactions
Navigate to Transactions to see all recorded transactions.
Click New Transaction to record a new one.
Risk score is color-coded: green for low risk, red for high risk.
A flagged indicator means AML rules were triggered for that transaction.

## 5. Alerts
Navigate to Alerts to see all generated alerts.
Use the Severity and Status dropdowns to filter.
Click an alert to open the detail view showing rule context and risk score.
Update the status using the dropdown and click Update Status.
Click Create Case to open a formal investigation case.

## 6. Cases
Navigate to Cases to see all investigation cases.
Click the colored status cards at the top to filter by status.
Click any row to see case details and the notes thread.
Type in the notes field and click Add Note to document findings.
Supervisors can click File SAR and enter a SAR reference number.

## 7. Sanctions Search
Navigate to Sanctions Search.
Enter a name to search against the OFAC SDN list.
Optional filters: Entity Type, Country, Program, Minimum Score slider.

Results are ranked by confidence:

| Badge | Score | Meaning |
|-------|-------|---------|
| STRONG | 0.85 or above | Very likely match — investigate immediately |
| POSSIBLE | 0.70 to 0.84 | Possible match — review carefully |
| WEAK | Below 0.70 | Low confidence — likely not a match |

## 8. AML Rules
Navigate to AML Rules to see all detection rules.
Click the toggle on any rule card to enable or disable it.
Click New Rule to add a custom rule with your own thresholds.

## 9. Audit Logs (Admin Only)
Navigate to Audit Logs to see all system actions.
Filter by action type using the dropdown.
Each entry shows the user, action, entity affected, timestamp, and before/after values.

## 10. Theme Toggle
Click the sun or moon icon in the top bar to switch between dark and light mode.
Your preference is saved automatically and persists between sessions.

## 11. Notification Bell
Click the bell icon in the top bar to see the 5 most recent open alerts.
Click any alert in the dropdown to navigate to the Alerts page.
Click "View all alerts" to see the full alerts list.
