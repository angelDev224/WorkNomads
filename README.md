# WorkNomads — Photo Classification Platform

A cloud-deployable microservices platform where users submit a profile photo with metadata and receive a classification result. Admins can search, filter, and manage all submissions.

---

## Architecture

```
Browser
  │
  ▼
[api-gateway :80]  ←── Nginx reverse proxy, rate-limiting, security headers
  │
  ├──► [auth-service :8001]        Registration, login, JWT, refresh, logout
  ├──► [submission-service :8002]  Photo upload + metadata + MinIO storage
  └──► [admin-service :8004]       Admin-only CRUD with filtering + audit log
              │
        RabbitMQ queue (durable, persistent)
              │
              ▼
    [classifier-service]           Async RabbitMQ consumer — classification
              │
              ▼
          PostgreSQL ◄─────────────────── All services share one DB
          MinIO / S3                      Photo object storage (pre-signed URLs)
          Redis                           Refresh token blacklist / cache
```

Architecture diagram source is available at `docs/architecture.drawio` (open in draw.io/diagrams.net).

### Services

| Service | Port | Description |
|---|---|---|
| api-gateway | 80 | Nginx — public entry point, rate-limiting, routing |
| auth-service | 8001 | Register/login, JWT access tokens, HttpOnly refresh cookies |
| submission-service | 8002 | Multipart photo upload, metadata, async classification trigger |
| classifier-service | — | RabbitMQ consumer, classifies submissions, writes results |
| admin-service | 8004 | Admin-only CRUD with filtering, ban/unban, audit log |

### Key Technical Decisions

| Concern | Choice | Why |
|---|---|---|
| Password hashing | `bcrypt` (direct, rounds=12) | `passlib` is abandoned and incompatible with `bcrypt≥5` |
| Token security | JWT (15 min) + HttpOnly refresh cookie (7 days) | XSS-safe; instant revocation via Redis blacklist |
| File upload security | Magic-byte validation + 10 MB cap | Extension spoofing prevented; DoS mitigated |
| Async classification | RabbitMQ durable queue + KEDA autoscaling | User request never blocks on classification |
| Admin mutations | Append-only `audit_log` table | Full accountability trail |

---

## Quick Start (Docker Compose)

### Prerequisites
- Docker ≥ 24 and Docker Compose v2

### 1. Configure

```bash
cp .env.example .env
# Edit .env — at minimum set a strong JWT_SECRET_KEY:
#   openssl rand -hex 32
```

### 2. Start the full stack

```bash
docker compose up --build
```

For local browser access to photo URLs, keep:

```env
MINIO_ENDPOINT=minio:9000
MINIO_PUBLIC_ENDPOINT=localhost:9000
MINIO_BUCKET_PUBLIC=true
```

First run takes ~3 minutes to pull and build images. The `minio-init` container
creates the photo bucket automatically. Subsequent starts are fast.

### 3. Verify everything is up

| URL | What |
|---|---|
| http://localhost/healthz | Gateway health check |
| http://localhost/auth/docs | Auth service — Swagger UI |
| http://localhost/submissions/docs | Submission service — Swagger UI |
| http://localhost/admin/docs | Admin service — Swagger UI |
| http://localhost:9000 | MinIO object API (presigned photo URLs) |
| http://localhost:15672 | RabbitMQ management UI (`worknomads` / `changeme`) |
| http://localhost:9001 | MinIO console (`minioadmin` / `minioadmin`) |

---

## API Reference

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/v1/auth/register` | — | Create account (`email` + `password`) |
| `POST` | `/v1/auth/login` | — | Returns `access_token`; sets refresh cookie |
| `POST` | `/v1/auth/refresh` | refresh cookie | Rotate refresh token, return new access token |
| `POST` | `/v1/auth/logout` | refresh cookie | Revoke refresh token |
| `GET` | `/v1/auth/me` | Bearer | Current user profile |

### Submissions

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/v1/submissions` | Bearer | Upload photo (multipart) + metadata |
| `GET` | `/v1/submissions` | Bearer | List own submissions (paginated) |
| `GET` | `/v1/submissions/{id}` | Bearer | Get submission + classification result |

**Submission form fields:** `name`, `age` (18–120), `place_of_living`, `gender`
(`male`/`female`/`non-binary`/`prefer_not_to_say`), `country_of_origin` (ISO 3166-1 alpha-2),
`description` (optional, max 1000 chars), `photo` (JPEG/PNG/WebP, max 10 MB).

