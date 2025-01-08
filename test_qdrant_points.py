import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models
import numpy as np

# Load environment variables
load_dotenv(override=True)

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

print("Attempting to add points to collection...")

try:
    # Initialize client
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=10
    )
    
    # Create test vector with exact values from OpenAI embedding
    test_vector = np.array([-0.00568144, -0.02810439, 0.02810439, -0.00384514, -0.0159536] + [0.0] * 1531, dtype=np.float32)
    print(f"Test vector length: {len(test_vector)}")
    print(f"First 5 values: {test_vector[:5]}")
    
    # Test payload similar to document
    test_payload = {"text": "VOTA - hyvien\nväestösuhteiden\nsuunnittelutyökalu"}
    print(f"Test payload: {test_payload}")
    
    # Add point to collection
    operation_info = client.upsert(
        collection_name="test_collection_2",
        points=[
            models.PointStruct(
                id=1,
                vector=test_vector.tolist(),
                payload=test_payload
            )
        ]
    )
    
    print("Point added successfully!")
    print("Operation info:", operation_info)
    
    # Count points to verify
    count = client.count(collection_name="test_collection_2")
    print(f"\nPoints in collection: {count.count}")
    
except Exception as e:
    print(f"Error: {str(e)}")
    if hasattr(e, 'response'):
        print(f"Response content: {e.response.content}")
