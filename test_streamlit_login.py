import requests
import json

def test_login():
    print("\nTesting login functionality...")
    
    # Test login endpoint
    login_url = "http://localhost:8000/auth/login"
    credentials = {
        "username": "superadmin",
        "password": "admin123"
    }
    
    print(f"\nSending request to {login_url}")
    print(f"Request body: {json.dumps(credentials, indent=2)}")
    
    try:
        response = requests.post(login_url, json=credentials)
        print(f"\nResponse status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print("\nLogin successful!")
            print(f"Token: {data.get('token')}")
            print(f"Role: {data.get('role')}")
            print(f"School ID: {data.get('school_id')}")
            return True
        else:
            print("\nLogin failed!")
            return False
            
    except Exception as e:
        print(f"\nError: {str(e)}")
        return False

if __name__ == "__main__":
    test_login()
