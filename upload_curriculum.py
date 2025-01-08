import requests
import json

# Session token from login response
token = "a9c0a32225e543cdb34e411ad50f0429"

# 1. Upload the file
upload_url = "http://127.0.0.1:8000/curriculum/upload"

# Prepare the multipart form data
with open('my_app/uploaded_files/VOTA - hyvien väestösuhteiden suunnittelutyökalu (1).pdf', 'rb') as f:
    files = {
        'file': ('VOTA - hyvien väestösuhteiden suunnittelutyökalu (1).pdf', f, 'application/pdf')
    }
    data = {
        'name': 'VOTA Curriculum',
        'school_id': '1',
        'session_token': token
    }
    upload_response = requests.post(upload_url, files=files, data=data)
print("Upload Response:")
print(f"Status Code: {upload_response.status_code}")
print(f"Response: {upload_response.text}")

if upload_response.status_code == 200:
    curriculum_data = upload_response.json()
    curriculum_id = curriculum_data['curriculum_id']

    # 2. Start ingestion
    ingest_url = "http://127.0.0.1:8000/curriculum/ingest"
    ingest_data = {
        "curriculum_id": curriculum_id,
        "collection_name": f"curriculum_{curriculum_id}",
        "session_token": token
    }
    ingest_response = requests.post(ingest_url, json=ingest_data)
    print("\nIngestion Response:")
    print(f"Status Code: {ingest_response.status_code}")
    print(f"Response: {ingest_response.text}")
