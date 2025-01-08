import requests
import json
import time

def test_flow():
    base_url = "http://localhost:8000"
    
    print("\n1. Testing server status...")
    try:
        response = requests.get(f"{base_url}/auth/test")
        print(f"Server status: {response.json()}")
    except Exception as e:
        print(f"Server error: {str(e)}")
        return
    
    print("\n2. Testing login...")
    login_data = {
        "username": "superadmin",
        "password": "admin123"
    }
    try:
        response = requests.post(
            f"{base_url}/auth/login",
            json=login_data
        )
        print(f"Login response status: {response.status_code}")
        print(f"Login response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            print(f"\nLogin successful!")
            print(f"Token: {token}")
            print(f"Role: {data.get('role')}")
            
            # Check active sessions
            time.sleep(1)  # Wait for server to process
            response = requests.get(f"{base_url}/auth/test")
            print(f"\nActive sessions after login: {response.json()}")
            
            return token
    except Exception as e:
        print(f"Login error: {str(e)}")
        return None

if __name__ == "__main__":
    test_flow()
