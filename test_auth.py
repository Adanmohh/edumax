import requests

url = "http://127.0.0.1:8000/auth/test"
response = requests.get(url)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
