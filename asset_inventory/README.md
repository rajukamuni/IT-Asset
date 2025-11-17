# IT Asset Inventory

A role-based IT asset inventory web app for tracking hardware, software, stock levels, and user assignments. The app is built with Flask + SQLite so small teams can deploy quickly without extra dependencies.

## Features

- **Authentication & roles** – Admin, Engineer, Manager, and End User experiences with tailored permissions.
- **Personal inventory view** – Each signed-in user sees their allocated hardware and software.
- **Team insights for managers** – Managers view their direct reports plus each report's assets.
- **Asset operations for engineers** – Engineers (and admins) can add/edit stock, assign items, and close assignments.
- **Admin controls** – Admins manage the full directory, invite new accounts, and access every feature.
- **Stock health** – Low stock alerts, recent assignment feed, and quick metrics for busy IT teams.

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

The seed script provisions sample users, assets, and assignments so you can explore the UI immediately.

| Role     | Email                | Password    |
|----------|---------------------|-------------|
| Admin    | admin@example.com    | admin123    |
| Engineer | engineer@example.com | engineer123 |
| Manager  | manager@example.com  | manager123  |
| End User | user@example.com     | user123     |

### Run the server

```bash
flask --app run.py --debug run
```

Visit http://127.0.0.1:5000/ and log in with one of the seeded accounts. The UI adapts automatically to the signed-in user's role.

## Customization tips

- Set `SECRET_KEY` and `DATABASE_URL` environment variables for production deployments.
- Update `seed_data.py` or use the admin UI to add real users and assets.
- Extend the `Asset` and `Assignment` models with fields like lifecycle stage, warranty, or cost centers as needed.

## Testing ideas

- Create end-to-end smoke scripts with Playwright or Cypress for login + assignment flows.
- Add unit tests for role guards (`role_required`) and helper methods in `models.py` when expanding business logic.
