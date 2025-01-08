import requests
import json

url = "http://127.0.0.1:8000/auth/register"
headers = {"Content-Type": "application/json"}
data = {
    "username": "admin",
    "password": "admin123",
    "role": "superadmin",
    "school_id": 1
}

response = requests.post(url, headers=headers, json=data)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
