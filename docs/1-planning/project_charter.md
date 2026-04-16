# Project Charter — AML Transaction Monitoring System

## 1. Project Overview

| Field | Details |
|-------|---------|
| Project Name | AML Transaction Monitoring System |
| Project Type | University Capstone Project |
| Version | 1.0 |
| Date | March 2026 |

## 2. Objectives
- Build a full-stack AML compliance platform with Python FastAPI backend and React frontend
- Implement 8 AML detection rules based on real regulatory guidance (BSA, FATF, FinCEN)
- Integrate OFAC SDN sanctions screening with fuzzy name matching
- Support three user roles: Admin, Analyst, Supervisor
- Achieve minimum 75% backend code coverage in the project

## 3. Scope

### In Scope
- User authentication and registration with email verification
- Customer and account management
- Transaction creation and monitoring
- AML rules engine with 8 detection typologies
- Alert generation and management
- Case management with notes and SAR filing
- OFAC sanctions screening
- Risk scoring engine
- Blacklist management
- Alert escalation engine
- Compliance reporting API
- Audit logging
- Dashboard with KPIs and charts
- Dark/Light mode UI

### Out of Scope
- Real payment processing integration
- Mobile application
- Machine learning-based detection
- Multi-currency conversion

## 4. Stakeholders

| Role | Responsibility |
|------|---------------|
| Developer | Full system design, implementation, and testing |
| University Supervisor | Project oversight and grading |
| End Users (simulated) | Admin, Analyst, Supervisor roles |

## 5. Deliverables
- Fully functional AML web application
- Source code on GitHub
- Complete documentation
- Working demo with seeded data

## 6. Timeline

| Phase | Duration |
|-------|---------|
| Requirements and Design | Week 1 |
| Backend Development | Weeks 2-4 |
| Frontend Development | Week 5 |
| Testing and Debugging | Week 6 |
| Documentation | Week 7 |

## 7. Constraints
- Must use Python FastAPI + SQLite + React as specified
- Minimum 75% backend code share
- Must use real OFAC SDN Advanced XML data

## 8. Authority
Project decisions are made by the developer in alignment with university supervisor requirements.
