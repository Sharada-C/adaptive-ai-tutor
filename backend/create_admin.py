"""Create an administrator (or promote an existing user to one).

    python create_admin.py <username> <password>

Run from the ``backend`` directory after ``python create_tables.py``.
Admins can then promote other users to instructor or admin from the
Admin page of the app.
"""

import sys

from app.db.database import SessionLocal, engine
from app.db.schema_upgrade import upgrade_user_table
from app.services.admin_account import ensure_admin


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python create_admin.py <username> <password>")
        return 1

    username, password = sys.argv[1].strip(), sys.argv[2]

    if len(password) < 8:
        print("The password must be at least 8 characters.")
        return 1

    upgrade_user_table(engine)

    db = SessionLocal()

    try:
        user = ensure_admin(db, username, password)
    finally:
        db.close()

    print(f"'{user.username}' is now an admin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
