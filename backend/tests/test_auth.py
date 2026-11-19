"""Authentication, roles and access control."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func

from app.api import quiz
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.database import SessionLocal
from app.main import app
from app.models import StudentProfile, User
from tests.conftest import TEST_PASSWORD, ensure_account, token_for


# These tests are about who may do what, so the client starts anonymous.
http = TestClient(app)

PASSWORD = "correct-horse-1"


def _name(prefix="pytest_auth"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _delete(username):
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(func.lower(User.username) == username.lower())
            .first()
        )

        if user:
            db.query(StudentProfile).filter(
                StudentProfile.user_id == user.id
            ).delete()
            db.delete(user)
            db.commit()

    finally:
        db.close()


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------- passwords


def test_password_hash_round_trip():
    stored = hash_password("s3cret-password")

    assert stored != "s3cret-password"
    assert "s3cret-password" not in stored
    assert verify_password("s3cret-password", stored)
    assert not verify_password("wrong", stored)


def test_password_hashes_are_salted():
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_password_handles_missing_or_broken_hashes():
    assert not verify_password("x", None)
    assert not verify_password("x", "")
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("x", "scrypt$a$b$c$d$e")


# ---------------------------------------------------------------- register


def test_register_creates_a_student_and_signs_in():
    username = _name()

    try:
        response = http.post(
            "/auth/register",
            json={"username": username, "password": PASSWORD},
        )

        assert response.status_code == 201

        body = response.json()

        assert body["token_type"] == "bearer"
        assert body["user"]["username"] == username
        assert body["user"]["role"] == "student"
        assert "password" not in str(body).lower().replace("token", "")

        me = http.get("/students/me", headers=_bearer(body["access_token"]))

        assert me.status_code == 200
        assert me.json()["student_id"] > 0

    finally:
        _delete(username)


def test_register_cannot_choose_a_role():
    username = _name()

    try:
        response = http.post(
            "/auth/register",
            json={"username": username, "password": PASSWORD, "role": "admin"},
        )

        assert response.status_code == 201
        assert response.json()["user"]["role"] == "student"

    finally:
        _delete(username)


def test_register_rejects_duplicate_usernames_ignoring_case():
    username = _name("PyTest_Dup")

    try:
        first = http.post(
            "/auth/register",
            json={"username": username, "password": PASSWORD},
        )
        again = http.post(
            "/auth/register",
            json={"username": username.lower(), "password": PASSWORD},
        )

        assert first.status_code == 201
        assert again.status_code == 409

    finally:
        _delete(username)


def test_register_validates_username_and_password():
    short_password = http.post(
        "/auth/register",
        json={"username": _name(), "password": "short"},
    )
    bad_name = http.post(
        "/auth/register",
        json={"username": "no spaces allowed", "password": PASSWORD},
    )

    assert short_password.status_code == 422
    assert "at least 8" in short_password.json()["detail"][0]["msg"]
    assert bad_name.status_code == 422


# ---------------------------------------------------------------- login


def test_login_with_correct_password_ignores_username_case():
    username = _name("PyTest_Login")

    try:
        http.post(
            "/auth/register",
            json={"username": username, "password": PASSWORD},
        )

        response = http.post(
            "/auth/login",
            json={"username": username.lower(), "password": PASSWORD},
        )

        assert response.status_code == 200
        assert response.json()["user"]["username"] == username

    finally:
        _delete(username)


def test_login_failure_does_not_reveal_which_part_was_wrong():
    username = _name()

    try:
        http.post(
            "/auth/register",
            json={"username": username, "password": PASSWORD},
        )

        wrong_password = http.post(
            "/auth/login",
            json={"username": username, "password": "not-the-password"},
        )
        unknown_user = http.post(
            "/auth/login",
            json={"username": _name("nobody"), "password": PASSWORD},
        )

        assert wrong_password.status_code == 401
        assert unknown_user.status_code == 401
        assert wrong_password.json() == unknown_user.json()

    finally:
        _delete(username)


def test_account_without_a_password_cannot_log_in():
    username = _name("legacy")
    db = SessionLocal()

    try:
        db.add(User(username=username))
        db.commit()

        response = http.post(
            "/auth/login",
            json={"username": username, "password": "anything-at-all"},
        )

        assert response.status_code == 401

    finally:
        db.close()
        _delete(username)


def test_deactivated_account_is_locked_out_immediately():
    username = _name()

    try:
        token = http.post(
            "/auth/register",
            json={"username": username, "password": PASSWORD},
        ).json()["access_token"]

        db = SessionLocal()
        user = db.query(User).filter(User.username == username).one()
        user.is_active = False
        db.commit()
        db.close()

        # The existing token stops working, and so does logging in.
        assert http.get("/auth/me", headers=_bearer(token)).status_code == 401

        login = http.post(
            "/auth/login",
            json={"username": username, "password": PASSWORD},
        )

        assert login.status_code == 403

    finally:
        _delete(username)


# ---------------------------------------------------------------- tokens


def test_protected_routes_need_a_valid_token():
    assert http.get("/subjects").status_code == 401
    assert http.get("/auth/me").status_code == 401
    assert (
        http.get("/auth/me", headers=_bearer("garbage")).status_code == 401
    )


def test_expired_and_tampered_tokens_are_rejected(monkeypatch):
    from app.core import security

    user_id = ensure_account("pytest_user")

    monkeypatch.setattr(security.settings, "access_token_minutes", -5)
    expired = create_access_token(user_id, "student")

    assert http.get("/auth/me", headers=_bearer(expired)).status_code == 401

    good = create_access_token(user_id, "student")
    tampered = good[:-3] + ("AAA" if not good.endswith("AAA") else "BBB")

    assert http.get("/auth/me", headers=_bearer(tampered)).status_code == 401


def test_role_comes_from_the_database_not_the_token():
    # A student whose token claims to be an admin is still a student.
    user_id = ensure_account("pytest_user", "student")
    forged = create_access_token(user_id, "admin")

    assert http.get("/admin/users", headers=_bearer(forged)).status_code == 403


def test_public_routes_stay_public():
    assert http.get("/health").status_code == 200


# ---------------------------------------------------------------- roles


def test_students_cannot_create_courses_or_upload_material():
    headers = token_for("pytest_user", "student")

    assert (
        http.post("/subjects", headers=headers, json={"name": "X"}).status_code
        == 403
    )
    assert (
        http.post(
            "/subjects/generate", headers=headers, json={"topic": "X"}
        ).status_code
        == 403
    )
    assert (
        http.post(
            "/knowledge/ingest/subject",
            headers=headers,
            json={"subject_id": 1, "text": "x"},
        ).status_code
        == 403
    )
    assert (
        http.post(
            "/knowledge/upload/subject",
            headers=headers,
            data={"subject_id": "1"},
            files={"file": ("a.txt", b"hello")},
        ).status_code
        == 403
    )


def test_students_can_list_courses():
    headers = token_for("pytest_user", "student")

    assert http.get("/subjects", headers=headers).status_code == 200


def test_instructors_are_allowed_past_the_role_check():
    headers = token_for("pytest_instructor", "instructor")

    # Validation (422) rather than permission (403) proves the role passed.
    response = http.post("/subjects", headers=headers, json={})

    assert response.status_code == 422


def test_instructor_cannot_use_admin_routes():
    headers = token_for("pytest_instructor", "instructor")

    assert http.get("/admin/users", headers=headers).status_code == 403


def test_students_cannot_read_or_change_other_students_data(test_student):
    other = token_for("pytest_other_user", "student")

    assert (
        http.get(f"/students/{test_student}/mastery", headers=other).status_code
        == 403
    )
    assert (
        http.patch(
            f"/students/{test_student}/level",
            headers=other,
            json={"learning_level": "advanced"},
        ).status_code
        == 403
    )
    assert (
        http.post(
            "/tutor/quiz",
            headers=other,
            json={"student_id": test_student, "concept_id": 1},
        ).status_code
        == 403
    )
    assert (
        http.get(
            f"/students/{test_student}/subjects/1/next", headers=other
        ).status_code
        == 403
    )


def test_students_cannot_open_another_users_profile(test_student):
    owner = http.get(
        "/students/me", headers=token_for("pytest_user")
    ).json()
    other = token_for("pytest_other_user")

    assert (
        http.get(f"/students/{owner['user_id']}/profile", headers=other)
        .status_code
        == 403
    )


def test_staff_can_read_but_not_act_as_a_student(test_student, monkeypatch):
    staff = token_for("pytest_instructor", "instructor")

    assert (
        http.get(f"/students/{test_student}/mastery", headers=staff).status_code
        == 200
    )

    # Taking a quiz as someone else is not allowed, even for staff.
    monkeypatch.setattr(quiz, "retrieve_with_subject_fallback", lambda **k: [])
    response = http.post(
        "/tutor/quiz",
        headers=staff,
        json={"student_id": test_student, "concept_id": 1},
    )

    assert response.status_code == 403

    assert (
        http.patch(
            f"/students/{test_student}/level",
            headers=staff,
            json={"learning_level": "advanced"},
        ).status_code
        == 403
    )


def test_students_cannot_set_mastery_directly(test_student):
    response = http.post(
        f"/students/{test_student}/mastery",
        headers=token_for("pytest_user"),
        json={"concept_id": 1, "mastery_score": 1.0},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------- admin


def test_admin_can_list_users_without_password_hashes():
    headers = token_for("pytest_admin", "admin")

    response = http.get("/admin/users", headers=headers)

    assert response.status_code == 200
    assert "password_hash" not in response.text
    assert any(u["username"] == "pytest_admin" for u in response.json())


def test_admin_can_change_role_and_the_change_applies_at_once():
    username = _name()

    try:
        token = http.post(
            "/auth/register",
            json={"username": username, "password": PASSWORD},
        ).json()
        user_id = token["user"]["id"]
        student = _bearer(token["access_token"])

        assert http.post("/subjects", headers=student, json={}).status_code == 403

        promoted = http.patch(
            f"/admin/users/{user_id}",
            headers=token_for("pytest_admin", "admin"),
            json={"role": "instructor"},
        )

        assert promoted.status_code == 200
        assert promoted.json()["role"] == "instructor"

        # Same token, new permissions.
        assert http.post("/subjects", headers=student, json={}).status_code == 422

    finally:
        _delete(username)


def test_admin_can_reset_a_password():
    username = _name()

    try:
        user_id = http.post(
            "/auth/register",
            json={"username": username, "password": PASSWORD},
        ).json()["user"]["id"]

        reset = http.patch(
            f"/admin/users/{user_id}",
            headers=token_for("pytest_admin", "admin"),
            json={"password": "brand-new-password"},
        )

        assert reset.status_code == 200

        old = http.post(
            "/auth/login", json={"username": username, "password": PASSWORD}
        )
        new = http.post(
            "/auth/login",
            json={"username": username, "password": "brand-new-password"},
        )

        assert old.status_code == 401
        assert new.status_code == 200

    finally:
        _delete(username)


def test_admin_cannot_remove_the_last_admin():
    # Make pytest_admin the only active admin for this check.
    db = SessionLocal()

    try:
        db.query(User).filter(
            User.role == "admin", User.username != "pytest_admin"
        ).update({"is_active": False})
        db.commit()

        admin_id = ensure_account("pytest_admin", "admin")
        headers = token_for("pytest_admin", "admin")

        demote = http.patch(
            f"/admin/users/{admin_id}", headers=headers, json={"role": "student"}
        )
        deactivate = http.patch(
            f"/admin/users/{admin_id}",
            headers=headers,
            json={"is_active": False},
        )

        assert demote.status_code == 400
        assert deactivate.status_code == 400

    finally:
        db.query(User).filter(User.role == "admin").update(
            {"is_active": True}
        )
        db.commit()
        db.close()


def test_admin_update_of_unknown_user_is_404():
    response = http.patch(
        "/admin/users/99999999",
        headers=token_for("pytest_admin", "admin"),
        json={"role": "student"},
    )

    assert response.status_code == 404


def test_ensure_admin_creates_and_promotes_without_resetting_passwords():
    from app.services.admin_account import ensure_admin

    username = _name("pytest_boot")
    db = SessionLocal()

    try:
        created = ensure_admin(db, username, "initial-password-1")

        assert created.role == "admin"
        assert verify_password("initial-password-1", created.password_hash)

        again = ensure_admin(db, username.upper(), "different-password-2")

        assert again.id == created.id
        assert verify_password("initial-password-1", again.password_hash)

    finally:
        db.close()
        _delete(username)
