# Deviations from SRS / SAD / Test Plan

This file records every place where the current BBMS implementation differs from the submitted Team 9 documents (SRS v1.0, SAD v1.0, Test Plan v1.0, Project Proposal). It is kept for the final demo so evaluators can see what was changed, added or postponed, and why. Last updated: 2026-10-20.

Scope of this review: code on the current branch (BB-01 project skeleton and BB-03/BB-04 authentication). Only `users` has real logic; the other six apps are empty scaffolds. `backlog.csv` and `.github/workflows` do not exist in the repo, so backlog mapping is limited to BB-01, BB-03 and BB-04. Reasons are only filled in where they are visible in the code or task descriptions; everything else says "To be confirmed by team".

## Summary

| Type | Count |
|---|---|
| CHANGED | 9 |
| ADDED | 3 |
| DROPPED | 0 |
| DEFERRED | 4 |
| **Total** | **16** |

Most important deviations:
- Frontend is server-rendered Django templates, not HTML/CSS/JS or React talking to the REST API (DEV-02).
- Registration works without OTP verification and without admin approval, and STAFF/ADMIN cannot self-register (DEV-03, DEV-04, DEV-05).
- Configurable rules (BR-3) are environment variables for now, not administrator-editable settings (DEV-06).
- Four SAD modules (Search & Matching, Administration, Certificates, Audit Logging) have no dedicated app yet (DEV-07).
- No CI pipeline, no HTTPS enforcement, and the Test Plan's Postman/JMeter tooling is not set up (DEV-13, DEV-14, DEV-16).

## Deviation log