### Admin (`role=admin` required)

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/admin/submissions` | List all submissions with filters |
| `GET` | `/v1/admin/submissions/{id}` | Full record with photo URL + result |
| `DELETE` | `/v1/admin/submissions/{id}` | Soft-delete (sets `deleted_at`) |
| `GET` | `/v1/admin/users` | List all users |
| `POST` | `/v1/admin/users/{id}/ban` | Disable account |
| `POST` | `/v1/admin/users/{id}/unban` | Restore account |

**Submission filter query params:**
`age_min`, `age_max`, `gender`, `place_of_living` (partial match), `country_of_origin`,
`status` (`pending`/`classified`/`error`), `created_after`, `created_before`, `include_deleted`

---

## Creating an Admin Account

Register a normal account first, then promote it in the database:

```bash
docker compose exec postgres psql -U worknomads -d worknomads \
  -c "UPDATE users SET role='admin' WHERE email='admin@example.com';"
```

---

## Running Tests

### Locally — any Python version including 3.14 (no MSVC / Build Tools required)

Each service ships a `requirements-test.txt` with only pure-Python or pre-built
packages. It uses `aiosqlite` instead of `asyncpg`, so no C/Rust compilation
is needed. Environment variables are injected by `pytest-env` from `pytest.ini`
— no `.env` file needed.

```powershell
# auth-service
cd services\auth-service
pip install -r requirements-test.txt
python -m pytest -v

# submission-service
cd ..\submission-service
pip install -r requirements-test.txt
python -m pytest -v

# classifier-service
cd ..\classifier-service
pip install -r requirements-test.txt
python -m pytest -v

# admin-service
cd ..\admin-service
pip install -r requirements-test.txt
python -m pytest -v
```

> **Note:** If `pytest` is not on your `PATH` (common with `--user` installs),
> use `python -m pytest` instead.

### Via Docker (Python 3.12, full dependencies)

```bash
for svc in auth-service submission-service classifier-service admin-service; do
  echo "=== $svc ==="
  docker compose run --rm $svc python -m pytest -v
done
```

### Dependency split rationale

| File | Used by | Contains |
|---|---|---|
| `requirements.txt` | Docker (`python:3.12-slim`) | Full runtime deps including `asyncpg`, `aio-pika`, `miniopy-async` |
| `requirements-test.txt` | Local dev (any Python) | Pure-Python/pre-built only; `asyncpg` → `aiosqlite`; `passlib` → `bcrypt` direct |

---


## Project Structure

```
WorkNomads/
├── docs/
│   └── architecture.drawio   Editable block diagram (draw.io)
│
├── services/
│   ├── auth-service/          FastAPI — register, login, JWT, Redis token blacklist
│   │   ├── app/
│   │   │   ├── api/auth.py    All auth endpoints
│   │   │   ├── core/          security.py (bcrypt + JWT), redis.py
│   │   │   ├── db/            SQLAlchemy models + async session
│   │   │   └── schemas/       Pydantic request/response models
│   │   ├── migrations/        Alembic — users + refresh_tokens tables
│   │   ├── tests/
│   │   ├── Dockerfile          Multi-stage, non-root user
│   │   ├── requirements.txt    Runtime (Docker)
│   │   └── requirements-test.txt  Local testing (any Python version)
│   │
│   ├── submission-service/    FastAPI — multipart upload, MinIO, RabbitMQ publish
│   ├── classifier-service/    RabbitMQ consumer — stub classifier (swap for real ML)
│   ├── admin-service/         FastAPI — admin panel, audit log
│   └── api-gateway/           Nginx config (rate-limiting, routing, security headers)
│
├── k8s/
│   ├── namespace.yaml
│   ├── infra/                 ConfigMap + Secrets (placeholder values)
│   ├── auth-service/          Deployment + Service + HPA
│   ├── submission-service/    Deployment + Service
│   ├── classifier-service/    Deployment + KEDA ScaledObject (queue-depth scaling)
│   ├── admin-service/         Deployment + Service
│   └── api-gateway/           Deployment + Service + Ingress (TLS via cert-manager)
│
├── .github/
│   └── workflows/
│       ├── ci.yml             lint → test → Docker build (multi-arch) → Trivy scan
│       └── cd.yml             Image tag injection → kubectl apply → rollout wait
│
├── docker-compose.yml         Full local stack (one command)
├── .env.example               All required env vars with documentation
├── requirements.md            Full requirements + architecture decisions
└── INSTRUCTIONS.md            Setup guide, security decisions, Kubernetes strategy
```

---

## Security Overview

| Layer | Mechanism |
|---|---|
| Passwords | `bcrypt` rounds=12 (direct, no passlib) |
| Access tokens | JWT HS256, 15 min TTL, `sub` + `role` claims |
| Refresh tokens | HttpOnly + Secure + SameSite=Strict cookie, 7-day TTL, Redis blacklist |
| File uploads | MIME type + magic-byte validation; 10 MB cap in Nginx and in-service |
| Rate limiting | Nginx `limit_req_zone` — 10 req/s (auth), 30 req/s (API) |
| Admin access | `role=admin` claim checked at gateway **and** service (defence-in-depth) |
| Audit trail | All admin mutations appended to `audit_log` table |
| Secrets | `.env` locally; Kubernetes Secrets (Sealed Secrets recommended for prod) |
