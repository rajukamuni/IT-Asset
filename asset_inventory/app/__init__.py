import os
from pathlib import Path
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message_category = "warning"


def create_app(test_config: dict | None = None) -> Flask:
    """Application factory for the IT asset inventory app."""
    app = Flask(__name__, instance_relative_config=True)

    default_db = "sqlite:///" + os.path.join(app.instance_path, "asset_inventory.db")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", default_db),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from .models import Role, User  # noqa: WPS433

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:  # type: ignore[name-defined]
        return User.query.get(int(user_id))

    from .routes import main_bp  # noqa: WPS433

    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_roles():
        return {"Role": Role}

    with app.app_context():
        db.create_all()

    return app
