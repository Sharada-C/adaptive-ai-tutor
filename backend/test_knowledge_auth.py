
import requests
import getpass
import io
import sys

BASE_URL = "http://127.0.0.1:8001"

session = requests.Session()

# --------------------------------------------------
# 1. Login and obtain student JWT
# --------------------------------------------------

print("\n========== STUDENT LOGIN ==========")

email = input("Enter student email: ")
password = getpass.getpass("Enter student password: ")

login_response = session.post(
    f"{BASE_URL}/auth/login",
    json={
        "email": email,
        "password": password
    },
    timeout=15
)

if login_response.status_code != 200:
    print("LOGIN FAILED:", login_response.status_code)
    print(login_response.text)
    sys.exit(1)

token = login_response.json()["access_token"]

student_headers = {
    "Authorization": f"Bearer {token}"
}

print("Login successful. Student JWT obtained.")

# --------------------------------------------------
# 2. Test helper
# --------------------------------------------------

results = []

def check_endpoint(name, method, url, expected_status,
                   headers=None, json_body=None,
                   multipart=False):

    try:
        if multipart:
            # Create a fresh in-memory text file for each request.
            files = {
                "file": (
                    "test_knowledge.txt",
                    io.BytesIO(b"Test knowledge content"),
                    "text/plain"
                )
            }

            data = {
                "concept_id": "1"
            } if url.endswith("/upload") else {
                "subject_id": "1"
            }

            response = session.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=30
            )

        else:
            response = session.post(
                url,
                headers=headers,
                json=json_body,
                timeout=30
            )

        passed = response.status_code == expected_status

        results.append(passed)

        status = "PASS" if passed else "FAIL"

        print(
            f"{status} | {name} | "
            f"Expected: {expected_status} | "
            f"Actual: {response.status_code}"
        )

        if not passed:
            print("Response:", response.text[:500])

    except requests.RequestException as error:
        results.append(False)
        print(f"FAIL | {name} | Request error: {error}")


# --------------------------------------------------
# 3. Endpoint test data
# --------------------------------------------------

endpoints = [
    {
        "name": "POST /knowledge/ingest",
        "url": f"{BASE_URL}/knowledge/ingest",
        "json": {
            "concept_id": 1,
            "text": "Operating system process management.",
            "source": "auth-test"
        },
        "multipart": False
    },
    {
        "name": "POST /knowledge/upload",
        "url": f"{BASE_URL}/knowledge/upload",
        "multipart": True
    },
    {
        "name": "POST /knowledge/ingest/subject",
        "url": f"{BASE_URL}/knowledge/ingest/subject",
        "json": {
            "subject_id": 1,
            "text": "Computer networks and TCP/IP.",
            "source": "auth-test"
        },
        "multipart": False
    },
    {
        "name": "POST /knowledge/upload/subject",
        "url": f"{BASE_URL}/knowledge/upload/subject",
        "multipart": True
    }
]


# --------------------------------------------------
# 4. Test without JWT: Expect 401
# --------------------------------------------------

print("\n========== TESTING WITHOUT JWT ==========")

for endpoint in endpoints:
    check_endpoint(
        name=endpoint["name"] + " | No JWT",
        method="POST",
        url=endpoint["url"],
        expected_status=401,
        headers=None,
        json_body=endpoint.get("json"),
        multipart=endpoint.get("multipart", False)
    )


# --------------------------------------------------
# 5. Test with student JWT: Expect 403
# --------------------------------------------------

print("\n========== TESTING WITH STUDENT JWT ==========")

for endpoint in endpoints:
    check_endpoint(
        name=endpoint["name"] + " | Student JWT",
        method="POST",
        url=endpoint["url"],
        expected_status=403,
        headers=student_headers,
        json_body=endpoint.get("json"),
        multipart=endpoint.get("multipart", False)
    )


# --------------------------------------------------
# 6. Final summary
# --------------------------------------------------

print("\n========== FINAL TEST SUMMARY ==========")

passed = sum(results)
total = len(results)
failed = total - passed

print(f"Total tests : {total}")
print(f"Passed      : {passed}")
print(f"Failed      : {failed}")

if failed == 0:
    print("\nALL KNOWLEDGE AUTHENTICATION TESTS PASSED!")
else:
    print("\nSOME TESTS FAILED. Review the responses above.")
    sys.exit(1)
