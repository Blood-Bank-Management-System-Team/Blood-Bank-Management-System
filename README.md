# Blood Bank Management System (BBMS)

Team 9 – Software Engineering project. A layered modular monolith built with Python 3.12, Django 5, Django REST Framework, PostgreSQL and Docker. User roles: Donor, Blood Bank Staff, Hospital/Patient, Administrator.

## Modules

| App | Functional requirements |
|---|---|
| users | FR1–FR3 |
| donors | FR4–FR7 |
| inventory | FR8–FR11, FR30, FR33, FR34 |
| bloodrequests | FR12–FR16, FR31, FR32, FR35 |
| camps | FR17–FR19 |
| notifications | FR20–FR21 |
| reports | FR22, FR23, FR28 |

Operational rules (e.g. `BBMS_MIN_DONATION_INTERVAL_DAYS`, default 90) are configured through environment variables, not hard-coded.

## Run locally (Windows, venv + SQLite)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # optional; leave DB_HOST empty to use SQLite
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/, `/admin/` and `/api/health/`.

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

The web app is served on http://localhost:8000/ with PostgreSQL 16 as the database. The image runs gunicorn as a non-root user, serves static files with WhiteNoise and applies migrations when the container starts.

## Deploy for free on Render + Neon + Brevo

Render hosts the app (free web service, built from `render.yaml`), Neon provides the Postgres database (free, no expiry; Render's own free Postgres is deleted after 30 days) and Brevo sends email over HTTPS (Render's free plan blocks SMTP).

1. **Neon** - create a project at https://neon.tech. In *Connect*, enable *Connection pooling* and copy the pooled connection string (`postgresql://user:pass@ep-xxx-pooler.<region>.aws.neon.tech/neondb?sslmode=require`). This is your `DATABASE_URL`.
2. **Brevo** - at https://www.brevo.com verify a sender (Senders, Domains & Dedicated IPs > Senders) and create an API key (SMTP & API > API Keys). The verified sender address is your `DEFAULT_FROM_EMAIL`, for example `BBMS <you@example.com>`.
3. **Render** - New > Blueprint, pick this repository and branch `main`. Render reads `render.yaml`; fill in the values marked `sync: false`:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string from step 1 |
   | `BREVO_API_KEY` | the Brevo API key |
   | `DEFAULT_FROM_EMAIL` | the verified Brevo sender |
   | `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD`, `DJANGO_SUPERUSER_EMAIL` | your first admin. Created on start if the username does not exist; an existing user's password is never changed. Render's free plan has no shell, so this is the way to get an admin. |

4. Open `https://<your-service>.onrender.com/api/health/`; it should return HTTP 200. The first request after 15 minutes of idle time is slow because the free instance sleeps. If Render assigns a different host name than `bbms-web.onrender.com`, it is allowed automatically (`RENDER_EXTERNAL_HOSTNAME`).

Render redeploys by itself on every push to `main`; the SSH deploy job in the CD workflow is not used here.

## Deployment (CD)

This section describes deploying to your own server over SSH. For Render, see above.

### Pipeline

```
PR -> CI (lint, tests, Docker build check) -> merge to main -> CI passes on main
   -> CD: build & push image to ghcr.io -> deploy over SSH -> /api/health/ smoke test
```

- **CI** (`.github/workflows/ci.yml`) also builds the Docker image on every push and PR (no push), so a broken Dockerfile is caught before merge.
- **CD** (`.github/workflows/cd.yml`) starts when CI completes successfully on `main`, or manually from the Actions tab.
- **build-and-push** publishes `ghcr.io/<owner>/<repo>` (lowercase) tagged with the commit SHA and `latest`.
- **deploy** (environment `production`) copies `docker-compose.prod.yml` and `scripts/deploy.sh` to the server, logs in to ghcr, pulls the tag and restarts the stack. It then calls `/api/health/` and fails the run unless it returns HTTP 200.
- Only one deploy runs at a time (`concurrency: cd-production`); later runs wait in the queue.

### One-time setup

1. **Secrets** - Settings > Secrets and variables > Actions (repository secrets, or secrets of the `production` environment):

   | Secret | Meaning |
   |---|---|
   | `DEPLOY_HOST` | Server host name or IP. If empty, the deploy step is skipped with a notice. |
   | `DEPLOY_USER` | SSH user (must be allowed to run `docker`). |
   | `DEPLOY_SSH_KEY` | Private SSH key (full text) for that user. |
   | `DEPLOY_PATH` | Absolute directory on the server, e.g. `/opt/bbms`. |
   | `DEPLOY_HEALTH_URL` | Optional. Full health-check URL if it differs from `https://<DEPLOY_HOST>/api/health/`. |

2. **Environment** - Settings > Environments > New environment > `production`. Optionally add *Required reviewers* so every deploy needs a manual approval.
3. **Server** - install Docker with the Compose plugin, create `DEPLOY_PATH`, and put a `.env` there (copy `.env.example`) with `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain` and the `DB_*` values. `DJANGO_DEBUG` is forced to `False` by `docker-compose.prod.yml`.
4. **HTTPS** - the web container listens on `127.0.0.1:8000`. Put a TLS-terminating reverse proxy (nginx, Caddy, ...) in front of it that forwards to that port and sets `X-Forwarded-Proto`. Django redirects plain HTTP to HTTPS and sets HSTS when `DJANGO_DEBUG=False`.
5. The image is pulled with the workflow's own `GITHUB_TOKEN`; no personal access token is needed.

### Roll back

Actions > **CD** > *Run workflow* > enter an older commit SHA in `image_tag` (any tag already in the GitHub Packages list for the repo). The build is skipped and that image is deployed and health-checked. Leave `image_tag` empty to build and deploy the selected branch instead.
Note that migrations are not reversed automatically; a rollback past a migration needs a manual fix.

## Run tests

```powershell
python manage.py test
```

## Team workflow

- Work on your own branch (e.g. `yourname/bb-NN-short-title`).
- Open a pull request into `main` and put `Closes #N` in the description.
- The repo owner reviews and merges.
- Any deviation from the SRS/SAD is recorded in `DEVIATIONS.md`.
