from app.db.database import engine
from app.models import Base

# Import all models so SQLAlchemy registers them.
import app.models  # noqa: F401


print("Creating database tables...")

Base.metadata.create_all(bind=engine)

print("Database tables created successfully.")