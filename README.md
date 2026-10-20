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

The web app is served on http://localhost:8000/ with PostgreSQL 16 as the database.

## Run tests

```powershell
python manage.py test
```

## Team workflow

- Work on your own branch (e.g. `yourname/bb-NN-short-title`).
- Open a pull request into `main` and put `Closes #N` in the description.
- The repo owner reviews and merges.
- Any deviation from the SRS/SAD is recorded in `DEVIATIONS.md`.
