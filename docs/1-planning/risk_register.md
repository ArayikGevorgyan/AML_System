# Risk Register — AML Transaction Monitoring System

| ID | Risk | Category | Probability | Impact | Score | Mitigation |
|----|------|----------|-------------|--------|-------|------------|
| R-01 | High false positive rate in AML rules causing alert fatigue | Technical | High | Medium | High | Tune rule thresholds; add false_positive status; track false positive rate in reports |
| R-02 | OFAC SDN XML format changes breaking import script | Technical | Low | High | Medium | Version-check XML namespace; monitor OFAC publication updates |
| R-03 | SQLite performance degradation under large transaction volume | Technical | Medium | Medium | Medium | WAL mode enabled; index key columns; batch inserts in scripts |
| R-04 | JWT token compromise leading to unauthorized access | Security | Low | High | Medium | Short token expiry (24h); logout invalidates token; HTTPS in production |
| R-05 | Weak password policy allowing easy account compromise | Security | Medium | High | High | Enforce minimum password complexity; bcrypt hashing; email verification |
| R-06 | SMTP email delivery failures blocking registration | Technical | Medium | Medium | Medium | Dev fallback prints code to console; multiple SMTP providers supported |
| R-07 | Incomplete audit trail missing critical compliance events | Compliance | Low | High | Medium | Audit service called on every create/update/delete action |
| R-08 | Incorrect sanctions match scoring causing missed hits | Compliance | Low | High | Medium | Multi-factor scoring (JW + token overlap + prefix); configurable min score |
| R-09 | Data loss due to SQLite corruption | Technical | Low | High | Medium | WAL mode; regular database backup recommended |
| R-10 | Scope creep delaying delivery | Management | Medium | Medium | Medium | Fixed scope defined in Project Charter; supervisor approval required for changes |
| R-11 | Browser compatibility issues with React UI | Technical | Low | Low | Low | Tested on Chrome/Safari; standard CSS variables used |
| R-12 | Python 3.13 package incompatibilities | Technical | Medium | High | High | Pinned compatible versions in requirements.txt; tested on Python 3.13 |