| ID | Type | Document & section | Requirement ID | What the document says | What we implemented | Reason | Impact | Backlog item |
|---|---|---|---|---|---|---|---|---|
| DEV-01 | CHANGED (process) | Project plan / backlog deadline | n/a | Backlog was due 12 Oct 2026. | Backlog was created on 20 Oct 2026, before Sprint-1 implementation started. | To be confirmed by team | Late planning; backlog dates and traceability start later than planned. | n/a |
| DEV-02 | CHANGED | SAD 3.6 Technology Stack; SAD 1.1 | n/a | Frontend is HTML, CSS, JavaScript / React, communicating with the backend through REST APIs. | Frontend is server-rendered Django templates with session login (`templates/`); no React or custom JavaScript. REST/JWT APIs exist in parallel. | To be confirmed by team | Low; SAD lists plain HTML/CSS as an option, but the frontend does not consume the REST API. | BB-03 |
| DEV-03 | CHANGED | SRS 5.1.3 FR1 | FR1 | Donors, blood bank staff, hospital staff and administrators can register and log in. | Only DONOR and HOSPITAL can self-register (API and web form). STAFF and ADMIN can log in but must be created by an administrator. | Rule given in the BB-03 task description; further rationale to be confirmed by team. | Low; staff/admin account creation depends on Django admin until the Admin module (FR26) exists. | BB-03 |
| DEV-04 | DEFERRED | SRS 4 use-case "Register always includes mobile/email verification"; SAD 4.2 Donor Registration sequence | FR3 | Registration includes an OTP sent via the notification service and verified before the profile is created. | Registration creates the account immediately; no OTP, no email/SMS verification. | OTP and notifications not built yet; reason for ordering to be confirmed by team. | Medium; accounts are unverified, and the sequence diagram does not match behaviour. | To be confirmed by team |
| DEV-05 | DEFERRED | SRS 5.9.2, FR27 | FR27 | Administrators approve and verify donor and hospital registrations. | Self-registered donors and hospitals are active immediately and web registration logs them in automatically. | Admin approval not built yet; to be confirmed by team. | Medium; no verification step before access. | To be confirmed by team |
| DEV-06 | CHANGED | SRS 2.5, BR-3; SAD 3.1 | BR-3 | Minimum donor eligibility interval, thresholds, roles and notification channels are configurable by authorized administrators. | `BBMS_MIN_DONATION_INTERVAL_DAYS` (default 90) is read from an environment variable in `config/settings.py`; it is not yet used by any feature and cannot be changed by an administrator at runtime. | Environment-variable configuration was specified in the BB-01 task; admin-editable configuration to be confirmed by team. | Medium; BR-3 is not met until an admin-editable configuration exists. | BB-01 |
| DEV-07 | CHANGED | SAD 3.4 Component Descriptions; SAD 4.1 Design Overview | FR24-FR29 | 11 modules including Search & Matching, Administration, Certificate Generation and Audit Logging (SAD 3.4 also lists Authentication & RBAC separately). | 7 Django apps: users, donors, inventory, bloodrequests, camps, notifications, reports. The four modules above have no dedicated app, and the README FR table does not assign FR24-FR27 or FR29 to any app. Authentication/RBAC lives in `users`. | The seven apps match SRS NFR15; ownership of the remaining modules to be confirmed by team. | Medium; owners and locations for search, admin, certificates and audit logging are undecided. | To be confirmed by team |
| DEV-08 | CHANGED | SRS NFR15 | NFR15 | Separate modules for users, donors, inventory, requests, notifications and reporting. | The requests module is named `bloodrequests` (also adds `camps`). | Avoids a clash with the `requests` library (stated in the BB-01 task). | Low; naming only. | BB-01 |
| DEV-09 | CHANGED | SAD 3.5 Architecture Pattern | NFR15 | Layers: Presentation, API/Controller, Business Logic, Data Access, Database. | No separate business-logic or data-access layer exists; views call serializers and models directly (`users/views.py`, `users/serializers.py`). | Too little logic so far to need a service layer; to be confirmed by team. | Low now; grows with the blood-safety rules (compatibility, reservation). | To be confirmed by team |
| DEV-10 | ADDED | SAD 3.6 Data Store (PostgreSQL) | n/a | PostgreSQL is the database. | When `DB_HOST` is not set, settings fall back to SQLite (`db.sqlite3`); PostgreSQL is used with Docker or when `DB_HOST` is set. Tests run on SQLite. | README documents venv + SQLite for local Windows development. | Low; PostgreSQL-specific behaviour (e.g. concurrency, NFR21) is not exercised in local tests. | BB-01 |
| DEV-11 | ADDED | SAD 4.3 API Design (only `/api/blood/availability` and `/api/blood-requests` defined) | FR1, NFR7 | No authentication or health APIs are specified. | Added `POST /api/auth/register/`, `POST /api/auth/login/`, `POST /api/auth/refresh/`, `GET /api/auth/me/` (JWT via simplejwt) and `GET /api/health/`. Web pages `/register/`, `/login/`, `/logout/`, `/dashboard/<role>/` and a landing page `/` were also added. | Needed to implement FR1/NFR6/NFR7; endpoint shapes are not in the SAD. | Low; the SAD API section should be updated with these endpoints. | BB-01, BB-03, BB-04 |
| DEV-12 | ADDED | SAD 3.4 / 4.5 Admin Dashboard and Admin Module | FR26 | Admin console is a role-specific dashboard. | Django's built-in `/admin/` is registered for the custom User (role in list and filter) and is the only place to create STAFF/ADMIN users. `/dashboard/admin/` is a placeholder. | Registering the User in admin was part of the BB-01 task. | Low; interim admin tooling. | BB-01 |
| DEV-13 | DEFERRED | Proposal "Plan of work" weeks 2-4 (shared repo and CI); SRS NFR17 | NFR17 | Automated build/test/deployment practices where applicable; CI set up in weeks 2-4. | No CI configuration exists (`.github/workflows` is absent); tests run locally only. | To be confirmed by team | Medium; no automated regression run on pull requests. | To be confirmed by team |
| DEV-14 | DEFERRED | SRS NFR7; SAD 3.9 Security Architecture | NFR7, NFR5 | All communication over HTTPS; sensitive data protected with encryption. | No HTTPS or secure-cookie settings in `config/settings.py`; `DJANGO_DEBUG` defaults to True and `DJANGO_SECRET_KEY` has an insecure development fallback. Passwords are hashed (Django default); no field-level encryption of medical data. | Deployment hardening not done yet; to be confirmed by team. | Medium; must be fixed before any real deployment. | To be confirmed by team |
| DEV-15 | CHANGED | SAD 3.6 Deployment; SRS NFR24 | NFR24 | Docker-compatible deployment. | The Dockerfile runs `migrate` then Django's `runserver`; `gunicorn` is in `requirements.txt` but unused. The Docker build has not been run or tested. | Simplicity for the skeleton; to be confirmed by team. | Low; not production-grade. | BB-01 |
| DEV-16 | CHANGED | Test Plan section 5 Test Automation Strategy | n/a | API regression tests with Postman/Newman, UI smoke tests, JMeter load tests. | Automated tests use Django's test runner and DRF `APIClient` (`users/tests.py`, 17 tests). No Postman collection, UI smoke tests or JMeter scripts exist. | To be confirmed by team | Low now; performance (NFR1/NFR2) and concurrency tests still have no tooling. | To be confirmed by team |

