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
- [Quick Start](#quick-start)
- [Demo Credentials](#demo-credentials)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)

---

## Overview

This system simulates a real-world AML transaction monitoring platform used by financial institutions to detect, investigate, and report suspicious financial activity. It implements rule-based detection, fuzzy sanctions screening against the official OFAC SDN list, alert generation, case management, and a full audit trail.

---

## Features

- **JWT Authentication** with role-based access control (Admin / Analyst / Supervisor)
- **User Registration** with email verification code
- **Customer & Account Management** with risk profiling and PEP flagging
- **Transaction Monitoring** with automated risk scoring
- **8-Rule AML Detection Engine** based on BSA, FATF, and FinCEN typologies
- **Micro-Transaction Detection** — repeated small amounts at high frequency
- **Alert Generation** with severity levels (LOW / MEDIUM / HIGH / CRITICAL)
- **Case Management** with investigation workflow and SAR filing support
- **OFAC Sanctions Screening** using Jaro-Winkler + Soundex fuzzy matching
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
| Sanctions Data | OFAC SDN Advanced XML (official) |
| Fuzzy Matching | jellyfish (Jaro-Winkler + Soundex), dnspython |
| XML Parsing | lxml iterparse (streaming, memory-efficient) |
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
    │  SQLite DB  │ │ Rules Engine│  │   Sanctions │
    │  (aml.db)   │ │  (8+ rules) │  │   Screener  │
    └─────────────┘ └─────────────┘  └─────────────┘
```

---

## Modules

| Module | Description |
|--------|-------------|
| **Authentication** | JWT login/logout, email verification on registration, 3 roles |
| **Customers** | Customer profiles, risk levels (LOW/MEDIUM/HIGH), PEP status, sanctions flag |
| **Accounts** | Bank accounts linked to customers with auto-generated account numbers |
| **Transactions** | Create and monitor transactions; automated risk scoring on submission |
| **Rules Engine** | 8+ configurable AML detection rules with thresholds and time windows |
| **Alerts** | Auto-generated from rule matches; severity classification; status workflow |
| **Cases** | Investigation management, notes thread, status tracking, SAR filing |
| **Sanctions Screening** | Fuzzy name search against real OFAC SDN list (2.6M-line XML) |
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

The sanctions screener uses a multi-stage pipeline to efficiently search the 2.6-million-line OFAC SDN Advanced XML:

```
Input Name
    │
    ▼
Normalize (lowercase, remove noise words, unicode-normalize)
    │
    ▼
Soundex Pre-filter (phonetic bucketing to reduce candidate pool)
    │
    ▼
Composite Score:
    Jaro-Winkler Similarity  × 0.70
  + Token Overlap Score      × 0.20
  + Prefix Bonus             × 0.10
    │
    ▼
Filter by min_score threshold → Rank → Return Results
```

**Match strength:** STRONG (≥0.85) | POSSIBLE (≥0.70) | WEAK (≥0.60)

---

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- OFAC SDN Advanced XML file

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

# Import OFAC SDN sanctions list (takes a few minutes for 2.6M lines)
python scripts/import_sanctions.py

# Configure email (optional — codes print to terminal if not configured)
cp .env.example .env
# Edit .env with your SMTP credentials (Brevo recommended)

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
| `POST /api/v1/sanctions/search` | Fuzzy search OFAC SDN list |
| `GET /api/v1/audit` | Retrieve audit log entries |

---

## Project Structure

```
AML/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings and environment variables
│   ├── database.py              # SQLAlchemy engine and session
│   ├── requirements.txt
│   ├── .env.example
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── customer.py
│   │   ├── account.py
│   │   ├── transaction.py
│   │   ├── rule.py
│   │   ├── alert.py
│   │   ├── case.py
│   │   ├── sanctions.py
│   │   └── audit_log.py
│   ├── routers/                 # FastAPI route handlers
│   │   ├── auth.py
│   │   ├── customers.py
│   │   ├── transactions.py
│   │   ├── rules.py
│   │   ├── alerts.py
│   │   ├── cases.py
│   │   ├── sanctions.py
│   │   ├── dashboard.py
│   │   └── audit.py
│   ├── services/                # Business logic
│   │   ├── rules_engine.py      # AML detection engine
│   │   ├── sanctions_screener.py
│   │   ├── alert_service.py
│   │   ├── case_service.py
│   │   ├── transaction_service.py
│   │   ├── customer_service.py
│   │   ├── dashboard_service.py
│   │   ├── auth_service.py
│   │   ├── audit_service.py
│   │   └── email_service.py
│   ├── core/
│   │   ├── security.py          # JWT and bcrypt
│   │   ├── dependencies.py      # FastAPI dependencies / RBAC
│   │   └── enums.py
│   └── scripts/
│       ├── seed_data.py         # Demo data seeder
│       └── import_sanctions.py  # OFAC XML importer
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── App.js
│       ├── index.css            # Global dark/light theme variables
│       ├── api/
│       │   └── client.js        # Axios instance with JWT interceptor
│       ├── context/
│       │   ├── AuthContext.js
│       │   └── ThemeContext.js  # Dark/light mode
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
│           ├── Sanctions.js
│           ├── Rules.js
│           └── Audit.js
│
└── docs/
    ├── REQUIREMENTS.md
    └── USER_STORIES.md
```
