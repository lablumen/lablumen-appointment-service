# lablumen-appointment-service

The core transactional backend for LabLumen. Manages lab appointments, patient profiles, the test catalog, and appointment lifecycle status. This service also owns the shared database schema — all Alembic migrations run here on startup.

---

## Responsibilities

- **Lab test catalog** — read-only list of 9 available tests (CBC, CMP, Lipid Profile, Thyroid, HbA1c, Urinalysis, Vitamin D, Vitamin B12, LFT, RFP) with prices snapshotted at booking time.
- **Patient profiles** — a Cognito account can register and manage multiple patient profiles (self, family members).
- **Appointments** — booking a date, time slot, and one or more test-patient combinations in a single transaction.
- **Appointment status** — `Booked → Checked-In → Completed → Cancelled`. Staff update status via PATCH.
- **Operations queue** — a staff-facing endpoint returning a flat grid of every ordered test with status, patient info, and report state.
- **Slot locking** — acquires a Redis distributed lock on `(date, time_slot)` before writing to Postgres, preventing double-bookings under concurrent requests.
- **Event publishing** — after a booking is committed, sends an `appointment.booked` event to SQS (fire-and-forget). A publish failure does not roll back the booking.

---

## Tech Stack

| Component | Detail |
|---|---|
| Runtime | Python 3.12 |
| Framework | FastAPI (fully async) |
| ORM | SQLAlchemy 2.x (async, mapped_column style) |
| Migrations | Alembic |
| Database driver | asyncpg |
| Validation | Pydantic v2 + pydantic-settings |
| Distributed lock | Redis (`redis.asyncio`, `SET NX EX`) |
| Messaging | AWS SQS (boto3) |
| Auth | Cognito JWT verification (PyJWT + JWKS, cached per pod) |

---

## Source Layout

```
app/
  main.py          Entry point; registers routers; runs Alembic migrations on startup
  auth.py          JWT verification against Cognito JWKS; role enforcement via cognito:groups
  models.py        SQLAlchemy ORM models for all tables
  schemas.py       Pydantic request/response schemas
  db.py            Async engine + session factory (DATABASE_URL from environment)
  redis_client.py  Distributed slot-lock helper (acquire / release)
  sqs.py           Fire-and-forget SQS publisher for booking events
  config.py        Settings loaded from environment variables
  routers/
    appointments.py  Booking, status updates, operations queue
    patients.py      Patient profile CRUD
    lab_tests.py     Test catalog listing
    health.py        /healthz liveness probe
alembic/
  versions/
    0001_initial_schema.py  All tables: users, patient_profiles, lab_tests, appointments,
                            appointment_test_mapping, lab_reports, report_embeddings
    0002_seed_lab_tests.py  Seeds the 9 lab test records with names and prices
```

---

## API Endpoints

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/api/v1/lab-tests` | Patient, Staff | List all active tests |
| GET | `/api/v1/patients` | Patient | List own patient profiles |
| POST | `/api/v1/patients` | Patient | Create a patient profile |
| DELETE | `/api/v1/patients/{id}` | Patient | Delete a patient profile |
| POST | `/api/v1/appointments` | Patient | Book an appointment |
| GET | `/api/v1/appointments` | Patient | List own appointments |
| PATCH | `/api/v1/appointments/{id}/status` | Staff | Update appointment status |
| GET | `/api/v1/appointments/ops` | Staff | Full operations queue |
| GET | `/healthz` | Internal | Liveness probe |

---

## Database Ownership

This service owns the entire database schema. Alembic migrations run automatically on every pod startup and cover all tables — including `lab_reports` and `report_embeddings` used by the report service and AI Lambda. This keeps migration management in one place while services stay independent at the API layer.

---

## Configuration

All values are injected as environment variables by External Secrets Operator from AWS at pod startup.

| Variable | Source | Description |
|---|---|---|
| `DATABASE_URL` | Secrets Manager | PostgreSQL async connection string |
| `REDIS_URL` | Kubernetes values | Redis service URL (`redis://redis:6379/0`) |
| `COGNITO_USER_POOL_ID` | SSM | Cognito pool ID for JWT verification |
| `COGNITO_APP_CLIENT_ID` | SSM | Cognito app client ID |
| `NOTIFICATIONS_QUEUE_URL` | SSM | SQS queue URL for booking events |
| `AWS_REGION` | SSM | AWS region |

---

## CI/CD

| Trigger | What Happens |
|---|---|
| Pull request | Lint (`ruff`), unit tests (`pytest`), SAST (SonarCloud), SCA (Snyk), container scan (Trivy) |
| Merge to `main` | Build image → Trivy gate → push to ECR → update `values-dev.yaml` in `lablumen-k8s` → ArgoCD deploys to dev |
| GitHub Release | Retag ECR image SHA → semver → update `values-prod.yaml` → ArgoCD deploys to production |

CI/CD logic is centralized in `lablumen-shared`. This repo only contains the thin caller workflows in `.github/workflows/`.
