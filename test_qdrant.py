import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
import urllib.parse

# Force reload environment variables
load_dotenv(override=True)

# Get credentials
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

print("Qdrant Configuration:")
print(f"URL: {QDRANT_URL}")
print(f"Raw API Key: {QDRANT_API_KEY}")

try:
    # Simple connection with API key
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=10
    )
    # Try to list collections
    collections = client.get_collections()
    print("Qdrant connection successful!")
    print("Available collections:", collections)
except Exception as e:
    print(f"Error connecting to Qdrant: {str(e)}")
    if hasattr(e, 'response'):
        print(f"Response status code: {e.response.status_code}")
        print(f"Response headers: {e.response.headers}")
        print(f"Response content: {e.response.content}")
