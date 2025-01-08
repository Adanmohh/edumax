import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Load environment variables
load_dotenv(override=True)

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

print("Attempting to create and configure collection...")

try:
    # Initialize client
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=10
    )
    
    # Delete collection if exists
    collection_name = "test_collection_2"
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)
        print(f"Deleted existing collection '{collection_name}'")

    # Create collection with explicit settings
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=1536,  # OpenAI embedding dimension
            distance=models.Distance.COSINE,
            on_disk=True  # Try with on-disk storage
        ),
        optimizers_config=models.OptimizersConfigDiff(
            memmap_threshold=20000  # Use memory mapping for large collections
        ),
        timeout=30  # Increase timeout for collection creation
    )
    
    print(f"Collection '{collection_name}' created successfully!")
    
    # List all collections to verify
    collections = client.get_collections()
    print("\nAvailable collections:", collections)
    
except Exception as e:
    print(f"Error: {str(e)}")
    if hasattr(e, 'response'):
        print(f"Response content: {e.response.content}")
