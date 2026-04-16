# Database Schema — AML Transaction Monitoring System

## Tables Overview

| Table | Description |
|-------|-------------|
| users | System users (Admin, Analyst, Supervisor) |
| customers | Financial institution customers |
| accounts | Customer bank accounts |
| transactions | Financial transactions |
| rules | AML detection rules |
| alerts | Generated AML alerts |
| cases | Investigation cases |
| case_notes | Notes added to cases |
| sanctions_entries | OFAC SDN entities |
| sanctions_aliases | Name aliases for SDN entities |
| sanctions_locations | Addresses for SDN entities |
| sanctions_identifiers | IDs for SDN entities |
| audit_logs | System audit trail |
| blacklist_entries | Internal blacklist |

## Table Definitions

### users
Stores system user accounts with role-based access.
Fields: id, username (unique), email (unique), full_name, password_hash, role (admin/analyst/supervisor), is_active, created_at, last_login

### customers
Stores customer profiles for financial monitoring.
Fields: id, customer_number (unique, format CUS-XXXXXX), full_name, email, phone, date_of_birth, nationality, occupation, annual_income, source_of_funds, risk_level (low/medium/high/critical), pep_status, sanctions_flag, created_at

### accounts
Bank accounts linked to customers.
Fields: id, account_number (unique), customer_id (FK to customers), account_type, currency, balance, is_active

### transactions
Financial transactions that are monitored by the rules engine.
Fields: id, transaction_ref (unique), from_customer_id, to_customer_id, from_account_id, to_account_id, amount, currency, transaction_type, originating_country, destination_country, risk_score, flagged, description, created_at

### rules
Configurable AML detection rules.
Fields: id, name, category (large_transaction/structuring/frequency/velocity/round_amount/high_risk_country/rapid_movement/pep_transaction), description, threshold_amount, threshold_count, time_window_hours, high_risk_countries (JSON), is_active, created_at

### alerts
Auto-generated alerts when AML rules match.
Fields: id, alert_number (unique, format ALT-YYYYMMDD-XXXXX), transaction_id, rule_id, customer_id, severity (low/medium/high/critical), status (open/investigating/false_positive/escalated/closed), reason, details (JSON), risk_score, created_at

### cases
Investigation cases linked to alerts.
Fields: id, case_number (unique), alert_id, customer_id, assigned_to (FK to users), status (open/under_review/escalated/closed), sar_filed, sar_reference, sar_filed_at, created_at

### case_notes
Notes added by analysts during investigation.
Fields: id, case_id (FK to cases), user_id (FK to users), content, created_at

### audit_logs
Full audit trail of all system actions.
Fields: id, user_id, action (create/update/delete/login/logout), entity_type, entity_id, old_value (JSON), new_value (JSON), ip_address, user_agent, created_at

### blacklist_entries
Internal blacklist for blocking suspicious entities.
Fields: id, entry_type (ip/country/entity/email/account), value, reason, severity, is_active, expires_at, created_at
