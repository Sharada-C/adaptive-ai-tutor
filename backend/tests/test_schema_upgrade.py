from sqlalchemy import text

from app.db.database import SessionLocal, engine
from app.db.schema_upgrade import upgrade_user_table
from app.models import User


def test_legacy_required_columns_no_longer_block_inserts():
    """An old users table with a required column the model lacks."""

    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS legacy_created_at "
            "TIMESTAMP NOT NULL DEFAULT now()"
        ))
        connection.execute(text(
            "ALTER TABLE users ALTER COLUMN legacy_created_at DROP DEFAULT"
        ))

    db = SessionLocal()

    try:
        upgrade_user_table(engine)

        user = User(username="legacy_schema_user", role="student")
        db.add(user)
        db.commit()

        db.delete(user)
        db.commit()

    finally:
        db.close()

        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE users DROP COLUMN IF EXISTS legacy_created_at"
            ))


def test_upgrade_is_safe_to_run_twice():
    upgrade_user_table(engine)
    upgrade_user_table(engine)
