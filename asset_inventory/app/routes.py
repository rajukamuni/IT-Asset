from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from . import db
from .models import Asset, Assignment, Role, User

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
    if current_user.role in (Role.MANAGER.value, Role.ADMIN.value):
        team_members = current_user.team_members.order_by(User.full_name).all()
        team_assignment_map = {
            member.id: [a for a in member.assignments if a.status == "active"]
            for member in team_members
        }

    metrics = {}
    low_stock_assets = []
    recent_assignments = []
    if current_user.role in (Role.ADMIN.value, Role.ENGINEER.value):
        metrics = {
            "asset_total": Asset.query.count(),
            "hardware_count": Asset.query.filter_by(asset_type="hardware").count(),
            "software_count": Asset.query.filter_by(asset_type="software").count(),
            "assigned_total": Assignment.query.filter_by(status="active").count(),
        }
        low_stock_assets = [
            asset
            for asset in Asset.query.all()
            if asset.available_quantity <= max(1, asset.total_quantity // 5)
        ]
        recent_assignments = (
            Assignment.query.order_by(Assignment.assigned_on.desc()).limit(5).all()
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
    )


@main_bp.route("/assets")
@login_required
def list_assets():
    assets = Asset.query.order_by(Asset.asset_type, Asset.name).all()
    return render_template("assets.html", assets=assets)


@main_bp.route("/assets/new", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN.value, Role.ENGINEER.value)
def create_asset():
    if request.method == "POST":
        total_quantity = int(request.form.get("total_quantity", 1) or 1)
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
        )
        db.session.add(asset)
        db.session.commit()
        flash("Asset added", "success")
        return redirect(url_for("main.list_assets"))
    return render_template("asset_form.html", asset=None)


@main_bp.route("/assets/<int:asset_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN.value, Role.ENGINEER.value)
def edit_asset(asset_id: int):
    asset = Asset.query.get_or_404(asset_id)
    if request.method == "POST":
        total_quantity = int(request.form.get("total_quantity", asset.total_quantity) or asset.total_quantity)
        asset.name = request.form.get("name", asset.name)
        asset.asset_tag = request.form.get("asset_tag", asset.asset_tag)
        asset.asset_type = request.form.get("asset_type", asset.asset_type)
        asset.category = request.form.get("category")
        asset.manufacturer = request.form.get("manufacturer")
        asset.status = request.form.get("status", asset.status)
        asset.total_quantity = total_quantity
        asset.available_quantity = int(request.form.get("available_quantity", asset.available_quantity) or asset.available_quantity)
        asset.notes = request.form.get("notes")
        db.session.commit()
        flash("Asset updated", "success")
        return redirect(url_for("main.list_assets"))
    return render_template("asset_form.html", asset=asset)


@main_bp.route("/assets/<int:asset_id>/assign", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN.value, Role.ENGINEER.value)
def assign_asset(asset_id: int):
    asset = Asset.query.get_or_404(asset_id)
    users = User.query.order_by(User.full_name).all()
    if request.method == "POST":
        user_id = int(request.form.get("user_id") or 0)
        quantity = int(request.form.get("quantity", 1) or 1)
        notes = request.form.get("notes")
        target_user = User.query.get_or_404(user_id)
        if quantity < 1:
            flash("Quantity must be at least 1", "warning")
        elif quantity > asset.available_quantity:
            flash("Not enough stock", "danger")
        else:
            asset.allocate(quantity)
            assignment = Assignment(user=target_user, asset=asset, quantity=quantity, notes=notes)
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

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Email is required", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Email already exists", "danger")
        else:
            user = User(
                full_name=request.form.get("full_name", "Unnamed"),
                email=email,
                role=request.form.get("role", Role.END_USER.value),
                department=request.form.get("department"),
                title=request.form.get("title"),
                manager_id=int(request.form.get("manager_id")) if request.form.get("manager_id") else None,
            )
            password = request.form.get("password") or "changeme123"
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("User created", "success")
            return redirect(url_for("main.manage_users"))

    return render_template("users.html", users=users, managers=managers, roles=Role)
