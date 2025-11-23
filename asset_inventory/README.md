# SahayaOn IT Asset Inventory

A multi-tenant IT asset inventory web app for managing hardware, software, and user assignments across many client accounts. Built with Flask + SQLite so MSP and IT teams can launch quickly without extra dependencies.

## Features

- **Role-aware experiences** – Admin, Engineer, Manager, and End User journeys with scoped access.
- **Multi-client control plane** – Admins can register clients, assign engineers per client, and see consolidated KPIs.
- **Engineer workbench** – Engineers receive client assignments from admins and can edit inventory only for those clients.
- **Manager + end-user focus** – Managers are tied to a single client (multiple managers per client) and see their team’s assets; end users only see their assignments.
- **Inventory intelligence** – Client cards, low-stock alerts, recent assignment feed, and metrics filtered to the user’s scope.

## Tech stack

- Python 3.11+
- Flask, Flask-Login, SQLAlchemy
- SQLite (default) – configurable via `DATABASE_URL`

## Getting started

```bash
cd asset_inventory
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Initialize the database

```bash
python seed_data.py
```

The seed script provisions sample clients, users, assets, and assignments so you can explore the UI immediately.

| Role     | Email                | Password    | Client scope                |
|----------|----------------------|-------------|-----------------------------|
| Admin    | admin@example.com    | admin123    | All clients (KriaSol + more) |
| Engineer | engineer@example.com | engineer123 | KriaSol HQ + Northwind      |
| Manager  | manager@example.com  | manager123  | KriaSol HQ                  |
| End User | user@example.com     | user123     | KriaSol HQ                  |

### Run the server

```bash
flask --app run.py --debug run
```

Visit http://127.0.0.1:5000/ and log in with one of the seeded accounts. The UI adapts automatically to the signed-in user's role and client scope.

## Customization tips

- Set `SECRET_KEY` and `DATABASE_URL` environment variables before running in production.
- Update `seed_data.py` or use the admin UI to add real clients, map engineers to clients, and invite actual teams.
- Extend the `Client`, `Asset`, and `Assignment` models with lifecycle, warranty, or cost center fields as required.

## Testing ideas

- Create end-to-end smoke scripts with Playwright or Cypress for login + assignment flows.
- Add unit tests for role guards (`role_required`) and helper methods in `models.py` when expanding business logic.
