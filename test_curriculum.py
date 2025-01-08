import requests

token = "149eff921bb04f30bf5e3a513c539692"

# Test curriculum endpoint
response = requests.get(
    "http://localhost:8001/curriculum",
    params={"session_token": token}
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
