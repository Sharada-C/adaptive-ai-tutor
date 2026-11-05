
import requests
import getpass
import sys

BASE_URL = "http://127.0.0.1:8001"

print("\n========== LOGIN ==========")

email = input("Student email: ")
password = getpass.getpass("Student password: ")

login = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": email, "password": password},
    timeout=15,
)

if login.status_code != 200:
    print("Login failed:", login.status_code, login.text)
    sys.exit(1)

token = login.json()["access_token"]

student_headers = {
    "Authorization": f"Bearer {token}"
}

# Student profile 8 belongs to this test account.
# Profile 1 belongs to another account.
student_id = 8
other_student_id = 1

# Use an existing concept ID.
concept_id = int(input("Enter an existing concept ID: "))

tests = [
    (
        "No JWT",
        f"{BASE_URL}/tutor/next/{student_id}/{concept_id}",
        None,
        401,
    ),
    (
        "Own student profile",
        f"{BASE_URL}/tutor/next/{student_id}/{concept_id}",
        student_headers,
        200,
    ),
    (
        "Another student's profile",
        f"{BASE_URL}/tutor/next/{other_student_id}/{concept_id}",
        student_headers,
        403,
    ),
    (
        "Nonexistent student profile",
        f"{BASE_URL}/tutor/next/999999/{concept_id}",
        student_headers,
        404,
    ),
]

passed = 0

print("\n========== NEXT ACTION AUTH TESTS ==========")

for name, url, headers, expected in tests:
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=30,
        )

        success = response.status_code == expected

        print(
            f"{'PASS' if success else 'FAIL'} | {name} | "
            f"Expected: {expected} | Actual: {response.status_code}"
        )

        if success:
            passed += 1
        else:
            print("Response:", response.text[:500])

    except requests.RequestException as error:
        print(f"FAIL | {name} | {error}")

print("\n========== SUMMARY ==========")
print(f"Passed: {passed}/4")
print(f"Failed: {4-passed}/4")

if passed == 4:
    print("ALL NEXT ACTION AUTH TESTS PASSED!")
else:
    sys.exit(1)
