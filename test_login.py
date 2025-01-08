import requests

response = requests.post(
    "http://localhost:8001/auth/login",
    json={
        "username": "superadmin",
        "password": "admin123"
    }
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
