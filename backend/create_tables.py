from sqlalchemy import text

from app.db.database import engine
from app.models import Base
from app.db.schema_upgrade import upgrade_user_table

# Import all models so SQLAlchemy registers them.
import app.models  # noqa: F401


print("Creating database tables...")

with engine.begin() as connection:
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

Base.metadata.create_all(bind=engine)
upgrade_user_table(engine)

print("Database tables created successfully.")