import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Load environment variables
load_dotenv(override=True)

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

print("Verifying collection contents...")

try:
    # Initialize client
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=10
    )
    
    # Get collection info
    collection_name = "test_collection_2"
    collection_info = client.get_collection(collection_name)
    print(f"\nCollection info:")
    print(collection_info)
    
    # Count points
    count = client.count(collection_name=collection_name)
    print(f"\nPoints in collection: {count.count}")
    
    # Get a sample point
    points = client.scroll(
        collection_name=collection_name,
        limit=1
    )[0]
    if points:
        point = points[0]
        print(f"\nSample point:")
        print(f"ID: {point.id}")
        print(f"Vector length: {len(point.vector)}")
        print(f"Payload preview: {str(point.payload)[:200]}...")
    
except Exception as e:
    print(f"Error: {str(e)}")
    if hasattr(e, 'response'):
        print(f"Response content: {e.response.content}")
