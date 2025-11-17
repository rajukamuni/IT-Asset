"""Populate the database with starter users, assets, and assignments."""

from datetime import datetime

from app import create_app, db
from app.models import Asset, Assignment, Role, User


STARTER_USERS = [
    {
        "full_name": "Alice Torres",
        "email": "admin@example.com",
        "role": Role.ADMIN.value,
        "department": "IT",
        "title": "Head of IT",
        "password": "admin123",
    },
    {
        "full_name": "Ben Carter",
        "email": "engineer@example.com",
        "role": Role.ENGINEER.value,
        "department": "IT",
        "title": "Systems Engineer",
        "password": "engineer123",
    },
    {
        "full_name": "Maya Patel",
        "email": "manager@example.com",
        "role": Role.MANAGER.value,
        "department": "Product",
        "title": "Product Manager",
        "password": "manager123",
    },
    {
        "full_name": "Noah Kim",
        "email": "user@example.com",
        "role": Role.END_USER.value,
        "department": "Product",
        "title": "Product Analyst",
        "password": "user123",
    },
]

STARTER_ASSETS = [
    {
        "name": "Dell Latitude 7440",
        "asset_tag": "HW-DEL-7440-01",
        "asset_type": "hardware",
        "category": "Laptop",
        "manufacturer": "Dell",
        "total_quantity": 5,
        "available_quantity": 5,
    },
    {
        "name": "MacBook Pro 14",
        "asset_tag": "HW-APL-MBP14-02",
        "asset_type": "hardware",
        "category": "Laptop",
        "manufacturer": "Apple",
        "total_quantity": 3,
        "available_quantity": 3,
    },
    {
        "name": "Microsoft 365 E3",
        "asset_tag": "SW-MS365-E3",
        "asset_type": "software",
        "category": "Productivity",
        "manufacturer": "Microsoft",
        "total_quantity": 120,
        "available_quantity": 120,
    },
    {
        "name": "Slack Enterprise Grid",
        "asset_tag": "SW-SLACK-GRID",
        "asset_type": "software",
        "category": "Collaboration",
        "manufacturer": "Slack",
        "total_quantity": 50,
        "available_quantity": 50,
    },
]


def seed() -> None:
    app = create_app()
    with app.app_context():
        if User.query.first():
            print("Database already has data. Aborting seed.")
            return

        db.create_all()

        users = []
        for payload in STARTER_USERS:
            user = User(
                full_name=payload["full_name"],
                email=payload["email"],
                role=payload["role"],
                department=payload["department"],
                title=payload["title"],
            )
            user.set_password(payload["password"])
            users.append(user)
            db.session.add(user)

        db.session.flush()

        manager = next(u for u in users if u.role == Role.MANAGER.value)
        end_user = next(u for u in users if u.role == Role.END_USER.value)
        engineer = next(u for u in users if u.role == Role.ENGINEER.value)

        end_user.manager_id = manager.id

        assets = []
        for payload in STARTER_ASSETS:
            asset = Asset(**payload)
            assets.append(asset)
            db.session.add(asset)

        db.session.flush()

        laptop = next(a for a in assets if a.asset_tag == "HW-DEL-7440-01")
        slack = next(a for a in assets if a.asset_tag == "SW-SLACK-GRID")

        laptop.allocate(1)
        slack.allocate(3)

        db.session.add(
            Assignment(
                user=end_user,
                asset=laptop,
                quantity=1,
                notes="Primary device",
                assigned_on=datetime.utcnow(),
            )
        )
        db.session.add(
            Assignment(
                user=end_user,
                asset=slack,
                quantity=3,
                notes="Team collaboration",
                assigned_on=datetime.utcnow(),
            )
        )

        db.session.commit()
        print("Seed data created. Use the credentials in README to sign in.")


if __name__ == "__main__":
    seed()
