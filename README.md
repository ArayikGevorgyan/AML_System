# AML Transaction Monitoring System

> Anti-Money Laundering (AML) platform built as a university capstone project, inspired by real-world systems such as NICE Actimize, Oracle FCCM, and the OFAC Sanctions Search Tool.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Modules](#modules)
- [AML Detection Rules](#aml-detection-rules)
- [Sanctions Screening Algorithm](#sanctions-screening-algorithm)
- [ML Models](#ml-models)
- [Quick Start](#quick-start)
- [Demo Credentials](#demo-credentials)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)

---

## Overview

This system simulates a real-world AML transaction monitoring platform used by financial institutions to detect, investigate, and report suspicious financial activity. It implements rule-based detection, fuzzy sanctions screening against the official OFAC SDN list and UN Consolidated List, alert generation, case management, ML-based anomaly detection, and a full audit trail.

---

## Features

- **JWT Authentication** with role-based access control (Admin / Analyst / Supervisor)
- **User Registration** with email verification code
- **Customer & Account Management** with risk profiling and PEP flagging
- **Transaction Monitoring** with automated risk scoring
- **9-Rule AML Detection Engine** based on BSA, FATF, and FinCEN typologies
- **Micro-Transaction Detection** — repeated small amounts at high frequency
- **Alert Generation** with severity levels (LOW / MEDIUM / HIGH / CRITICAL)
- **Case Management** with investigation workflow and SAR filing support
- **OFAC SDN + UN Consolidated List Screening** using token-recall Jaro-Winkler fuzzy matching
- **Searchable Dropdowns** for Type, Program (86 programs), and Country (196 countries) filters
- **ML Anomaly Detection** using Isolation Forest per-customer behavioural models
- **ML Risk Prediction** using Gradient Boosting — predicts SAR probability in next 90 days
- **Bulk Screening CLI** — screen a CSV of names/IDs against the sanctions database
- **Health Check CLI** — system-wide status check with exit codes for monitoring
- **Compliance Report Generator** — text and CSV reports for given date ranges
- **Interactive Dashboard** with KPIs, charts, and real-time statistics
- **Full Audit Trail** for all system actions
- **Dark / Light Mode** toggle with persistent preference

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, React Router v6, Recharts, React Icons, Axios |
| Backend | Python 3.13, FastAPI, SQLAlchemy ORM, Pydantic v2 |
| Database | SQLite (WAL mode, foreign keys enabled) |
| Authentication | JWT (python-jose), bcrypt password hashing |
| Sanctions Data | OFAC SDN Advanced XML + UN Consolidated List XML |
| Fuzzy Matching | jellyfish (Jaro-Winkler), SQL ILIKE substring pre-filter |
| XML Parsing | lxml iterparse (streaming, memory-efficient) |
| ML / Statistics | scikit-learn, numpy (Isolation Forest, Gradient Boosting) |
| Email | SMTP via Brevo (or dev fallback to terminal) |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   React Frontend (Port 3000)            │
│   Dashboard │ Customers │ Transactions │ Alerts │ Cases │
│   Sanctions │ Rules │ Audit │ Login │ Register          │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP/REST (Axios + JWT)
┌──────────────────────────▼──────────────────────────────┐
│                  FastAPI Backend (Port 8000)            │
│  /api/v1/auth │ /customers │ /transactions │ /alerts    │
│  /cases │ /rules │ /sanctions │ /dashboard │ /audit     │
└──────────┬───────────────┬────────────────┬─────────────┘
           │               │                │
    ┌──────▼──────┐ ┌──────▼──────┐  ┌──────▼──────┐
    │  SQLite DB  │ │ Rules Engine│  │  Sanctions  │
    │  (aml.db)   │ │  (9+ rules) │  │  Screener   │
    └─────────────┘ └─────────────┘  └──────┬──────┘
                                            │
                                     ┌──────▼──────┐
                                     │  OFAC SDN   │
                                     │  + UN List  │
                                     └─────────────┘
```

---

## Modules

| Module | Description |
|--------|-------------|
| **Authentication** | JWT login/logout, email verification on registration, 3 roles |
| **Customers** | Customer profiles, risk levels (LOW/MEDIUM/HIGH/CRITICAL), PEP status, sanctions flag |
| **Accounts** | Bank accounts linked to customers with auto-generated account numbers |
| **Transactions** | Create and monitor transactions; automated risk scoring on submission |
| **Rules Engine** | 9+ configurable AML detection rules with thresholds and time windows |
| **Alerts** | Auto-generated from rule matches; severity classification; status workflow |
| **Cases** | Investigation management, notes thread, status tracking, SAR filing |
| **Sanctions Screening** | Fuzzy name search against OFAC SDN + UN Consolidated List |
| **Blacklist** | Custom blacklist/whitelist for IPs, countries, entities, emails, accounts |
| **Risk Scoring** | Composite risk score (profile + transaction behaviour + alert history) |
| **ML Models** | Isolation Forest anomaly detection + Gradient Boosting SAR prediction |
| **Analysis** | Transaction trends, risk distribution, sanctions statistics |
| **Dashboard** | KPI cards, trend charts, alert distribution, case statistics |
| **Audit Logs** | Complete immutable audit trail with before/after JSON snapshots |

---

## AML Detection Rules

All rules are based on official regulatory guidance from the **Bank Secrecy Act (BSA)**, **FATF Recommendations**, and **FinCEN typologies**.

| # | Rule | Regulatory Basis | Description |
|---|------|-----------------|-------------|
| 1 | **Large Transaction** | BSA / 31 USC §5313 | Single transaction exceeds $10,000 reporting threshold |
| 2 | **Structuring (Smurfing)** | 31 USC §5324 | Multiple transactions just below threshold to avoid CTR reporting |
| 3 | **High Frequency** | FATF Rec. 20 | Unusually high number of transactions within 24 hours |
| 4 | **High Velocity** | FinCEN Advisory | Large cumulative amount moved within a time window |
| 5 | **High-Risk Country** | FATF / OFAC | Transaction involving OFAC-listed or FATF high-risk jurisdiction |
| 6 | **Rapid Movement** | FinCEN Pass-Through | Funds received and sent out within hours (layering indicator) |
| 7 | **Round Amount** | FATF Guidance | Suspiciously round transaction amounts (e.g. $5,000.00) |
| 8 | **PEP Transaction** | FATF Rec. 12 | Transaction involving a Politically Exposed Person |
| 9 | **Micro-Transaction** | FinCEN Guidance | Repeated small amounts at high frequency (account testing indicator) |

---

## Sanctions Screening Algorithm

The sanctions screener uses a multi-stage pipeline to search the OFAC SDN Advanced XML and UN Consolidated List. Results are displayed one row per alias — matching OFAC's official display model.

```
Input Name
    │
    ▼
Normalize (lowercase, unicode→ASCII, remove honorifics, keep Arabic particles)
    │
    ▼
SQL ILIKE Substring Pre-filter (candidate retrieval — fast DB-level filter)
    │
    ▼
Composite Score per alias:
    Token Recall (per-token best Jaro-Winkler)  × 0.60
  + Full-string Jaro-Winkler                   × 0.25
  + Token Jaccard Overlap                      × 0.15
    │
    ▼
Exact token subset → Score 100 (matches OFAC "Min Score = 100" rule)
    │
    ▼
Filter by min_score → Sort by score desc → Return Results
```

**Match strength:** EXACT (100) | STRONG (≥85) | POSSIBLE (≥70) | WEAK (<70)

**Supported lists:**

| List | Source | Entries |
|------|--------|---------|
| OFAC SDN | sdn_advanced.xml (official OFAC) | ~18,000+ |
| UN SC List | consolidatedLegacyByNAME.xml (UN Security Council) | ~1,000+ |

---

## ML Models

### Anomaly Detector (`ml/anomaly_detector.py`)
- **Algorithm:** Isolation Forest (unsupervised)
- **Purpose:** Detects statistically unusual transactions for a specific customer based on their own historical behaviour — catches novel fraud patterns that no rule covers
- **Features:** log(amount), hour of day, day of week, is_international, is_round_amount, transaction type, channel
- **Output:** anomaly_score (0–100), is_anomaly (bool), reason

### Customer Risk Predictor (`ml/risk_model.py`)
- **Algorithm:** Gradient Boosting Classifier (sklearn)
- **Purpose:** Predicts probability that a customer will generate a SAR in the next 90 days
- **Features:** 14 features including transaction velocity, flag ratio, alert severity score, PEP/sanctions status, country risk, account age
- **Output:** sar_probability (0–1), risk_band, top_factors

### Feature Engineering (`ml/feature_engineering.py`)
Centralised pipeline extracting 30+ features per customer across 5 groups: amount statistics, velocity windows, temporal patterns, geographic risk, and alert history.

### Model Evaluator (`ml/model_evaluator.py`)
Evaluation suite with precision/recall/F1/ROC-AUC, confusion matrix, threshold analysis, K-fold cross-validation, and side-by-side model comparison. Recall is weighted as the most important metric for AML.

---

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- OFAC SDN Advanced XML file (`sdn_advanced.xml`)
- UN Consolidated List XML file (`consolidatedLegacyByNAME.xml`) *(optional)*

### 1. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Seed the database (users, rules, customers, transactions)
python scripts/seed_data.py

# Import OFAC SDN sanctions list
python scripts/import_sanctions.py

# Import UN Consolidated List (optional)
python scripts/import_un_sanctions.py

# Configure email (optional — codes print to terminal if not configured)
cp .env.example .env
# Edit .env with your SMTP credentials

# Start the API server
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm start
```

Open `http://localhost:3000` in your browser.

### 3. CLI Tools

```bash
# Bulk screen a CSV of names against sanctions lists
python scripts/bulk_screen.py --input customers.csv --output results.csv

# System health check
python scripts/health_check.py

# Generate compliance report (last 30 days)
python scripts/generate_report.py --days 30 --format text

# Train ML risk model
python ml/train.py
```

### 4. Run Tests

```bash
cd backend
pytest tests/ -v
```

---

## Demo Credentials

| Username | Password | Role |
|----------|----------|------|
| `admin` | `Admin@123` | Admin |
| `ArayikAnalyst` | `Analyst@123` | Analyst |
| `ArayikSupervisor` | `Super@123` | Supervisor |

---

## API Documentation

Interactive Swagger UI available at: `http://localhost:8000/docs`

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/auth/login` | Authenticate and receive JWT token |
| `POST /api/v1/auth/send-verification` | Send email verification code |
| `POST /api/v1/auth/register` | Register new user account |
| `GET /api/v1/dashboard` | Fetch all dashboard KPIs and charts |
| `GET /api/v1/customers` | List all customers |
| `POST /api/v1/transactions` | Create transaction (triggers rules engine) |
| `GET /api/v1/alerts` | List alerts with filters |
| `POST /api/v1/sanctions/search` | Fuzzy search OFAC SDN + UN list |
| `GET /api/v1/sanctions/stats` | Sanctions database statistics |
| `GET /api/v1/audit` | Retrieve audit log entries |

---

## Project Structure

```
AML/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings and environment variables
│   ├── database.py                # SQLAlchemy engine and session
│   ├── requirements.txt
│   ├── .env.example
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── customer.py
│   │   ├── account.py
│   │   ├── transaction.py
│   │   ├── rule.py
│   │   ├── alert.py
│   │   ├── case.py
│   │   ├── sanctions.py
│   │   ├── blacklist.py
│   │   └── audit_log.py
│   ├── routers/                   # FastAPI route handlers
│   │   ├── auth.py
│   │   ├── customers.py
│   │   ├── transactions.py
│   │   ├── rules.py
│   │   ├── alerts.py
│   │   ├── cases.py
│   │   ├── sanctions.py
│   │   ├── blacklist.py
│   │   ├── dashboard.py
│   │   ├── reporting.py
│   │   ├── risk_scoring.py
│   │   └── audit.py
│   ├── services/                  # Business logic
│   │   ├── rules_engine.py        # AML detection engine (9 rules)
│   │   ├── sanctions_screener.py  # Jaro-Winkler fuzzy screener
│   │   ├── alert_service.py
│   │   ├── case_service.py
│   │   ├── transaction_service.py
│   │   ├── customer_service.py
│   │   ├── risk_scoring_service.py
│   │   ├── blacklist_service.py
│   │   ├── dashboard_service.py
│   │   ├── auth_service.py
│   │   ├── audit_service.py
│   │   ├── escalation_service.py
│   │   ├── reporting_service.py
│   │   ├── predictive_risk_service.py
│   │   └── email_service.py
│   ├── ml/                        # Machine learning models
│   │   ├── anomaly_detector.py    # Isolation Forest per-customer
│   │   ├── risk_model.py          # Gradient Boosting SAR predictor
│   │   ├── feature_engineering.py # Centralised feature pipeline
│   │   ├── model_evaluator.py     # Metrics, threshold analysis
│   │   └── train.py               # Training script
│   ├── analysis/                  # Data analysis modules
│   │   ├── transaction_analysis.py
│   │   ├── risk_distribution.py
│   │   └── sanctions_stats.py
│   ├── tests/                     # Unit tests (pytest)
│   │   ├── test_sanctions_screener.py
│   │   ├── test_risk_scoring.py
│   │   ├── test_rules_engine.py
│   │   ├── test_auth_service.py
│   │   ├── test_alert_service.py
│   │   ├── test_transaction_service.py
│   │   └── test_blacklist_service.py
│   ├── core/
│   │   ├── security.py            # JWT and bcrypt
│   │   ├── dependencies.py        # FastAPI dependencies / RBAC
│   │   └── enums.py
│   └── scripts/
│       ├── seed_data.py           # Demo data seeder
│       ├── import_sanctions.py    # OFAC XML importer
│       ├── import_un_sanctions.py # UN Consolidated List importer
│       ├── bulk_screen.py         # CLI: bulk sanctions screening
│       ├── health_check.py        # CLI: system health check
│       └── generate_report.py     # CLI: compliance report generator
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── App.js
│       ├── index.css              # Global dark/light theme variables
│       ├── api/
│       │   └── client.js          # Axios instance with JWT interceptor
│       ├── context/
│       │   ├── AuthContext.js
│       │   └── ThemeContext.js    # Dark/light mode
│       ├── components/layout/
│       │   ├── Layout.js
│       │   ├── Sidebar.js
│       │   └── Topbar.js
│       └── pages/
│           ├── Login.js
│           ├── Register.js
│           ├── Dashboard.js
│           ├── Customers.js
│           ├── Transactions.js
│           ├── Alerts.js
│           ├── Cases.js
│           ├── Sanctions.js       # Searchable Type/Program/Country dropdowns
│           ├── Rules.js
│           └── Audit.js
│
└── docs/
    ├── REQUIREMENTS.md
    └── USER_STORIES.md
```
