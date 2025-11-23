from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import false

from . import db
from .models import Asset, Assignment, Client, Role, User

main_bp = Blueprint("main", __name__)


def role_required(*roles: str) -> Callable:
    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped_view(**kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return view(**kwargs)

        return wrapped_view

    return decorator


def _accessible_clients():
    client_ids = current_user.accessible_client_ids()
    query = Client.query.order_by(Client.name)
    if client_ids is None:
        return query.all()
    if not client_ids:
        return []
    return query.filter(Client.id.in_(client_ids)).all()


def _assert_client_access(client_id: int) -> None:
    if not current_user.can_access_client(client_id):
        abort(403)


def _scoped_query(model):
    client_ids = current_user.accessible_client_ids()
    query = model.query
    if client_ids is None or not hasattr(model, "client_id"):
        return query
    if not client_ids:
        return query.filter(false())
    return query.filter(model.client_id.in_(client_ids))


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.login"))


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid credentials", "danger")
        else:
            login_user(user)
            flash(f"Welcome back, {user.full_name.split()[0]}!", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("login.html")


@main_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Signed out successfully", "info")
    return redirect(url_for("main.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    active_assignments = [a for a in current_user.assignments if a.status == "active"]
    hardware_assignments = [a for a in active_assignments if a.asset.asset_type == "hardware"]
    software_assignments = [a for a in active_assignments if a.asset.asset_type == "software"]

    team_members = []
    team_assignment_map: dict[int, list[Assignment]] = {}
    if current_user.is_manager:
        team_members = (
            current_user.team_members.filter_by(client_id=current_user.client_id)
            .order_by(User.full_name)
            .all()
        )
    elif current_user.is_admin:
        team_members = current_user.team_members.order_by(User.full_name).all()
    if team_members:
        team_assignment_map = {
            member.id: [a for a in member.assignments if a.status == "active"]
            for member in team_members
        }

    metrics = {}
    low_stock_assets = []
    recent_assignments = []
    client_cards = []
    if current_user.is_admin or current_user.is_engineer:
        asset_query = _scoped_query(Asset)
        assignment_query = _scoped_query(Assignment)
        metrics = {
            "asset_total": asset_query.count(),
            "hardware_count": asset_query.filter_by(asset_type="hardware").count(),
            "software_count": asset_query.filter_by(asset_type="software").count(),
            "assigned_total": assignment_query.filter_by(status="active").count(),
        }
        low_stock_assets = [
            asset
            for asset in asset_query.all()
            if asset.available_quantity <= max(1, asset.total_quantity // 5)
        ]
        recent_assignments = (
            assignment_query.order_by(Assignment.assigned_on.desc()).limit(5).all()
        )

    if not current_user.is_end_user:
        for client in _accessible_clients():
            if not client:
                continue
            client_cards.append(
                {
                    "client": client,
                    "asset_total": Asset.query.filter_by(client_id=client.id).count(),
                    "active_assignments": Assignment.query.filter_by(
                        client_id=client.id, status="active"
                    ).count(),
                    "manager_count": client.members.filter_by(role=Role.MANAGER.value).count(),
                }
            )

    return render_template(
        "dashboard.html",
        hardware_assignments=hardware_assignments,
        software_assignments=software_assignments,
        team_members=team_members,
        team_assignment_map=team_assignment_map,
        metrics=metrics,
        low_stock_assets=low_stock_assets,
        recent_assignments=recent_assignments,
        client_cards=client_cards,
    )


@main_bp.route("/assets")
@login_required
def list_assets():
    assets = _scoped_query(Asset).order_by(Asset.asset_type, Asset.name).all()
    return render_template(
        "assets.html",
        assets=assets,
        clients=_accessible_clients(),
    )


@main_bp.route("/assets/new", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN.value, Role.ENGINEER.value)
def create_asset():
    client_options = _accessible_clients()
    if not client_options:
        flash("No client access assigned. Ask an admin to map you to a client first.", "warning")
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        total_quantity = int(request.form.get("total_quantity", 1) or 1)
        client_id = int(request.form.get("client_id") or 0)
        if client_id not in [client.id for client in client_options]:
            flash("Please pick a client you support.", "danger")
            return render_template("asset_form.html", asset=None, clients=client_options)
        asset = Asset(
            name=request.form.get("name", "Untitled"),
            asset_tag=request.form.get("asset_tag", ""),
            asset_type=request.form.get("asset_type", "hardware"),
            category=request.form.get("category"),
            manufacturer=request.form.get("manufacturer"),
            status=request.form.get("status", "available"),
            total_quantity=total_quantity,
            available_quantity=int(request.form.get("available_quantity", total_quantity) or total_quantity),
            notes=request.form.get("notes"),
            client_id=client_id,
        )
        db.session.add(asset)
        db.session.commit()
        flash("Asset added", "success")
        return redirect(url_for("main.list_assets"))
    return render_template("asset_form.html", asset=None, clients=client_options)


@main_bp.route("/assets/<int:asset_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN.value, Role.ENGINEER.value)
def edit_asset(asset_id: int):
    asset = Asset.query.get_or_404(asset_id)
    _assert_client_access(asset.client_id)
    client_options = _accessible_clients()
    if request.method == "POST":
        total_quantity = int(request.form.get("total_quantity", asset.total_quantity) or asset.total_quantity)
        client_id = int(request.form.get("client_id") or asset.client_id)
        if client_id not in [client.id for client in client_options]:
            flash("Please pick a client you support.", "danger")
            return render_template("asset_form.html", asset=asset, clients=client_options)
        asset.name = request.form.get("name", asset.name)
        asset.asset_tag = request.form.get("asset_tag", asset.asset_tag)
        asset.asset_type = request.form.get("asset_type", asset.asset_type)
        asset.category = request.form.get("category")
        asset.manufacturer = request.form.get("manufacturer")
        asset.status = request.form.get("status", asset.status)
        asset.total_quantity = total_quantity
        asset.available_quantity = int(request.form.get("available_quantity", asset.available_quantity) or asset.available_quantity)
        asset.notes = request.form.get("notes")
        asset.client_id = client_id
        db.session.commit()
        flash("Asset updated", "success")
        return redirect(url_for("main.list_assets"))
    return render_template("asset_form.html", asset=asset, clients=client_options)


@main_bp.route("/assets/<int:asset_id>/assign", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN.value, Role.ENGINEER.value)
def assign_asset(asset_id: int):
    asset = Asset.query.get_or_404(asset_id)
    _assert_client_access(asset.client_id)
    users = (
        User.query.filter_by(client_id=asset.client_id)
        .order_by(User.full_name)
        .all()
    )
    if request.method == "POST":
        user_id = int(request.form.get("user_id") or 0)
        quantity = int(request.form.get("quantity", 1) or 1)
        notes = request.form.get("notes")
        target_user = User.query.get_or_404(user_id)
        if target_user.client_id != asset.client_id:
            flash("User must belong to the same client as the asset.", "danger")
            return render_template("assign_asset.html", asset=asset, users=users)
        if quantity < 1:
            flash("Quantity must be at least 1", "warning")
        elif quantity > asset.available_quantity:
            flash("Not enough stock", "danger")
        else:
            asset.allocate(quantity)
            assignment = Assignment(
                user=target_user,
                asset=asset,
                quantity=quantity,
                notes=notes,
                client_id=asset.client_id,
            )
            db.session.add(assignment)
            db.session.commit()
            flash("Asset assigned", "success")
            return redirect(url_for("main.list_assets"))
    return render_template("assign_asset.html", asset=asset, users=users)


@main_bp.route("/assignments/<int:assignment_id>/return", methods=["POST"])
@login_required
@role_required(Role.ADMIN.value, Role.ENGINEER.value)
def return_assignment(assignment_id: int):
    assignment = Assignment.query.get_or_404(assignment_id)
    _assert_client_access(assignment.client_id)
    if assignment.status != "active":
        flash("Assignment already closed", "info")
    else:
        assignment.asset.release(assignment.quantity)
        assignment.close()
        db.session.commit()
        flash("Asset returned to inventory", "success")
    return redirect(request.referrer or url_for("main.dashboard"))


@main_bp.route("/users", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN.value)
def manage_users():
    users = User.query.order_by(User.role, User.full_name).all()
    managers = User.query.filter(User.role.in_([Role.MANAGER.value, Role.ADMIN.value])).all()
    clients = Client.query.order_by(Client.name).all()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Email is required", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Email already exists", "danger")
        else:
            role = request.form.get("role", Role.END_USER.value)
            primary_client_id = request.form.get("client_id")
            client_id = int(primary_client_id) if primary_client_id else None
            if role in (Role.MANAGER.value, Role.END_USER.value) and not client_id:
                flash("Managers and end users must be tied to a client.", "danger")
                return render_template(
                    "users.html",
                    users=users,
                    managers=managers,
                    roles=Role,
                    clients=clients,
                )
            user = User(
                full_name=request.form.get("full_name", "Unnamed"),
                email=email,
                role=role,
                department=request.form.get("department"),
                title=request.form.get("title"),
                manager_id=int(request.form.get("manager_id")) if request.form.get("manager_id") else None,
                client_id=client_id,
            )
            password = request.form.get("password") or "changeme123"
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            if role == Role.ENGINEER.value:
                assigned_client_ids = [int(cid) for cid in request.form.getlist("assigned_client_ids") if cid]
                if assigned_client_ids:
                    user.supported_clients = Client.query.filter(Client.id.in_(assigned_client_ids)).all()
                    db.session.commit()
            flash("User created", "success")
            return redirect(url_for("main.manage_users"))

    return render_template("users.html", users=users, managers=managers, roles=Role, clients=clients)


@main_bp.route("/clients", methods=["GET", "POST"])
@login_required
def clients():
    if request.method == "POST":
        if not current_user.is_admin:
            abort(403)
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()
        if not name or not code:
            flash("Client name and code are required.", "danger")
        elif Client.query.filter_by(code=code).first():
            flash("Client code already exists.", "danger")
        else:
            client = Client(
                name=name,
                code=code,
                industry=request.form.get("industry"),
                headquarters=request.form.get("headquarters"),
                contact_email=request.form.get("contact_email"),
                contact_phone=request.form.get("contact_phone"),
                notes=request.form.get("notes"),
            )
            db.session.add(client)
            db.session.commit()
            flash("Client created.", "success")
            return redirect(url_for("main.clients"))
    clients = _accessible_clients()
    engineer_directory = []
    if current_user.is_admin:
        engineer_directory = (
            User.query.filter_by(role=Role.ENGINEER.value)
            .order_by(User.full_name)
            .all()
        )
    return render_template(
        "clients.html",
        clients=clients,
        engineer_directory=engineer_directory,
    )


@main_bp.route("/clients/<int:client_id>/engineers", methods=["POST"])
@login_required
@role_required(Role.ADMIN.value)
def update_client_engineers(client_id: int):
    client = Client.query.get_or_404(client_id)
    assigned_engineer_ids = [int(eid) for eid in request.form.getlist("engineer_ids") if eid]
    if assigned_engineer_ids:
        client.engineers = (
            User.query.filter(
                User.role == Role.ENGINEER.value,
                User.id.in_(assigned_engineer_ids),
            ).all()
        )
    else:
        client.engineers = []
    db.session.commit()
    flash(f"Engineer access updated for {client.name}.", "success")
    return redirect(url_for("main.clients"))
