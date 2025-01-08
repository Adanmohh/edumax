import requests
import logging
import http.client as http_client
import sys

def test_curriculum_endpoint():
    # Enable debug logging
    http_client.HTTPConnection.debuglevel = 1
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True
    
    print("\nTesting database connection...", file=sys.stderr)
    try:
        # First get a session token
        login_response = requests.post(
            'http://localhost:8000/auth/login',
            json={'username': 'admin', 'password': 'admin123'}
        )
        print("\nLogin Response:", file=sys.stderr)
        print(f"Status: {login_response.status_code}", file=sys.stderr)
        print(f"Body: {login_response.json()}", file=sys.stderr)
        
        token = login_response.json()['token']
        
        # Then test the curriculum endpoint
        print("\nTesting curriculum endpoint...", file=sys.stderr)
        curriculum_response = requests.get(
            'http://localhost:8000/curriculum',
            params={'session_token': token, 'school_id': 1}
        )
        print("\nCurriculum Response:", file=sys.stderr)
        print(f"Status: {curriculum_response.status_code}", file=sys.stderr)
        print(f"Headers: {dict(curriculum_response.headers)}", file=sys.stderr)
        
        # Try to get JSON response
        try:
            json_response = curriculum_response.json()
            print(f"JSON Body: {json_response}", file=sys.stderr)
            if curriculum_response.status_code >= 400:
                print("\nError Details:", file=sys.stderr)
                print(f"Error Message: {json_response.get('error')}", file=sys.stderr)
                print(f"Error Type: {json_response.get('type')}", file=sys.stderr)
                print(f"Traceback: {json_response.get('traceback')}", file=sys.stderr)
        except ValueError:
            print(f"Raw Body: {curriculum_response.text}", file=sys.stderr)
            print(f"Response Content: {curriculum_response.content}", file=sys.stderr)
            print(f"Response Encoding: {curriculum_response.encoding}", file=sys.stderr)
            
        # Raise for status to get detailed error info
        curriculum_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"\nError making request: {str(e)}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_json = e.response.json()
                print(f"Error Response JSON: {error_json}", file=sys.stderr)
            except ValueError:
                print(f"Error Response Text: {e.response.text}", file=sys.stderr)
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}", file=sys.stderr)
        import traceback
        print(f"Traceback: {traceback.format_exc()}", file=sys.stderr)

if __name__ == "__main__":
    test_curriculum_endpoint()
