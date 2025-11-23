from __future__ import annotations

import enum
from datetime import datetime
from typing import List

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


class Role(enum.Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    MANAGER = "manager"
    END_USER = "end_user"

    @classmethod
    def choices(cls) -> List[str]:
        return [role.value for role in cls]


engineer_clients = db.Table(
    "engineer_clients",
    db.Column("engineer_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("client_id", db.Integer, db.ForeignKey("client.id"), primary_key=True),
)


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(40), nullable=False, unique=True)
    industry = db.Column(db.String(120))
    headquarters = db.Column(db.String(120))
    contact_email = db.Column(db.String(120))
    contact_phone = db.Column(db.String(60))
    notes = db.Column(db.Text)

    assets = db.relationship("Asset", back_populates="client", cascade="all, delete-orphan")
    members = db.relationship("User", back_populates="client", lazy="dynamic")
    engineers = db.relationship(
        "User",
        secondary=engineer_clients,
        back_populates="supported_clients",
        lazy="dynamic",
    )


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default=Role.END_USER.value)
    password_hash = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(120))
    title = db.Column(db.String(120))
    manager_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=True)

    assignments = db.relationship("Assignment", back_populates="user", cascade="all, delete-orphan")
    team_members = db.relationship(
        "User",
        backref=db.backref("manager", remote_side=[id]),
        lazy="dynamic",
    )
    client = db.relationship("Client", back_populates="members")
    supported_clients = db.relationship(
        "Client",
        secondary=engineer_clients,
        back_populates="engineers",
        lazy="dynamic",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN.value

    @property
    def is_engineer(self) -> bool:
        return self.role == Role.ENGINEER.value

    @property
    def is_manager(self) -> bool:
        return self.role == Role.MANAGER.value

    @property
    def is_end_user(self) -> bool:
        return self.role == Role.END_USER.value

    def accessible_client_ids(self) -> list[int] | None:
        """Return client IDs the user can act on.

        None == unrestricted (admin); [] == no assignment (e.g., engineer missing mapping)
        """
        if self.is_admin:
            return None
        if self.is_engineer:
            return [client.id for client in self.supported_clients]
        if self.client_id:
            return [self.client_id]
        return []

    def can_access_client(self, client_id: int) -> bool:
        ids = self.accessible_client_ids()
        return ids is None or client_id in ids


class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    asset_tag = db.Column(db.String(120), unique=True, nullable=False)
    asset_type = db.Column(db.String(20), nullable=False)  # hardware or software
    category = db.Column(db.String(120))
    manufacturer = db.Column(db.String(120))
    status = db.Column(db.String(50), default="available")
    total_quantity = db.Column(db.Integer, default=1)
    available_quantity = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)

    assignments = db.relationship("Assignment", back_populates="asset", cascade="all, delete-orphan")
    client = db.relationship("Client", back_populates="assets")

    def allocate(self, quantity: int) -> None:
        if quantity > self.available_quantity:
            raise ValueError("Insufficient stock for allocation")
        self.available_quantity -= quantity
        if self.available_quantity == 0:
            self.status = "allocated"

    def release(self, quantity: int) -> None:
        self.available_quantity += quantity
        if self.available_quantity > 0:
            self.status = "available"


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default="active")
    notes = db.Column(db.String(255))
    assigned_on = db.Column(db.DateTime, default=datetime.utcnow)
    returned_on = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="assignments")
    asset = db.relationship("Asset", back_populates="assignments")
    client = db.relationship("Client")

    def close(self) -> None:
        self.status = "returned"
        self.returned_on = datetime.utcnow()