## Not yet implemented (planned)

`backlog.csv` is not in the repo, so sprint and backlog numbers are not known and are marked "To be confirmed". Implemented so far: FR1 (with DEV-03/04/05), NFR6 and NFR7 (JWT/session only), NFR17 (version control only), password hashing part of NFR5.

| Requirement ID | Description | Planned sprint/backlog item |
|---|---|---|
| FR2 | Profile management (personal, blood group, medical, contact info) | To be confirmed by team |
| FR3 | Password reset and OTP verification | To be confirmed by team |
| FR4-FR7 | Donor registration/eligibility, donation history, next eligible date and reminders | To be confirmed by team |
| FR8-FR11, FR30, FR33, FR34 | Inventory: units, expiry flagging, stock view, low-stock alerts, traceability, disposal, filter/sort | To be confirmed by team |
| FR12-FR16, FR31, FR32, FR35 | Blood search, requests, approval, cross-bank search, compatibility, reservation, status, validation | To be confirmed by team |
| FR17-FR19 | Donation camps and inventory update after a camp | To be confirmed by team |
| FR20, FR21 | SMS/email notifications and emergency broadcasts | To be confirmed by team |
| FR22, FR23 | Reports and admin dashboard with charts | To be confirmed by team |
| FR24, FR25 | Donor and nearby blood-bank/hospital search | To be confirmed by team |
| FR26-FR28 | Admin management, registration approval, audit logs | To be confirmed by team |
| FR29 | Donation certificate | To be confirmed by team |
| NFR1, NFR2 | Search response time; concurrent access | To be confirmed by team |
| NFR3, NFR4, NFR9-NFR11 | Scalability, availability, backups, failover | To be confirmed by team |
| NFR13, NFR16, NFR18, NFR19 | Multilingual content, API documentation, hospital API integration, SMS/email gateway | To be confirmed by team |
| NFR20-NFR22 | No duplicate allocation, transactional consistency, audit logs | To be confirmed by team |
| SAFETY-1 to SAFETY-4 | Compatibility check, expiry block, duplicate allocation block, recovery | To be confirmed by team |
| BR-1, BR-2 | Compatibility rule; donor interval rule | To be confirmed by team |
| SAD 4.4 | Logging of login/security events, donations, requests; monitoring | To be confirmed by team |
| SAD 4.5 | Role dashboard content (current dashboards are placeholders showing name and role) | To be confirmed by team |

## Test Plan differences

- **Planned test case IDs not automated:** TC-INV-01 to TC-INV-08, TC-REQ-05, TC-REQ-07, TC-PERF-01/02, TC-SEC-01 to TC-SEC-04, TC-DATA-01/02, TC-AUD-01 and TC-SAF-01 to TC-SAF-04 have no matching code, because the features they test are not built yet. Appendix A cases (TC-REQ-05 compatibility, TC-INV-04 expiry, TC-DATA-01 concurrent allocation) are also not automated.
- **Automated now:** 17 tests in `users/tests.py` (health, home page, default role, hashed password, API registration/role restriction/weak password/login/refresh/wrong password/`me`, dashboard redirects and 403, web registration). They partly cover FR1, NFR5, NFR6 and NFR7. They are not labelled with Test Plan IDs, and the Test Plan does not define TC-SEC-01 to TC-SEC-04 in detail, so the mapping is to be confirmed by team.
- **Tooling:** Postman/Newman, JMeter, UI smoke tests and coverage metrics are not set up (DEV-16). Tests run on SQLite, not the planned PostgreSQL staging environment (DEV-10).
- **Not planned in code yet:** SQL injection/XSS tests, HTTPS verification, concurrency tests (NFR20/NFR21) and notification stubs.
- **Document inconsistency:** the Test Plan introduction calls the system "BBMS v2.0" while the SRS and SAD are version 1.0. To be confirmed by team.

## Change history

| Date | Change | By |
|---|---|---|
| 2026-10-20 | Initial deviation log generated from code review | Team 9 |
