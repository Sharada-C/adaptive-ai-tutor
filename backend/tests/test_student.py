from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_student_mastery():
    response = client.get("/students/1/mastery")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)

    for mastery in data:
        assert "concept_id" in mastery
        assert "mastery_score" in mastery
        assert 0.0 <= mastery["mastery_score"] <= 1.0