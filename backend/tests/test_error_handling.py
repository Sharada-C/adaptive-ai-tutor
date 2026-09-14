from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_diagnostic_start_invalid_student():
    response = client.post(
        "/tutor/diagnostic/start",
        json={
            "student_id": 999999,
            "subject_id": 1,
            "limit": 2,
        },
    )

    assert response.status_code == 404
def test_diagnostic_start_invalid_subject():
    response = client.post(
        "/tutor/diagnostic/start",
        json={
            "student_id": 1,
            "subject_id": 999999,
            "limit": 2,
        },
    )

    assert response.status_code == 404

def test_diagnostic_start_invalid_limit():
    response = client.post(
        "/tutor/diagnostic/start",
        json={
            "student_id": 1,
            "subject_id": 1,
            "limit": 0,
        },
    )

    assert response.status_code == 422